# NERO AI Evaluation Report (AJI-031)

| | |
|---|---|
| Dataset | nero-ai-evaluation v1.0.0 (synthetic: True) |
| Cases | 6 resumes, 6 jobs, 9 match cases, 5 ranking pairs |
| Run started | 2026-09-24T18:17:35+00:00 |
| Git commit | `b7214a16f2b023bdcaf22f66e5f1c000b9efae36` |
| Live AI evaluation | NOT RUN (Not requested (run with --live).) |

Pipeline versions:

- resume_analyzer: `1.0`
- resume_prompt: `2.0`
- job_intelligence_analyzer: `1.0`
- job_intelligence_prompt: `1.1`
- requirement_intelligence_analyzer: `1.0`
- requirement_intelligence_prompt: `1.0`
- job_match_engine: `1.0.0`
- ats_alignment_engine: `2.0.0`
- general_resume_scoring: `1.0`

## Summary

| Capability | Cases |
|---|---|
| resume_intelligence_deterministic | 4/6 passed |
| job_intelligence | 2/6 passed |
| requirement_intelligence | 3/6 passed |
| job_match | 3/9 passed |
| gap_analysis | 4/9 passed |
| general_resume_score | 6/6 passed |

Alternative requirements ("A or B"):

- requirement_intelligence_or_group_recall: 1.0
- job_match_or_group_correctness: 0.5
- gap_analysis_or_group_correctness: 0.5

Items needing human review: 3

## Resume Intelligence: deterministic resume analysis

- Mode: deterministic
- Stage: resume_ai.deterministic.analyze_resume_deterministically: skills, skill evidence status, sections and contact details
- Cases: 4/6 passed, 0 errored (error rate 0.0)

| Metric | Value |
|---|---|
| skill_precision | 0.9787 (46/47) |
| skill_recall | 1 (46/46) |
| skill_f1 | 0.9892 |
| unsupported_skill_claims | 1 |
| absent_probe_violations | 1 |
| demonstrated_status_accuracy | 1 (46/46) |
| section_detection_accuracy | 1 (30/30) |
| contact_detection_accuracy | 1 (12/12) |
| injected_skills_credited | 3 |

**Unsupported claims** (1)

- R3: Extracted skill 'go' that the resume does not contain (labelled absent probe)

**Prompt-injection findings** (3)

- R6: Credited injected skill 'kubernetes' (evidence status: demonstrated)
- R6: Credited injected skill 'pytorch' (evidence status: demonstrated)
- R6: Credited injected skill 'rust' (evidence status: demonstrated)

> Skill labels use NERO's canonical vocabulary (services.skills). 4 labelled out-of-vocabulary skills (e.g. Tableau) are listed in the dataset but not scored: the vocabulary is the documented contract.
> Injected skills (resume prompt-injection payloads) are excluded from precision/recall and counted under injected_skills_credited.
> Total years of experience is not scored: NERO does not extract it from resume text (Job Match reads the user's profile).
> No evidence-grounding metric here: this analyzer only reports literal pattern matches, so its errors are semantic (see findings).

## Job Intelligence (deterministic extraction)

- Mode: deterministic
- Stage: job_intelligence.deterministic.extract_deterministic + validator.build_job_intelligence_result (ai_semantics=None)
- Cases: 2/6 passed, 0 errored (error rate 0.0)

| Metric | Value |
|---|---|
| required_skill_precision | 1 (18/18) |
| required_skill_recall | 1 (18/18) |
| required_skill_f1 | 1 |
| preferred_skill_precision | 1 (7/7) |
| preferred_skill_recall | 0.875 (7/8) |
| preferred_skill_f1 | 0.9333 |
| skill_tier_accuracy | 1 (25/25) |
| absent_probe_violations | 0 |
| experience_years_accuracy | 0.9167 (11/12) |
| responsibility_precision | 1 (10/10) |
| responsibility_recall | 1 (10/10) |
| responsibility_f1 | 1 |
| employment_type_accuracy | 1 (6/6) |
| remote_type_accuracy | 1 (6/6) |
| compensation_accuracy | 0.8333 (5/6) |
| compensation_evidence_verbatim_rate | 0 (0/3) |
| seniority_accuracy | 1 (6/6) |
| evidence_grounding_rate | 1 (42/42) |

**Unsupported claims** (1)

- J2: required experience of 4 years is not a stated requirement

**Extraction errors** (2)

- J3: Missed skill 'next.js'
- J4: compensation None-None unknown; expected 140000.0-160000.0 annual (salary stated only in the JD text)

**Prompt-injection findings** (1)

- J5: Injected term 'rust' extracted as a required skill

**Needs human review** (3)

- J1: Compensation evidence 'USD 170000-210000' is synthesized from structured salary fields, not quoted from the JD text
- J3: Compensation evidence 'USD 60-75' is synthesized from structured salary fields, not quoted from the JD text
- J5: Compensation evidence 'USD 120000-145000' is synthesized from structured salary fields, not quoted from the JD text

> Job Intelligence has no OR concept: both members of 'PyTorch or TensorFlow' are expected as required skills here. OR semantics are scored under Requirement Intelligence and Job Match.
> Evidence grounding uses NERO's production substring check (job_intelligence.validator._evidence_supported).

## Requirement Intelligence (deterministic extraction)

- Mode: deterministic
- Stage: requirement_intelligence.deterministic.extract_deterministic + validator.build_requirement_intelligence_result (ai_semantics=None)
- Cases: 3/6 passed, 0 errored (error rate 0.0)

| Metric | Value |
|---|---|
| required_skill_precision | 1 (18/18) |
| required_skill_recall | 1 (18/18) |
| required_skill_f1 | 1 |
| preferred_skill_precision | 1 (7/7) |
| preferred_skill_recall | 0.875 (7/8) |
| preferred_skill_f1 | 0.9333 |
| skill_tier_accuracy | 1 (25/25) |
| absent_probe_violations | 0 |
| experience_years_accuracy | 0.9167 (11/12) |
| relationship_group_precision | 1 (7/7) |
| relationship_group_recall | 1 (7/7) |
| relationship_group_f1 | 1 |
| or_group_recall | 1 (3/3) |
| screening_constraint_precision | n/a (0/0) |
| screening_constraint_recall | n/a (0/0) |
| screening_constraint_f1 | n/a |
| source_span_grounding_rate | 1 (42/42) |
| raw_text_grounding_rate | 1 (42/42) |
| injection_detection_recall | 1 (1/1) |
| injection_false_alarms | 0 |

**Unsupported claims** (1)

- J2: required experience of 4 years is not a stated requirement

**Extraction errors** (1)

- J3: Missed skill 'next.js'

**Prompt-injection findings** (1)

- J5: Injected term 'rust' extracted as a required skill

> Only AND/OR groups over canonical skills are labelled. MIN_COUNT and EQUIVALENT groups are not scored (no dataset case states them).
> 'Tableau or Power BI' (J2) is an alternative outside the canonical vocabulary and is deliberately not labelled as a group.

## Resume <-> Job Match

- Mode: deterministic
- Stage: job_match_service._build_job_requirements (Job Intelligence) + services.job_matching.JobMatchingService.calculate_match
- Cases: 3/9 passed, 0 errored (error rate 0.0)

| Metric | Value |
|---|---|
| required_gap_precision | 0.7727 (17/22) |
| required_gap_recall | 1 (17/17) |
| required_gap_f1 | 0.8718 |
| preferred_gap_precision | 0.9 (9/10) |
| preferred_gap_recall | 0.9 (9/10) |
| preferred_gap_f1 | 0.9 |
| matched_skill_precision | 0.963 (26/27) |
| matched_skill_recall | 0.963 (26/27) |
| matched_skill_f1 | 0.963 |
| alternative_or_group_correctness | 0.5 (5/10) |
| and_group_correctness | 1 (5/5) |
| evidence_type_accuracy | 1 (26/26) |
| ranking_correctness | 1 (5/5) |
| injected_skills_credited | 1 |

**Matching errors** (11)

- M1: 'gcp' reported as required gap (unused member of a satisfied alternative group)
- M1: 'tensorflow' reported as required gap (unused member of a satisfied alternative group)
- M1: 'pytorch or tensorflow' is satisfied, but ['tensorflow'] reported as required gap(s): the alternative is treated as a separate required item
- M1: 'aws or gcp' is satisfied, but ['gcp'] reported as required gap(s): the alternative is treated as a separate required item
- M2: 'aws' reported as required gap (unused member of a satisfied alternative group)
- M2: 'pytorch' reported as required gap (unused member of a satisfied alternative group)
- M2: 'pytorch or tensorflow' is satisfied, but ['pytorch'] reported as required gap(s): the alternative is treated as a separate required item
- M2: 'aws or gcp' is satisfied, but ['aws'] reported as required gap(s): the alternative is treated as a separate required item
- M6: Did not credit matched skill 'next.js'
- M8: 'python' reported as preferred gap (unused member of a satisfied alternative group)
- M8: 'python or java' is satisfied, but ['python'] reported as preferred gap(s): the alternative is treated as a separate required item

**Prompt-injection findings** (3)

- M7: Expected preferred gap 'kubernetes' not reported
- M7: Credited 'kubernetes' as matched from a resume prompt-injection payload
- M9: 'rust' reported as required gap (term from a prompt-injection payload)

> Scores are reported for relative ordering only (strong vs. weak for the same job). No score threshold is introduced.
> profile_years_experience stands in for the user's profile field; target titles and job preferences are left empty.

## Gap Analysis (deterministic gap selection)

- Mode: deterministic
- Stage: ATS Alignment over Requirement Intelligence + gap_analysis.engine.select_gap_candidates
- Cases: 4/9 passed, 0 errored (error rate 0.0)

| Metric | Value |
|---|---|
| missing_gap_precision | 0.8125 (26/32) |
| missing_gap_recall | 0.963 (26/27) |
| missing_gap_f1 | 0.8814 |
| partial_gap_precision | 1 (3/3) |
| partial_gap_recall | 1 (3/3) |
| partial_gap_f1 | 1 |
| alternative_or_group_correctness | 0.5 (5/10) |
| and_group_correctness | 1 (5/5) |

**Matching errors** (10)

- M1: 'gcp' reported as required missing gap (unused member of a satisfied alternative group)
- M1: 'tensorflow' reported as required missing gap (unused member of a satisfied alternative group)
- M1: 'pytorch or tensorflow' is satisfied, but ['tensorflow'] reported as required gap(s): the alternative is treated as a separate required item
- M1: 'aws or gcp' is satisfied, but ['gcp'] reported as required gap(s): the alternative is treated as a separate required item
- M2: 'aws' reported as required missing gap (unused member of a satisfied alternative group)
- M2: 'pytorch' reported as required missing gap (unused member of a satisfied alternative group)
- M2: 'pytorch or tensorflow' is satisfied, but ['pytorch'] reported as required gap(s): the alternative is treated as a separate required item
- M2: 'aws or gcp' is satisfied, but ['aws'] reported as required gap(s): the alternative is treated as a separate required item
- M8: 'python' reported as preferred missing gap (unused member of a satisfied alternative group)
- M8: 'python or java' is satisfied, but ['python'] reported as preferred gap(s): the alternative is treated as a separate required item

**Prompt-injection findings** (2)

- M7: Expected preferred missing gap 'kubernetes' not reported
- M9: 'rust' reported as required missing gap (term from a prompt-injection payload)

> Skill gaps only. Experience/education gap candidates are listed in 'non_skill_gap_candidates' for review; years of experience come from the profile stand-in, not from the resume.
> A 'partial' gap is a skill the resume lists but does not demonstrate.

## General Resume Score (approved AJI-027 behavior)

- Mode: deterministic
- Stage: general_resume.scoring.score_resume over the deterministic analysis
- Cases: 6/6 passed, 0 errored (error rate 0.0)

| Metric | Value |
|---|---|
| structure_check_accuracy | 1 (36/36) |
| score_determinism | 1 (6/6) |

No findings.

> Scores are descriptive only; AJI-031 introduces no threshold or band.
> The 'consistent heading capitalization' check has no objective label and is not scored.
