"""Builders for persisted `JobIntelligence` rows and their legacy
skill/experience items, shared by the ATS Alignment, Gap Analysis and
Job Match reconciliation tests."""

from uuid import uuid4

from apps.api.models import Job, JobIntelligence


def make_job_intelligence(
    db,
    *,
    job: Job,
    required_skills: list[dict] | None = None,
    preferred_skills: list[dict] | None = None,
    required_experience: list[dict] | None = None,
    education: list[dict] | None = None,
    certifications: list[dict] | None = None,
    content_fingerprint: str | None = None,
) -> JobIntelligence:
    structured = {
        "analysis_version": "1.0",
        "job_id": str(job.id),
        "identity": {"original_title": job.title},
        "employment": {"employment_type": "full_time"},
        "location": {"remote_type": "remote"},
        "required_skills": required_skills or [],
        "preferred_skills": preferred_skills or [],
        "required_experience": required_experience or [],
        "preferred_experience": [],
        "education": education or [],
        "certifications": certifications or [],
        "responsibilities": [],
        "authorization": {},
        "compensation": {},
        "domain": {},
    }

    record = JobIntelligence(
        id=uuid4(),
        job_id=job.id,
        content_fingerprint=content_fingerprint or f"fingerprint-{uuid4()}",
        raw_jd_snapshot={"title": job.title},
        source="test",
        source_url=job.source_url,
        analysis_version="1.0",
        analyzer_version="1.0",
        prompt_version="1.0",
        extraction_status="complete",
        structured_intelligence=structured,
    )
    db.add(record)
    db.flush()

    return record


def skill_item(canonical_skill: str, *, level: str = "required") -> dict:
    return {
        "canonical_skill": canonical_skill,
        "level": level,
        "evidence_text": f"{canonical_skill} required.",
        "confidence": "high",
    }


def experience_item(minimum_years: float, *, level: str = "required") -> dict:
    return {
        "level": level,
        "minimum_years": minimum_years,
        "evidence_text": f"{minimum_years}+ years required.",
        "confidence": "high",
    }
