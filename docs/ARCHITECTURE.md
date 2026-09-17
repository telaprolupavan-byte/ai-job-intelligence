# AJI Architecture Notes

This file tracks foundational architecture decisions that later tickets
(AJI-010 and onward) depend on. It is intentionally short — it records
conventions and decisions, not a full system design.

## Legacy models removed (AJI-009)

`JobMatch`, `ResumeAnalysis`, `ResumeRecommendation`, and `SearchRun` were
removed from `apps/api/models.py` and dropped via Alembic migration
`c8e7007f5d4a`. They were part of the original schema but had zero
references anywhere in the running application (no router, service, or
test touched them) and were superseded by `JobMatchResult` and
`ResumeAIAnalysis` respectively. `SavedJob` was intentionally kept even
though it is also currently unused — it is reserved for future
Application Tracking work.

Do not resurrect these names for new features. In particular:
- Do not add an `ats_score` field to anything named `ResumeAnalysis` —
  ATS Alignment (AJI-013) gets its own new table, separate from
  `JobMatchResult` (see "Job Match vs. ATS Alignment" below).
- Do not rebuild `ResumeRecommendation` as-is — Gap Analysis /
  Job-specific Suggestions (AJI-014/015) should be built on top of the
  evidence-based matching engine (`services.job_matching`), not on the
  pre-evidence-engine shape that table had.

## Canonical skill normalization

All skill identity/normalization goes through `services/skills`
(see `services/skills/README.md`). Resume-side deterministic analysis,
job requirement extraction, and resume/job evidence matching all resolve
skill text through this one module. Do not introduce another skill
vocabulary — extend `CANONICAL_SKILLS` in `services/skills/canonical.py`
if a new skill needs to be recognized.

## Explicit ResumeVersion selection

`apps/api/services/job_match_service.py` is the orchestration layer for
Job Match (DB access + calling the pure `services.job_matching` engine).
`calculate_job_match(db, current_user, job_id, resume_version_id=None)`
accepts an optional, explicit `resume_version_id`:

- When provided, that exact `ResumeVersion` is used. Ownership is always
  enforced (it must belong to `current_user`); a nonexistent or
  not-owned version raises the same 404 as any other unowned resource in
  this API, so existence of another user's data is never leaked.
- When omitted, the existing default behavior is unchanged: the user's
  most recently created `Resume`, preferring its master `ResumeVersion`
  and falling back to its newest version.

The `/jobs/{job_id}/match` endpoint exposes this as an optional
`resume_version_id` query parameter. No UI selector exists yet — a future
Resume Version Selection feature should call this same parameter rather
than adding a second code path.

## Analysis/scoring versioning convention

AJI will accumulate several AI/scoring artifacts (Resume Intelligence,
Job Intelligence, ATS Analysis, Job Match). `ResumeAIAnalysis` already
establishes the pattern; follow it for every new artifact table instead
of inventing new version fields per table:

| Field              | Meaning                                                                 |
|--------------------|--------------------------------------------------------------------------|
| `analysis_version` | Version of the *output schema/contract* for this artifact. Bump when the shape of the stored result changes in a way older consumers can't read. |
| `analyzer_version` | Version of the *deterministic/algorithmic* logic that produced or fed the artifact (e.g. the deterministic resume analyzer, the requirement extractor, the scoring formula). Bump when that logic changes in a way that would produce a different result for the same input. |
| `prompt_version`   | Version of the *LLM prompt* used, when an artifact involves an AI call. Bump whenever prompt text changes. Not applicable to purely deterministic artifacts (e.g. `JobMatchResult`, which has no prompt). |
| `engine_version`   | Used by purely deterministic (non-AI) scoring artifacts (e.g. `JobMatchResult`) in place of the analyzer/prompt split above — one version number for "the deterministic scoring logic that produced this result." |
| `model_provider` / `model_name` | Which AI provider/model produced an AI-derived artifact, when applicable. |

Rule of thumb: an artifact is either AI-derived (use
`analysis_version` + `analyzer_version` + `prompt_version` +
`model_provider`/`model_name`, as `ResumeAIAnalysis` does) or purely
deterministic (use a single `engine_version`, as `JobMatchResult` does).
Don't add fields that don't apply to a given artifact's nature.

Every such table is insert-only: a new analysis is a new row, never an
update to an existing one. This is what makes historical
ATS/Match/Application records immune to being silently rewritten by a
later resume edit or scoring-logic change.

## Job Match vs. ATS Alignment (do not merge these)

`JobMatchResult` (existing) answers: *"How well does this job fit the
user's profile/preferences?"* — must-have/preferred skill coverage,
experience, role/title alignment, location, and employment type
compatibility, computed by `services.job_matching`.

ATS Alignment (AJI-013, not yet implemented) will answer a different
question: *"How well does this exact ResumeVersion align with this exact
JD, the way AJI estimates an applicant tracking system would read it?"*
It is AJI's own estimate, not the employer's proprietary ATS score.

These stay as two separate tables/services, sharing the same
`services.job_matching` evidence primitives (`SkillEvidence`,
`MatchStatus`, `EvidenceType`) where appropriate, but never merged into
one score or one table. Do not add an ATS field to `JobMatchResult`, and
do not blend the two scores into a single number.

## Hard Eligibility (AJI-011)

Future pipeline ordering:

```
User Profile + Preferences
        |
Hard Eligibility          <- services/eligibility (this section)
        |
Eligible Jobs
        |
Job Intelligence           (not yet implemented)
        |
ATS Alignment               (AJI-013, not yet implemented)
        |
Job Match                  <- services/job_matching (existing, unchanged)
        |
Priority Ranking            (not yet implemented)
```

Hard Eligibility is a deterministic **pre-filter**, not a score. It
answers "is this job even a candidate for this user at all?" *before*
Job Match, ATS Alignment, or any future priority ranking ever run. A high
ATS/Job Match score must never override a hard eligibility constraint —
e.g. a Contract-only user against a 98-scoring Full-Time job is
INELIGIBLE, full stop.

**Hard Eligibility vs. Job Match vs. ATS Alignment — do not merge these:**

| | Question it answers | Output |
|---|---|---|
| Hard Eligibility | "Can this job even be considered?" | `ELIGIBLE` / `INELIGIBLE` / `UNKNOWN` + explainable checks |
| Job Match (existing) | "How well does this job fit?" | A 0-100 score |
| ATS Alignment (AJI-013, future) | "How would an ATS read this resume against this JD?" | AJI's own separate estimate |

Hard Eligibility never produces a score, never uses an LLM, and is never
merged into `JobMatchResult` or a future ATS table. Job Match's own
scoring weights (`services/job_matching/scorer.py`) are unchanged by this
ticket — Job Match may continue to use location/employment/remote type as
*soft* scoring inputs even for a job that Hard Eligibility would exclude;
it is the `/jobs/{job_id}/eligibility` pre-filter that keeps ineligible
jobs out of any pipeline that chains after it, not a change to how Job
Match scores.

### Package layout

- `services/eligibility/` — the pure, DB-free, LLM-free engine
  (`contracts.py`, `location.py`, `job_signals.py`, `engine.py`), mirroring
  `services/job_matching`'s DB/AI-free-core convention. `evaluate_eligibility(criteria, job)`
  is a plain function of two dataclasses to an `EligibilityResult`, so it
  is trivial to unit test and cheap to run over many jobs.
- `apps/api/services/eligibility_service.py` — the orchestration layer
  that builds `UserEligibilityCriteria`/`JobEligibilitySignals` from the
  `Preference`/`Profile`/`Job` ORM models and calls the pure engine.
  `evaluate_jobs_eligibility()` builds the user's criteria exactly once
  and reuses it across every job — no N+1 queries, no re-parsing job text
  per constraint.
- `GET /jobs/{job_id}/eligibility` (authenticated) — returns the result
  for one job. Not persisted: eligibility is recalculated query-time from
  current Preference/Profile/Job data, since there is no concrete need
  yet for historical eligibility snapshots (unlike `JobMatchResult`/
  `ResumeAIAnalysis`, which are insert-only artifacts by design). The
  public `GET /jobs` listing is unchanged and never includes personalized
  eligibility data — only the authenticated per-job endpoint does.

### Hard constraints vs. soft preferences

A "hard constraint" can make a job `INELIGIBLE`. A "soft preference" can
only ever influence a Job Match *score*. Not every `Preference` field is
a hard constraint — only the ones below, and only when the user has
actually made them restrictive (an empty/unset field is never treated as
a hard constraint: "no restriction" must never quietly exclude jobs):

| Field | Hard when... | Also used softly by Job Match? |
|---|---|---|
| `employment_types` | non-empty (acts as an accepted-type allow-list) | Yes — first entry, unchanged |
| `locations` | non-empty (acts as an accepted-location allow-list) | Yes — first entry, unchanged |
| `remote_preference` | set (exact required remote/hybrid/onsite match) | Yes — unchanged |
| `excluded_locations` (new) | non-empty | No — hard-only |
| `requires_sponsorship` / `is_us_citizen` / `has_security_clearance` (new) | set (not `None`) | No — hard-only |
| `enforce_minimum_experience` (new) | `True` | No — hard-only |

`employment_types`/`locations`/`remote_preference` are intentionally
dual-purpose (reused, not duplicated) rather than adding a second parallel
preference system: Job Match keeps treating them as soft signals exactly
as before, while `services.eligibility` treats a non-empty/non-null value
on those same fields as a hard restriction. Salary minimums and target
titles are deliberately **not** modeled as hard constraints anywhere —
they stay Job Match-only soft signals.

Experience is a hard constraint *only* when `enforce_minimum_experience`
is explicitly enabled — the ticket's "do not automatically convert every
preference into a hard constraint" applies most directly here, since
Profile/Preference had no existing user-declared hard minimum to reuse.
When enabled, the user's `Profile.years_experience` is compared against
the job's minimum-years requirement, extracted from job text via the
existing `services.job_matching.extractor.extract_experience_requirements`
(reused as-is, not reimplemented).

### Unknown data

Jobs frequently don't disclose employment type, remote status,
sponsorship, citizenship, or an exact location. The engine never invents
an answer: a restrictive constraint whose corresponding job signal is
missing/unclear always resolves to `ConstraintStatus.UNKNOWN` on that
check. Overall `EligibilityResult.status` is:

- `INELIGIBLE` if any check `FAIL`ed (a hard failure always wins, even
  if other checks are `UNKNOWN` — it is never masked),
- else `UNKNOWN` if any check is `UNKNOWN`,
- else `ELIGIBLE`.

A missing job location, for example, is `UNKNOWN` when a location
restriction is configured — never silently treated as a match.

### Work authorization

`Preference` gained three new nullable fields — `requires_sponsorship`,
`is_us_citizen`, `has_security_clearance` — each `None` meaning
"unspecified" (the corresponding check is skipped, not assumed). These
represent only the user's own declared situation for comparison purposes;
the engine never makes a legal/immigration determination and never infers
any of them from an unrelated profile field.

On the job side, `services/eligibility/job_signals.py` deterministically
scans job text (title/description/requirements/responsibilities) for
explicit phrases — "visa sponsorship available", "unable to sponsor",
"must be authorized to work in the U.S.", "U.S. citizenship required",
"security clearance required" — into a `WorkAuthorizationSignals` struct.
No LLM call, no guessing: absence of matching language means "not
disclosed" (`None`/`False`), never "explicitly does not apply".

### Location matching

`services/eligibility/location.py` resolves a "City, ST" job location and
a user-configured location token (which may be a bare state name, a state
abbreviation, or a "City, ST" string) against each other using an exact
US state name<->abbreviation table plus case-insensitive substring
matching — e.g. a user preference of "New Jersey" matches a job located
in "Newark, NJ". This is deliberately limited to exact state resolution
and substring matching; it never does fuzzy/approximate geographic
matching.

### Testing

`tests/test_eligibility_engine.py`, `tests/test_eligibility_location.py`,
and `tests/test_eligibility_job_signals.py` unit-test the pure engine
with no database. `tests/test_eligibility_service.py` and
`tests/test_jobs_eligibility_api.py` cover the DB-backed orchestration
and the authenticated endpoint, including that two users get independent
results for the same job and that the public `/jobs` listing never leaks
personalized eligibility data.
