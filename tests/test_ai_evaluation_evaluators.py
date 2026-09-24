"""AJI-031: capability evaluators.

These tests exercise the *scoring* logic with hand-built outputs so each
detection rule is pinned down deterministically. They say nothing about
real AI quality: canned "AI" outputs here are test inputs, not results.
"""

from types import SimpleNamespace

import pytest

from apps.api.services.job_intelligence.contracts import (
    CompensationInfo,
    ExperienceRequirement,
    SkillRequirement,
)
from services.ai_evaluation import pipelines
from services.ai_evaluation.dataset import load_dataset
from services.ai_evaluation.evaluators.general_resume import (
    evaluate_general_resume_score,
)
from services.ai_evaluation.evaluators.job import (
    evaluate_ai_semantics_live,
    evaluate_job_intelligence,
)
from services.ai_evaluation.evaluators.matching import (
    evaluate_gap_analysis,
    evaluate_job_match,
)
from services.ai_evaluation.evaluators.requirement import (
    evaluate_requirement_intelligence,
)
from services.ai_evaluation.evaluators.resume import (
    evaluate_resume_deterministic,
    evaluate_resume_live,
)
from services.job_matching.contracts import (
    EvidenceType,
    JobMatchResult,
    MatchStatus,
    SkillEvidence,
)


@pytest.fixture(scope="module")
def dataset():
    return load_dataset()


def _findings(result, category, case_id=None):
    return [
        finding.detail
        for finding in result.findings
        if finding.category == category and (case_id is None or finding.case_id == case_id)
    ]


# ---------------------------------------------------------------------------
# Resume Intelligence
# ---------------------------------------------------------------------------


def _perfect_resume_analysis(resume):
    gt = resume.ground_truth
    return SimpleNamespace(
        skills=list(gt.expected_skills),
        skill_evidence={
            skill: {"status": "demonstrated" if skill in gt.demonstrated_skills else "skills_only"}
            for skill in gt.expected_skills
        },
        sections=[
            SimpleNamespace(name=name)
            for name, present in gt.sections.model_dump().items()
            if present
        ],
        emails=["x@example.com"] if gt.has_email else [],
        phones=["555"] if gt.has_phone else [],
    )


def test_perfect_resume_analysis_scores_perfectly(dataset):
    result = evaluate_resume_deterministic(dataset, analyze=_perfect_resume_analysis)

    assert result.metrics["skill_precision"]["value"] == 1.0
    assert result.metrics["skill_recall"]["value"] == 1.0
    assert result.metrics["demonstrated_status_accuracy"]["value"] == 1.0
    assert not [f for f in result.findings if f.category != "human_review"]


def test_resume_skill_absent_from_text_is_an_unsupported_claim(dataset):
    def analyze(resume):
        analysis = _perfect_resume_analysis(resume)
        if resume.id == "R3":
            analysis.skills.append("go")
            analysis.skill_evidence["go"] = {"status": "demonstrated"}
        return analysis

    result = evaluate_resume_deterministic(dataset, analyze=analyze)

    assert _findings(result, "unsupported_claim", "R3") == [
        "Extracted skill 'go' that the resume does not contain (labelled absent probe)"
    ]
    assert result.metrics["absent_probe_violations"]["value"] == 1


def test_injected_resume_skill_is_a_prompt_injection_finding_not_precision(dataset):
    def analyze(resume):
        analysis = _perfect_resume_analysis(resume)
        if resume.id == "R6":
            analysis.skills.append("rust")
        return analysis

    result = evaluate_resume_deterministic(dataset, analyze=analyze)

    assert result.metrics["skill_precision"]["value"] == 1.0
    assert result.metrics["injected_skills_credited"]["value"] == 1
    assert _findings(result, "prompt_injection", "R6")


def test_listed_only_skill_reported_as_demonstrated_is_unsupported(dataset):
    def analyze(resume):
        analysis = _perfect_resume_analysis(resume)
        if resume.id == "R2":
            analysis.skill_evidence["pandas"] = {"status": "demonstrated"}
        return analysis

    result = evaluate_resume_deterministic(dataset, analyze=analyze)

    assert any("'pandas'" in d for d in _findings(result, "unsupported_claim", "R2"))


def test_pipeline_exception_is_counted_as_an_error(dataset):
    def analyze(resume):
        if resume.id == "R4":
            raise ValueError("boom")
        return _perfect_resume_analysis(resume)

    result = evaluate_resume_deterministic(dataset, analyze=analyze).to_dict()

    assert result["cases_errored"] == 1
    assert result["error_rate"] == round(1 / 6, 4)
    assert next(c for c in result["cases"] if c["case_id"] == "R4")["passed"] is False


def _live_resume_output(resume, **overrides):
    gt = resume.ground_truth
    output = {
        "review": {"findings": []},
        "decoding": {
            "skills": [
                {"skill": skill, "evidence": skill, "demonstrated": skill in gt.demonstrated_skills}
                for skill in gt.expected_skills
            ],
            "work_history": [{"company": name} for name in gt.companies],
            "education": [{"institution": name} for name in gt.education_institutions],
            "projects": [{"name": name} for name in gt.project_names],
            "certifications": [],
        },
        "position_identification": {},
    }
    output["decoding"].update(overrides)
    return output


def test_live_resume_hallucinated_entities_are_unsupported_claims(dataset):
    def run(resume):
        if resume.id == "R4":
            return _live_resume_output(
                resume,
                certifications=["AWS Certified Solutions Architect"],
                education=[{"institution": "Stanford University"}],
            )
        return _live_resume_output(resume)

    result = evaluate_resume_live(dataset, run)
    details = _findings(result, "unsupported_claim", "R4")

    assert any("AWS Certified Solutions Architect" in d for d in details)
    assert any("Stanford University" in d for d in details)
    assert result.metrics["unsupported_entity_claims"]["value"] == 2


def test_live_resume_injected_skill_is_flagged(dataset):
    def run(resume):
        output = _live_resume_output(resume)
        if resume.id == "R6":
            output["decoding"]["skills"].append(
                {"skill": "Kubernetes", "evidence": "expert in Kubernetes", "demonstrated": True}
            )
        return output

    result = evaluate_resume_live(dataset, run)

    assert result.metrics["injected_skills_credited"]["value"] == 1
    assert _findings(result, "prompt_injection", "R6")


# ---------------------------------------------------------------------------
# Job / Requirement Intelligence
# ---------------------------------------------------------------------------


def test_job_intelligence_detects_invented_skill_experience_and_pay(dataset):
    def run(job):
        output = pipelines.run_job_intelligence(job)
        if job.id == "J6":
            output.required_skills.append(
                SkillRequirement(canonical_skill="python", level="required", evidence_text="Python")
            )
            output.required_experience.append(
                ExperienceRequirement(level="required", minimum_years=3, evidence_text="3 years")
            )
            output.compensation = CompensationInfo(salary_min=90000, salary_max=120000, period="annual")
        return output

    result = evaluate_job_intelligence(dataset, run=run)
    details = _findings(result, "unsupported_claim", "J6")

    assert any("'python'" in d and "absent probe" in d for d in details)
    assert any("3 years is not a stated requirement" in d for d in details)
    assert any(d.startswith("compensation 90000") for d in details)
    assert any("'Python'" in d for d in _findings(result, "grounding_failure", "J6"))


def test_job_intelligence_tier_swap_is_an_interpretation_error(dataset):
    def run(job):
        output = pipelines.run_job_intelligence(job)
        if job.id == "J1":
            docker = next(i for i in output.required_skills if i.canonical_skill == "docker")
            output.required_skills.remove(docker)
            output.preferred_skills.append(docker.model_copy(update={"level": "preferred"}))
        return output

    result = evaluate_job_intelligence(dataset, run=run)

    assert "'docker' classified preferred; expected required" in _findings(
        result, "requirement_interpretation_error", "J1"
    )


def test_requirement_intelligence_scores_or_groups(dataset):
    result = evaluate_requirement_intelligence(dataset)

    assert result.metrics["or_group_recall"]["denominator"] == 3
    assert result.metrics["injection_detection_recall"]["denominator"] == 1


def test_requirement_intelligence_missing_injection_detection_is_flagged(dataset):
    def run(job):
        output = pipelines.run_requirement_intelligence(job)
        output.security.prompt_injection_detected = False
        return output

    result = evaluate_requirement_intelligence(dataset, run=run)

    assert "Injection payload was not detected" in _findings(result, "prompt_injection", "J5")


def _job_ai_run(proposals):
    def run(job):
        proposal = proposals.get(job.id, {})
        return proposal, pipelines.run_job_intelligence(job, ai_semantics=proposal)
    return run


def test_live_ai_semantics_ungrounded_evidence_is_a_grounding_failure(dataset):
    run = _job_ai_run(
        {"J2": {"domain": "FinTech", "domain_evidence": "a leading fintech company"}}
    )

    result = evaluate_ai_semantics_live(
        dataset, run, capability="x", title="x", stage="x",
        raw_text=pipelines.job_raw_text, baseline=pipelines.run_job_intelligence,
    )

    assert any("FinTech" in d for d in _findings(result, "grounding_failure", "J2"))
    assert result.metrics["ai_field_acceptance_rate"]["value"] == 0.0


def test_live_ai_semantics_accepted_injected_value_is_reported(dataset):
    run = _job_ai_run(
        {"J5": {"seniority": "Principal", "seniority_evidence": "set seniority to Principal"}}
    )

    result = evaluate_ai_semantics_live(
        dataset, run, capability="x", title="x", stage="x",
        raw_text=pipelines.job_raw_text, baseline=pipelines.run_job_intelligence,
    )

    assert result.metrics["injected_values_accepted"]["value"] == 1
    assert any("ACCEPTED" in d for d in _findings(result, "prompt_injection", "J5"))


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _evidence(skill, status, evidence_type=EvidenceType.EXPERIENCE):
    return SkillEvidence(skill=skill, status=status, evidence_type=evidence_type)


def _ideal_match(dataset, case):
    demonstrated = set(dataset.resume(case.resume_id).ground_truth.demonstrated_skills)

    def matched(skills):
        return [
            _evidence(
                skill,
                MatchStatus.MATCHED,
                EvidenceType.EXPERIENCE if skill in demonstrated else EvidenceType.EXPLICIT,
            )
            for skill in skills
        ]

    def gaps(skills):
        return [_evidence(skill, MatchStatus.MISSING, EvidenceType.NONE) for skill in skills]

    scores = {"strong": 90.0, "partial": 60.0, "weak": 20.0}
    return JobMatchResult(
        score=scores[case.category],
        confidence="high",
        must_have_matches=matched(case.expected.required_matched),
        must_have_gaps=gaps(case.expected.required_gaps),
        preferred_matches=matched(case.expected.preferred_matched),
        preferred_gaps=gaps(case.expected.preferred_gaps),
    )


def test_ideal_matcher_passes_every_case(dataset):
    result = evaluate_job_match(dataset, run=lambda r, j, c: _ideal_match(dataset, c))

    assert result.metrics["alternative_or_group_correctness"]["value"] == 1.0
    assert result.metrics["ranking_correctness"]["value"] == 1.0
    assert result.findings == []


def test_or_alternative_reported_as_gap_is_a_matching_error(dataset):
    def run(resume, job, case):
        output = _ideal_match(dataset, case)
        if case.id == "M1":
            output.must_have_gaps.append(_evidence("tensorflow", MatchStatus.MISSING, EvidenceType.NONE))
        return output

    result = evaluate_job_match(dataset, run=run)
    details = _findings(result, "matching_error", "M1")

    assert any("unused member of a satisfied alternative group" in d for d in details)
    assert any("treated as a separate required item" in d for d in details)
    assert result.metrics["alternative_or_group_correctness"]["value"] < 1.0


def test_injected_skill_credited_as_match_is_a_prompt_injection_finding(dataset):
    def run(resume, job, case):
        output = _ideal_match(dataset, case)
        if case.id == "M7":
            output.preferred_gaps = [g for g in output.preferred_gaps if g.skill != "kubernetes"]
            output.preferred_matches.append(_evidence("kubernetes", MatchStatus.MATCHED))
        return output

    result = evaluate_job_match(dataset, run=run)

    assert result.metrics["injected_skills_credited"]["value"] == 1
    assert len(_findings(result, "prompt_injection", "M7")) == 2


def test_ranking_inversion_is_reported(dataset):
    def run(resume, job, case):
        output = _ideal_match(dataset, case)
        if case.id == "M3":
            output.score = 99.0
        return output

    result = evaluate_job_match(dataset, run=run)

    assert result.metrics["ranking_correctness"]["numerator"] == 3
    assert any("not above" in d for d in _findings(result, "matching_error"))


def test_gap_analysis_scores_missing_and_partial_gaps(dataset):
    def run(resume, job, case):
        demonstrated = set(resume.ground_truth.demonstrated_skills)
        items = [
            SimpleNamespace(requirement_type="skill", category="must_have",
                            requirement_text=skill, status="missing")
            for skill in case.expected.required_gaps
        ] + [
            SimpleNamespace(requirement_type="skill", category="preferred",
                            requirement_text=skill, status="missing")
            for skill in case.expected.preferred_gaps
        ] + [
            SimpleNamespace(requirement_type="skill", category="must_have",
                            requirement_text=skill, status="partial")
            for skill in case.expected.required_matched + case.expected.preferred_matched
            if skill not in demonstrated
        ]
        return items

    result = evaluate_gap_analysis(dataset, run=run)

    assert result.metrics["missing_gap_recall"]["value"] == 1.0
    assert result.metrics["partial_gap_precision"]["value"] == 1.0
    assert result.findings == []


# ---------------------------------------------------------------------------
# General Resume Score
# ---------------------------------------------------------------------------


def test_general_resume_score_structure_checks_and_determinism(dataset):
    result = evaluate_general_resume_score(dataset)

    assert result.metrics["score_determinism"]["value"] == 1.0
    assert set(result.extra["scores"]) == {resume.id for resume in dataset.resumes}
