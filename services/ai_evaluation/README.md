# NERO AI Evaluation (AJI-031)

A small, controlled, hand-labelled evaluation set, plus a repeatable
command, that measures how correct NERO's existing AI capabilities are.
It establishes a **baseline**. It does not change or tune any production
prompt, model, extractor, matcher or score.

## Application tests vs. AI evaluation

| | Application tests (`tests/`) | AI evaluation (this package) |
|---|---|---|
| Question answered | Does the code behave as designed? | Are the outputs *correct* for real-looking inputs? |
| AI providers | Mocked | Deterministic mode: none. Live mode: the real providers |
| Runs in CI | Yes | The deterministic evaluation runs in CI through `tests/test_ai_evaluation_*.py`, which also guards against regressions from the committed baseline. Live mode never runs in CI |
| Credentials | None | Live mode needs `OPENAI_API_KEY` |

A passing mocked test says nothing about AI quality. The scoring tests in
`tests/test_ai_evaluation_evaluators.py` feed hand-built outputs into the
scorers to pin down each detection rule. Those outputs are test inputs,
not measurements.

## What is evaluated, and by which mode

NERO's capabilities are split between deterministic extraction and an LLM
stage. The two are evaluated separately and never mixed:

| Capability | Production code evaluated | Mode |
|---|---|---|
| Resume Intelligence: resume analysis | `resume_ai.deterministic.analyze_resume_deterministically`. This is the resume side of Job Match, ATS, Gap Analysis and the General Resume Score | deterministic |
| Resume Intelligence: LLM analysis | `resume_ai` provider + `ResumeAIInterpreter` → `ResumeAIResult` | live |
| Job Intelligence | `job_intelligence.deterministic` + `validator` (skills, tiers, experience, responsibilities, employment, remote, compensation, seniority) | deterministic |
| Job Intelligence: AI semantics | provider + interpreter + evidence validator (title, role family, seniority, domain) | live |
| Requirement Intelligence | `requirement_intelligence.deterministic` + `validator` (tiers, AND/OR groups, screening, spans, injection signals) | deterministic |
| Requirement Intelligence: AI semantics | provider + interpreter + evidence validator | live |
| Resume ↔ Job Match | `job_match_service._build_job_requirements` + `JobMatchingService` | deterministic |
| Gap Analysis (gap selection) | ATS Alignment over Requirement Intelligence + `gap_analysis.engine.select_gap_candidates` | deterministic |
| General Resume Score | `general_resume.scoring.score_resume` (approved AJI-027 behavior) | deterministic |

Deterministic mode passes `ai_semantics=None`. This is the same path
production takes when the AI stage is unavailable. The AI-decoded fields
(title, role family, domain, and seniority when the title has none) never
feed skills, experience, matching or gaps, so every match and gap result
is fully covered without an API key.

Not covered: the AI wording layers of Gap Analysis suggestions and General
Resume improvements. Both are already restricted by production validators
to quotes and hedged templates. Measuring their wording quality needs
human rating and is recommended as a follow-up.

## Commands

```bash
# Deterministic evaluation. No credentials, no network, safe anywhere.
JWT_SECRET_KEY=any python -m services.ai_evaluation.run_eval

# Compare against the committed baseline; exit 1 on any regression.
python -m services.ai_evaluation.run_eval \
    --compare services/ai_evaluation/baselines/v1-deterministic.json \
    --fail-on-regression

# Live LLM evaluation. Calls the configured provider and costs money.
OPENAI_API_KEY=... AI_MODEL=gpt-5.6-terra \
    python -m services.ai_evaluation.run_eval --live --output-dir ai-eval-live
```

Output goes to `report.json` (machine-readable) and `report.md`, in
`ai-evaluation-output/` by default (git-ignored).

Exit codes:

- `0`: the run succeeded.
- `1`: `--fail-on-regression` was given and a metric or case regressed.
- `2`: `--live` was requested but the providers could not be created. The
  report says **NOT RUN** and gives the reason. Mocked output is never
  substituted.
- `3`: the dataset failed validation.

`JWT_SECRET_KEY` only exists because importing the API package loads its
settings. The CLI supplies a placeholder when none is set, and the
evaluation never authenticates anyone.

## Dataset (`dataset/v1/`, version 1.0.0)

Everything in the dataset is synthetic:

- company names are fictional;
- email addresses use `example.com`;
- phone numbers use `555`;
- every resume header says "Synthetic Evaluation Resume".

A test enforces this.

| File | Content |
|---|---|
| `manifest.json` | Name, version, date, and strong-vs-weak ranking pairs |
| `resumes/R*.txt` + `resumes.json` | 6 resumes (plain text) and their labels |
| `jobs.json` | 6 jobs, stored as the raw fields NERO's extractors read, with labels |
| `match_cases.json` | 9 resume × job pairs with expected matches, gaps and group outcomes |

The dataset deliberately includes:

- **Resumes:** strong and complete (R1); listed-only skills (R2);
  irrelevant skills plus the phrase "go-live" (R3); incomplete, with no
  contact details, education or bullets (R4); alternative evidence via
  TensorFlow + GCP (R5); a prompt-injection payload (R6).
- **Jobs:**
  - "PyTorch or TensorFlow" and "AWS or GCP" (J1);
  - a spurious "4 years running" (J2);
  - hourly contract pay and an AND requirement (J3);
  - a preferred "Python or Java" and salary stated only in text (J4);
  - a JD prompt-injection payload (J5);
  - an empty/vague JD as a pure hallucination probe (J6).

### Ground truth

Labels cover only fields NERO actually produces:

- **Resume:** canonical skills; which skills are *demonstrated* in
  experience or projects rather than only listed; skills deliberately
  absent (hallucination probes); sections; email and phone; bullets;
  companies, institutions and projects (for the live LLM stage); any
  injection payload and its injected terms.
- **Job:** required and preferred skills; absent skills; experience years;
  responsibilities; employment type; remote type; compensation; title
  seniority; AND/OR requirement groups; screening constraints; any
  injection payload and forbidden values.
- **Match:** expected matched skills and gaps per tier; whether each
  AND/OR group is satisfied; injected terms that must not be credited.

`dataset.validate_ground_truth` rejects inconsistent labels before any
scoring runs. It checks that:

- quotes and payloads really occur in the text;
- skill names are in NERO's canonical vocabulary;
- no skill is both expected and absent;
- each match case agrees with its resume and job labels;
- ranking pairs share a job.

### Excluded from scoring (no reliable ground truth)

- **Total years of experience from resume text:** NERO does not extract it
  (Job Match reads the user's profile). Each match case carries
  `profile_years_experience` as a stand-in for that profile field.
- **Skills outside the canonical vocabulary** (e.g. Tableau, Excel,
  Airflow): listed in the labels for visibility but not scored, because the
  vocabulary is NERO's documented contract.
- **AI normalized title, role family and domain; Resume Intelligence
  roles, profiles and review wording:** no single correct answer. They are
  listed as "needs human review" items.
- **The General Resume Score's value:** the approved AJI-027 score has no
  threshold or band, and none is introduced here. Only its objective
  structure checks and its determinism are scored; the numbers are
  reported descriptively.
- **MIN_COUNT / EQUIVALENT requirement groups:** no case states them.

## Metrics

Every metric carries its numerator and denominator. `value` is `null`
when there is nothing to measure. Metrics are reported per capability;
there is no single overall score.

- **Precision / recall / F1** (micro-averaged over cases) for:
  - extracted skills, per tier;
  - responsibilities;
  - AND/OR groups;
  - screening constraints;
  - Job Match gaps and matches;
  - Gap Analysis missing and partial gaps.
- **Accuracy** for:
  - skill tier;
  - demonstrated-vs-listed status;
  - sections and contact details;
  - experience years;
  - employment type, remote type and compensation;
  - seniority;
  - Job Match evidence type;
  - General Resume structure checks.
- **Evidence grounding:** Job Intelligence evidence text is checked with
  NERO's own production rule, `job_intelligence.validator._evidence_supported`
  (a case- and whitespace-insensitive substring match), reused in
  `grounding.py` rather than reimplemented. Requirement Intelligence
  source spans are checked against the exact character offsets.
- **Unsupported claims** are counted separately from ordinary extraction
  errors. The counters `unsupported_*`, `absent_probe_violations` and
  `unsupported_entity_claims` track them.
- **Alternative requirements:**
  - `or_group_recall` measures whether Requirement Intelligence models
    "A or B" as an OR group;
  - `alternative_or_group_correctness` measures whether Job Match and Gap
    Analysis avoid reporting the unused member of a satisfied group as a
    gap.
- **Prompt injection:**
  - `injection_detection_recall`: the existing JD detector;
  - `injected_skills_credited`: an injected term reached a skill, match
    or gap;
  - `injected_values_*`: live mode; injected values proposed or accepted
    by the AI.
- **Ranking correctness:** for the same job, a strong case scores above a
  weak one. This is a relative check, not a threshold.
- **Failure/error rate:** a pipeline exception is recorded as an `error`
  finding for that case and counted in `error_rate`.

Findings are categorized:

- `unsupported_claim`
- `extraction_error`
- `matching_error`
- `requirement_interpretation_error`
- `grounding_failure`
- `prompt_injection`
- `human_review` (never fails a case)
- `error`

## Regressions and reproducibility

- `baselines/v1-deterministic.json` is the committed baseline, and
  `baselines/v1-deterministic.md` is the same run rendered for reading.
- Each report records:
  - the dataset version;
  - the git commit, with a dirty-tree flag;
  - the pipeline versions (analyzer, prompt and engine);
  - the start time;
  - for live runs, the provider and model.
- `report.compare_reports` checks every metric against its `direction`,
  lists cases that passed before and fail now, and warns when the dataset
  version differs.
- `tests/test_ai_evaluation_report.py` fails CI if the current code
  regresses against the committed baseline.

When a later ticket intentionally changes behavior:

1. Rerun the evaluation.
2. Review the comparison.
3. Commit the new baseline in the same PR, with the reason.

Changing any label or case requires bumping the dataset version
(`dataset/v2/`). Never edit labels to make results look better.

## Adding a case

1. Add the text or fields and the labels in `dataset/<new version>/`.
2. Run the loader. Ground-truth validation lists any inconsistency.
3. Label from the text alone, before looking at NERO's output.
