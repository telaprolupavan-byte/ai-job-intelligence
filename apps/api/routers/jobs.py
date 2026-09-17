from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import get_db
from apps.api.dependencies import get_current_user
from apps.api.models import (
    Company,
    Job,
    JobMatchResult,
    Resume,
    ResumeVersion,
    User,
)
from apps.api.services.resume_ai.deterministic import (
    analyze_resume_deterministically,
)
from services.job_matching.extractor import (
    build_job_requirements,
    split_preferred_section,
)
from services.job_matching.resume_adapter import (
    build_resume_evidence_from_analysis,
)
from services.job_matching.service import JobMatchingService


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.get("")
def list_jobs(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    employment_type: str | None = Query(default=None),
    remote_type: str | None = Query(default=None),
    location: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    query = (
        select(Job, Company.name)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Job.is_active.is_(True))
    )

    if search:
        search_pattern = f"%{search.strip()}%"

        query = query.where(
            Job.title.ilike(search_pattern)
            | Company.name.ilike(search_pattern)
        )

    if employment_type:
        query = query.where(
            Job.employment_type == employment_type
        )

    if remote_type:
        query = query.where(
            Job.remote_type == remote_type
        )

    if location:
        query = query.where(
            Job.location.ilike(f"%{location.strip()}%")
        )

    count_query = select(func.count()).select_from(
        query.subquery()
    )

    total = db.scalar(count_query) or 0

    offset = (page - 1) * page_size

    query = (
        query
        .order_by(
            Job.posting_date.desc().nullslast(),
            Job.id.asc(),
        )
        .offset(offset)
        .limit(page_size)
    )

    results = db.execute(query).all()

    jobs = [
        {
            "id": str(job.id),
            "title": job.title,
            "company": company_name,
            "location": job.location,
            "country": job.country,
            "remote_type": job.remote_type,
            "employment_type": job.employment_type,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "contract_duration": job.contract_duration,
            "contract_worker_type": job.contract_worker_type,
            "description": job.description,
            "requirements": job.requirements,
            "responsibilities": job.responsibilities,
            "posting_date": (
                job.posting_date.isoformat()
                if job.posting_date
                else None
            ),
            "source": job.source,
            "source_url": job.source_url,
            "application_url": job.application_url,
            "first_seen_at": job.first_seen_at.isoformat(),
            "last_seen_at": job.last_seen_at.isoformat(),
        }
        for job, company_name in results
    ]

    return {
        "jobs": jobs,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (
                (total + page_size - 1) // page_size
                if total
                else 0
            ),
        },
    }


@router.post("/{job_id}/match")
def calculate_job_match(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate and persist a deterministic Job Match Score for the
    authenticated user against a specific job.
    """

    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    # 1. Load the job.
    job = (
        db.query(Job)
        .filter(Job.id == job_uuid)
        .first()
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    # 2. Load the user's most recent resume.
    resume = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .first()
    )

    if resume is None:
        raise HTTPException(
            status_code=404,
            detail="No resume found for this user",
        )

    # 3. Prefer the master resume version.
    resume_version = (
        db.query(ResumeVersion)
        .filter(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.is_master.is_(True),
        )
        .order_by(ResumeVersion.created_at.desc())
        .first()
    )

    # Fall back to the newest version.
    if resume_version is None:
        resume_version = (
            db.query(ResumeVersion)
            .filter(
                ResumeVersion.resume_id == resume.id
            )
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )

    if resume_version is None:
        raise HTTPException(
            status_code=404,
            detail="No resume version found for this user",
        )

    # 4. Analyze the actual resume text using the
    # existing deterministic resume analyzer.
    analysis = analyze_resume_deterministically(
        resume_version.content_text
    )

    # 5. Convert the resume analysis into Job Matching evidence.
    profile = current_user.profile

    resume_evidence = build_resume_evidence_from_analysis(
        analysis,
        experience_years=(
            profile.years_experience
            if profile
            else None
        ),
    )

    resume_titles = (
        profile.target_titles
        if profile and profile.target_titles
        else []
    )

    # 6. Build job requirements from the actual job text.
    requirement_text = "\n".join(
        part
        for part in [
            job.requirements,
            job.responsibilities,
            job.description,
        ]
        if part
    )

    must_have_text, preferred_text = split_preferred_section(
        requirement_text
    )

    job_requirements = build_job_requirements(
        must_have_text=must_have_text,
        preferred_text=preferred_text,
    )

    # 7. Load the user's matching preferences.
    preferences = current_user.preferences

    preferred_remote_type = (
        preferences.remote_preference
        if preferences
        else None
    )

    preferred_location = None

    if preferences and preferences.locations:
        preferred_location = preferences.locations[0]

    preferred_employment_type = None

    if preferences and preferences.employment_types:
        preferred_employment_type = (
            preferences.employment_types[0]
        )

    # 8. Calculate the deterministic match.
    service = JobMatchingService()

    result = service.calculate_match(
        job_title=job.title,
        job_requirements=job_requirements,
        resume_evidence=resume_evidence,
        resume_titles=resume_titles,
        job_remote_type=job.remote_type,
        job_location=job.location,
        job_employment_type=job.employment_type,
        preferred_remote_type=preferred_remote_type,
        preferred_location=preferred_location,
        preferred_employment_type=preferred_employment_type,
    )

    # 9. Convert result objects into JSON-safe dictionaries.
    result_data = {
        "score": result.score,
        "confidence": result.confidence,
        "must_have_matches": [
            {
                "skill": evidence.skill,
                "status": evidence.status.value,
                "evidence_type": evidence.evidence_type.value,
                "evidence": evidence.evidence,
            }
            for evidence in result.must_have_matches
        ],
        "must_have_gaps": [
            {
                "skill": evidence.skill,
                "status": evidence.status.value,
                "evidence_type": evidence.evidence_type.value,
                "evidence": evidence.evidence,
            }
            for evidence in result.must_have_gaps
        ],
        "preferred_matches": [
            {
                "skill": evidence.skill,
                "status": evidence.status.value,
                "evidence_type": evidence.evidence_type.value,
                "evidence": evidence.evidence,
            }
            for evidence in result.preferred_matches
        ],
        "preferred_gaps": [
            {
                "skill": evidence.skill,
                "status": evidence.status.value,
                "evidence_type": evidence.evidence_type.value,
                "evidence": evidence.evidence,
            }
            for evidence in result.preferred_gaps
        ],
        "components": [
            {
                "name": component.name,
                "score": component.score,
                "max_score": component.max_score,
                "explanation": component.explanation,
            }
            for component in result.components
        ],
        "strengths": result.strengths,
        "skill_gaps": result.skill_gaps,
    }

    # 10. Persist the match result.
    match_record = JobMatchResult(
        user_id=current_user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        engine_version=result.engine_version,
        score=result.score,
        confidence=result.confidence,
        result=result_data,
    )

    db.add(match_record)
    db.commit()
    db.refresh(match_record)

    # 11. Return the persisted result.
    return {
        "id": str(match_record.id),
        "job_id": str(job.id),
        "resume_version_id": str(resume_version.id),
        "score": result.score,
        "confidence": result.confidence,
        "engine_version": result.engine_version,
        "strengths": result.strengths,
        "skill_gaps": result.skill_gaps,
        "components": result_data["components"],
        "must_have_matches": result_data["must_have_matches"],
        "must_have_gaps": result_data["must_have_gaps"],
        "preferred_matches": result_data["preferred_matches"],
        "preferred_gaps": result_data["preferred_gaps"],
    }