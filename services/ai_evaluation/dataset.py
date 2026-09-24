"""Loading, schema validation and ground-truth validation for the AJI-031
evaluation dataset.

The dataset lives in `dataset/<version>/` as plain JSON and text files so
a developer can read every case and its labels without running anything.
Two layers of checking happen on load:

1. Schema validation: every file is parsed into the closed pydantic
   models below (`extra="forbid"`), so a typo in a field name is an error
   rather than a silently ignored label.
2. Ground-truth validation (`validate_ground_truth`): the labels must be
   internally consistent and must refer to the source text they describe.
   Evidence quotes and injection payloads must actually occur in the
   text, skill labels must be names in NERO's canonical skill vocabulary
   (`services.skills`), a skill cannot be both expected and absent, and
   every match case's expected matches/gaps must agree with its resume's
   and job's own labels. This keeps a mislabelled case from quietly
   turning into a false NERO failure (or a false pass).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from services.ai_evaluation.grounding import is_grounded
from services.skills.canonical import CANONICAL_SKILLS


DATASET_ROOT = Path(__file__).resolve().parent / "dataset"
DEFAULT_VERSION = "v1"


class DatasetError(ValueError):
    """Raised when the dataset cannot be loaded or its labels are invalid."""


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResumeInjection(_Closed):
    payload: str = Field(min_length=1)
    injected_terms: list[str] = Field(default_factory=list)


class ResumeSections(_Closed):
    summary: bool
    experience: bool
    projects: bool
    education: bool
    skills: bool


class ResumeGroundTruth(_Closed):
    expected_skills: list[str]
    demonstrated_skills: list[str]
    absent_skills: list[str]
    out_of_vocabulary_skills: list[str] = Field(default_factory=list)
    evidence_quotes: dict[str, str] = Field(default_factory=dict)
    sections: ResumeSections
    has_email: bool
    has_phone: bool
    has_bullets: bool
    companies: list[str] = Field(default_factory=list)
    education_institutions: list[str] = Field(default_factory=list)
    project_names: list[str] = Field(default_factory=list)
    # Informational only: NERO does not extract total years of experience
    # from resume text (Job Match reads the user's profile instead), so
    # this is never scored. See the README's "Excluded from scoring".
    stated_years_experience: float | None = None
    injection: ResumeInjection | None = None
    notes: str = ""


class ResumeCase(_Closed):
    id: str = Field(min_length=1)
    text_file: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    ground_truth: ResumeGroundTruth
    # Filled in by the loader from `text_file`.
    text: str = ""


class JobFields(_Closed):
    """The raw job fields NERO's extractors read (see
    `job_intelligence.deterministic.RawJobDescription`). Multi-line text
    fields are stored as a list of lines for readability and joined with
    newlines on load."""

    title: str = Field(min_length=1)
    location: str | None = None
    country: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    description: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)

    def text(self, field: str) -> str | None:
        lines = getattr(self, field)
        return "\n".join(lines) if lines else None


class ExpectedCompensation(_Closed):
    salary_min: float | None = None
    salary_max: float | None = None
    period: Literal["annual", "hourly", "unknown"] = "unknown"
    # True when the salary is stated only in free text and not in the
    # structured salary fields.
    text_only: bool = False


class ExpectedGroup(_Closed):
    relationship: Literal["AND", "OR"]
    level: Literal["required", "preferred"]
    members: list[str] = Field(min_length=2)
    evidence: str = Field(min_length=1)


class JobInjection(_Closed):
    payload: str = Field(min_length=1)
    injected_terms: list[str] = Field(default_factory=list)
    forbidden_values: dict[str, str] = Field(default_factory=dict)


class JobGroundTruth(_Closed):
    required_skills: list[str]
    preferred_skills: list[str]
    absent_skills: list[str]
    out_of_vocabulary_skills: list[str] = Field(default_factory=list)
    required_experience_years: list[float]
    preferred_experience_years: list[float]
    responsibilities: list[str]
    employment_type: str
    remote_type: Literal["remote", "hybrid", "onsite", "unknown"]
    compensation: ExpectedCompensation
    seniority: str | None = None
    requirement_groups: list[ExpectedGroup] = Field(default_factory=list)
    screening_constraint_types: list[str] = Field(default_factory=list)
    injection: JobInjection | None = None
    notes: str = ""


class JobCase(_Closed):
    id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    job: JobFields
    ground_truth: JobGroundTruth


class ExpectedMatchGroup(_Closed):
    level: Literal["required", "preferred"]
    members: list[str] = Field(min_length=2)
    satisfied: bool


class ExpectedMatch(_Closed):
    required_matched: list[str]
    required_gaps: list[str]
    preferred_matched: list[str]
    preferred_gaps: list[str]
    requirement_groups: list[ExpectedMatchGroup] = Field(default_factory=list)
    not_credited: list[str] = Field(default_factory=list)


class MatchCase(_Closed):
    id: str = Field(min_length=1)
    resume_id: str
    job_id: str
    category: Literal["strong", "partial", "weak"]
    profile_years_experience: float | None = None
    expected: ExpectedMatch
    notes: str = ""


class Ranking(_Closed):
    job_id: str
    higher: str
    lower: str


class ManifestFiles(_Closed):
    resumes: str
    jobs: str
    match_cases: str


class Manifest(_Closed):
    dataset: str
    version: str
    created: str
    ticket: str
    synthetic: bool
    description: str
    files: ManifestFiles
    rankings: list[Ranking] = Field(default_factory=list)


class EvaluationDataset(_Closed):
    manifest: Manifest
    resumes: list[ResumeCase]
    jobs: list[JobCase]
    match_cases: list[MatchCase]

    def resume(self, resume_id: str) -> ResumeCase:
        return next(item for item in self.resumes if item.id == resume_id)

    def job(self, job_id: str) -> JobCase:
        return next(item for item in self.jobs if item.id == job_id)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetError(f"Missing dataset file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetError(f"Invalid JSON in {path}: {exc}") from exc


def load_dataset(
    version: str = DEFAULT_VERSION,
    *,
    root: Path = DATASET_ROOT,
    validate: bool = True,
) -> EvaluationDataset:
    base = root / version
    raw_manifest = _read_json(base / "manifest.json")

    try:
        manifest = Manifest.model_validate(raw_manifest)
        resumes = [
            ResumeCase.model_validate(item)
            for item in _read_json(base / manifest.files.resumes)
        ]
        jobs = [
            JobCase.model_validate(item)
            for item in _read_json(base / manifest.files.jobs)
        ]
        match_cases = [
            MatchCase.model_validate(item)
            for item in _read_json(base / manifest.files.match_cases)
        ]
    except DatasetError:
        raise
    except Exception as exc:
        raise DatasetError(f"Dataset schema validation failed: {exc}") from exc

    for resume in resumes:
        text_path = base / resume.text_file

        try:
            resume.text = text_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise DatasetError(f"Missing resume text file: {text_path}") from exc

    dataset = EvaluationDataset(
        manifest=manifest,
        resumes=resumes,
        jobs=jobs,
        match_cases=match_cases,
    )

    if validate:
        errors = validate_ground_truth(dataset)

        if errors:
            raise DatasetError(
                "Ground-truth validation failed:\n- " + "\n- ".join(errors)
            )

    return dataset


# ---------------------------------------------------------------------------
# Ground-truth validation
# ---------------------------------------------------------------------------


def _non_canonical(skills: list[str]) -> list[str]:
    return [skill for skill in skills if skill not in CANONICAL_SKILLS]


def _duplicates(ids: list[str]) -> set[str]:
    return {item for item in ids if ids.count(item) > 1}


def _validate_resume(resume: ResumeCase) -> list[str]:
    errors: list[str] = []
    gt = resume.ground_truth
    prefix = f"resume {resume.id}"

    if not resume.text.strip():
        errors.append(f"{prefix}: text is empty")

    for label, skills in (
        ("expected_skills", gt.expected_skills),
        ("demonstrated_skills", gt.demonstrated_skills),
        ("absent_skills", gt.absent_skills),
    ):
        for skill in _non_canonical(skills):
            errors.append(f"{prefix}: {label} has non-canonical skill {skill!r}")

    for skill in sorted(set(gt.demonstrated_skills) - set(gt.expected_skills)):
        errors.append(f"{prefix}: demonstrated skill {skill!r} is not expected")

    for skill in sorted(set(gt.expected_skills) & set(gt.absent_skills)):
        errors.append(f"{prefix}: skill {skill!r} is both expected and absent")

    for skill in gt.out_of_vocabulary_skills:
        if skill in CANONICAL_SKILLS:
            errors.append(
                f"{prefix}: out_of_vocabulary skill {skill!r} is canonical"
            )

    for skill, quote in gt.evidence_quotes.items():
        if skill not in gt.expected_skills:
            errors.append(f"{prefix}: evidence quote for unexpected skill {skill!r}")
        if not is_grounded(quote, resume.text):
            errors.append(f"{prefix}: evidence quote for {skill!r} not in text")

    for label, values in (
        ("company", gt.companies),
        ("education institution", gt.education_institutions),
        ("project name", gt.project_names),
    ):
        for value in values:
            if not is_grounded(value, resume.text):
                errors.append(f"{prefix}: {label} {value!r} not in text")

    if gt.injection is not None:
        if not is_grounded(gt.injection.payload, resume.text):
            errors.append(f"{prefix}: injection payload not in text")

        for term in gt.injection.injected_terms:
            if term not in CANONICAL_SKILLS:
                errors.append(f"{prefix}: injected term {term!r} is not canonical")
            if term in gt.expected_skills:
                errors.append(
                    f"{prefix}: injected term {term!r} must not be an expected skill"
                )

    return errors


def _requirement_text(job: JobCase) -> str:
    return "\n".join(
        part
        for part in [job.job.text("description"), job.job.text("requirements")]
        if part
    )


def _validate_job(job: JobCase) -> list[str]:
    errors: list[str] = []
    gt = job.ground_truth
    prefix = f"job {job.id}"

    for label, skills in (
        ("required_skills", gt.required_skills),
        ("preferred_skills", gt.preferred_skills),
        ("absent_skills", gt.absent_skills),
    ):
        for skill in _non_canonical(skills):
            errors.append(f"{prefix}: {label} has non-canonical skill {skill!r}")

    for skill in sorted(set(gt.required_skills) & set(gt.preferred_skills)):
        errors.append(f"{prefix}: skill {skill!r} is both required and preferred")

    listed = set(gt.required_skills) | set(gt.preferred_skills)

    for skill in sorted(listed & set(gt.absent_skills)):
        errors.append(f"{prefix}: skill {skill!r} is both listed and absent")

    responsibilities_text = job.job.text("responsibilities") or ""

    for item in gt.responsibilities:
        if not is_grounded(item, responsibilities_text):
            errors.append(f"{prefix}: responsibility {item!r} not in text")

    requirement_text = _requirement_text(job)

    for group in gt.requirement_groups:
        if not is_grounded(group.evidence, requirement_text):
            errors.append(f"{prefix}: group evidence {group.evidence!r} not in text")

        tier = gt.required_skills if group.level == "required" else gt.preferred_skills

        for member in group.members:
            if member not in tier:
                errors.append(
                    f"{prefix}: group member {member!r} is not a "
                    f"{group.level} skill"
                )

    if gt.injection is not None:
        if not is_grounded(gt.injection.payload, requirement_text):
            errors.append(f"{prefix}: injection payload not in text")

        for term in gt.injection.injected_terms:
            if term in listed:
                errors.append(
                    f"{prefix}: injected term {term!r} must not be a listed skill"
                )

    compensation = gt.compensation

    if compensation.text_only:
        if job.job.salary_min is not None or job.job.salary_max is not None:
            errors.append(f"{prefix}: text_only compensation but salary fields set")
    elif (
        compensation.salary_min != job.job.salary_min
        or compensation.salary_max != job.job.salary_max
    ):
        errors.append(f"{prefix}: compensation labels disagree with salary fields")

    return errors


def _validate_match_case(case: MatchCase, dataset: EvaluationDataset) -> list[str]:
    prefix = f"match case {case.id}"
    resume_ids = {item.id for item in dataset.resumes}
    job_ids = {item.id for item in dataset.jobs}

    errors: list[str] = []

    if case.resume_id not in resume_ids:
        errors.append(f"{prefix}: unknown resume {case.resume_id!r}")
    if case.job_id not in job_ids:
        errors.append(f"{prefix}: unknown job {case.job_id!r}")
    if errors:
        return errors

    resume_gt = dataset.resume(case.resume_id).ground_truth
    job_gt = dataset.job(case.job_id).ground_truth
    expected = case.expected
    resume_skills = set(resume_gt.expected_skills)

    for level, matched, gaps, job_skills in (
        ("required", expected.required_matched, expected.required_gaps, job_gt.required_skills),
        ("preferred", expected.preferred_matched, expected.preferred_gaps, job_gt.preferred_skills),
    ):
        both = set(matched) & set(gaps)
        if both:
            errors.append(f"{prefix}: {level} skills both matched and gaps: {sorted(both)}")

        for skill in matched:
            if skill not in resume_skills:
                errors.append(f"{prefix}: {level} match {skill!r} not in resume labels")
            if skill not in job_skills:
                errors.append(f"{prefix}: {level} match {skill!r} not a job {level} skill")

        for skill in gaps:
            if skill in resume_skills:
                errors.append(f"{prefix}: {level} gap {skill!r} is a resume skill")
            if skill not in job_skills:
                errors.append(f"{prefix}: {level} gap {skill!r} not a job {level} skill")

        alternatives = {
            member
            for group in expected.requirement_groups
            if group.level == level and group.satisfied
            for member in group.members
        }
        covered = set(matched) | set(gaps)

        for skill in job_skills:
            if skill not in covered and skill not in alternatives:
                errors.append(f"{prefix}: job {level} skill {skill!r} is unlabelled")

    job_groups = {
        (group.level, frozenset(group.members)): group.relationship
        for group in job_gt.requirement_groups
    }

    for group in expected.requirement_groups:
        relationship = job_groups.get((group.level, frozenset(group.members)))

        if relationship is None:
            errors.append(f"{prefix}: group {group.members} not labelled on the job")
            continue

        present = [member in resume_skills for member in group.members]
        truly_satisfied = any(present) if relationship == "OR" else all(present)

        if truly_satisfied != group.satisfied:
            errors.append(
                f"{prefix}: group {group.members} satisfied={group.satisfied} "
                "disagrees with the resume labels"
            )

    for skill in expected.not_credited:
        if skill in expected.required_matched or skill in expected.preferred_matched:
            errors.append(f"{prefix}: not_credited {skill!r} is listed as matched")

    return errors


def validate_ground_truth(dataset: EvaluationDataset) -> list[str]:
    """Return every ground-truth inconsistency found (empty when valid)."""
    errors: list[str] = []

    for label, ids in (
        ("resume", [item.id for item in dataset.resumes]),
        ("job", [item.id for item in dataset.jobs]),
        ("match case", [item.id for item in dataset.match_cases]),
    ):
        for duplicate in sorted(_duplicates(ids)):
            errors.append(f"duplicate {label} id {duplicate!r}")

    for resume in dataset.resumes:
        errors.extend(_validate_resume(resume))

    for job in dataset.jobs:
        errors.extend(_validate_job(job))

    for case in dataset.match_cases:
        errors.extend(_validate_match_case(case, dataset))

    cases = {case.id: case for case in dataset.match_cases}

    for ranking in dataset.manifest.rankings:
        for case_id in (ranking.higher, ranking.lower):
            case = cases.get(case_id)
            if case is None:
                errors.append(f"ranking references unknown match case {case_id!r}")
            elif case.job_id != ranking.job_id:
                errors.append(
                    f"ranking case {case_id!r} is not for job {ranking.job_id!r}"
                )

    return errors
