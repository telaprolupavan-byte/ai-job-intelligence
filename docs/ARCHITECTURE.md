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
- Do not rebuild `ResumeRecommendation` as-is — Gap Analysis &
  Job-Specific Suggestions (delivered as AJI-015; see that section) is
  built on top of AJI-013 ATS Alignment's evidence-based requirement
  results, not on the pre-evidence-engine shape that table had.

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
- `GET /jobs/{job_id}/eligibility` (authenticated) — recalculates the
  result query-time from current Preference/Profile/Job data (evaluation
  is deterministic and cheap, so there is no staleness risk in always
  recomputing), then upserts it into `JobEligibilityResult` — one row per
  `(user_id, job_id)`, overwritten in place on every (re-)evaluation, not
  insert-only history like `JobMatchResult`/`ResumeAIAnalysis`/
  `JobIntelligence`. Eligibility has no AI cost to recompute and a future
  consumer only ever wants the *current* status, so keeping a full
  history has no concrete use yet (unlike those AI-derived artifacts,
  where a past analysis must stay stable). This makes a job's current
  hard-eligibility status queryable by a later AJI-012/AJI-013 pipeline
  step without recomputing it. The public `GET /jobs` listing is
  unchanged and never includes personalized eligibility data — only the
  authenticated per-job endpoint does.

### Hard constraints vs. soft preferences

A "hard constraint" can make a job `INELIGIBLE`. A "soft preference" can
only ever influence a Job Match *score*. Not every `Preference` field is
a hard constraint — only the ones below, and only when the user has
actually made them restrictive (an empty/unset field is never treated as
a hard constraint: "no restriction" must never quietly exclude jobs).

**This dual-purpose reuse of `employment_types`/`locations`/
`remote_preference` is an intentional design decision, confirmed as of
the AJI-011 post-push review — not an oversight.** The alternative (a
second, parallel set of "hard" preference fields duplicating these three)
was deliberately rejected per the ticket's "do not create duplicate
preference/profile systems" instruction. Restating the exact rule as
plainly as possible:

- **Hard *and* soft** (participate in Hard Eligibility *whenever
  non-empty/set*, and continue to feed Job Match's existing scoring
  exactly as before, unchanged): `employment_types`, `locations`,
  `remote_preference`.
- **Hard-only** (new in AJI-011; never read by Job Match):
  `excluded_locations`, `requires_sponsorship`, `is_us_citizen`,
  `has_security_clearance`, `enforce_minimum_experience`.
- **Soft-only** (never a hard constraint, never will silently become
  one): `target_titles`, `minimum_salary`, `minimum_hourly_rate`.

| Field | Hard when... | Also used softly by Job Match? |
|---|---|---|
| `employment_types` | non-empty (acts as an accepted-type allow-list) | Yes — first entry, unchanged |
| `locations` | non-empty (acts as an accepted-location allow-list) | Yes — first entry, unchanged |
| `remote_preference` | set (exact required remote/hybrid/onsite match) | Yes — unchanged |
| `excluded_locations` (new) | non-empty | No — hard-only |
| `requires_sponsorship` / `is_us_citizen` / `has_security_clearance` (new) | set (not `None`) | No — hard-only |
| `enforce_minimum_experience` (new) | `True` | No — hard-only |
| `target_titles` | never | Yes — soft-only, unchanged |
| `minimum_salary` / `minimum_hourly_rate` | never | Not currently read by either engine |

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

This ordering is the entire correctness contract of the engine:
**`UNKNOWN` must never be silently converted into `INELIGIBLE`.** A
missing/unclear job signal under an active hard constraint always
produces a per-check `UNKNOWN`, and `evaluate_eligibility()`'s
status-selection logic (`services/eligibility/engine.py`) only ever
promotes `UNKNOWN` checks to overall `INELIGIBLE` when a *different*,
independently-evaluated check actually `FAIL`ed — never as a side effect
of the `UNKNOWN` check itself. `tests/test_eligibility_engine.py` has a
dedicated regression test per constraint (employment type, location,
remote arrangement, sponsorship, citizenship, clearance, experience) that
asserts missing/unclear job data under that constraint alone yields
overall `UNKNOWN` with `failed_constraints == []`, plus a combination
test (`test_combination_failed_wins_over_unknown`) proving a real `FAIL`
elsewhere is what changes the outcome, not the `UNKNOWN` check itself. A
missing job location, for example, is `UNKNOWN` when a location
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

## Job/JD Intelligence (AJI-012)

Job Intelligence answers a different question from everything else in
the pipeline:

| | Question it answers |
|---|---|
| Hard Eligibility | "Can this job even be considered?" |
| **Job Intelligence (this section)** | **"What does this specific job require?"** |
| ATS Alignment (AJI-013, future) | "How would an ATS read this resume against this JD?" |
| Job Match (existing) | "How well does this job fit?" |

It converts a `Job`'s observable JD text into a structured, versioned,
evidence-backed contract. It is the canonical representation AJI-013
(ATS Alignment), AJI-014 (Job Match Reconciliation), AJI-015 (Gap
Analysis & Job-Specific Suggestions), and a future Priority Ranking
ticket all consume — none of them re-parse the raw JD text themselves.
(This roadmap line was written during AJI-012's own build; ticket
numbering shifted once delivery started — AJI-014 ended up being a Job
Match defect-fix, not Gap Analysis, so AJI-015 below covers both gap
analysis and job-specific suggestions in one ticket. See that section for
the resolution.)

**Resume Intelligence vs. Job Intelligence — do not merge these:**
Resume Intelligence (AJI-010, `apps.api.services.resume_ai`) decodes
*"who is the candidate and what does the resume demonstrate?"* from a
`ResumeVersion`. Job Intelligence decodes *"what does this job
require?"* from a `Job`. Both follow the same two-stage
deterministic-extraction-then-schema-constrained-AI-decoding shape and
the same analysis/analyzer/prompt versioning convention, but they are
independent artifacts about independent entities — neither is a
prerequisite for the other, and neither computes a score.

### Package layout

`apps/api/services/job_intelligence/` mirrors `resume_ai`'s layout
(DB-free deterministic + AI pipeline modules colocated with the DB
orchestration, since — like Resume Intelligence — this is a
single-purpose intelligence pipeline tied to one entity, not a
cross-cutting engine like `services.job_matching`/`services.eligibility`):

- `contracts.py` — the full `JobIntelligenceResult` Pydantic contract
  (see "The contract" below).
- `deterministic.py` — pure, DB-free extraction from a plain
  `RawJobDescription` dataclass (not the ORM `Job`, so it is trivial to
  unit test). Reuses existing building blocks rather than introducing
  parallel logic: `services.skills` (AJI-009 canonical vocabulary),
  `services.job_discovery.normalizer` (employment/remote type alias
  normalization), `services.job_matching.extractor.PREFERRED_SECTION_MARKERS`
  (section-heading phrases), and
  `services.eligibility.job_signals.extract_work_authorization_signals`
  (AJI-011's sponsorship/citizenship/clearance phrase detection, extended
  here only with the "preferred" nuance eligibility's boolean signals
  don't need).
- `prompts.py` / `providers/openai_provider.py` / `providers/factory.py`
  / `interpreter.py` — the AI semantic decoding stage, structured exactly
  like `resume_ai`'s equivalent modules (OpenAI Structured Outputs via
  `client.responses.parse`, a closed `extra="forbid"` schema, the same
  provider-error handling). A second AI provider abstraction was not
  introduced — this reuses the same architecture, with its own schema.
- `validator.py` — merges deterministic extraction with AI semantics
  into the final contract and is the concrete anti-hallucination check
  (see "AI safety" below).
- `service.py` — the DB-touching orchestration layer (fingerprinting,
  idempotency/caching, persistence), the same role
  `apps.api.services.resume_ai.service` plays for Resume Intelligence.

### The contract

`JobIntelligenceResult` (`contracts.py`) is deliberately not one giant
opaque JSON blob's *shape* even though it's stored in a single JSONB
column (see "Persistence" below) — every field is explicitly typed:

- **Identity**: `original_title` (verbatim), `normalized_title` /
  `role_family` / `seniority`, each optional and independently
  confidence-tagged. Never invented when evidence is insufficient — the
  field simply stays `null`.
- **Employment**: one of the enumerated employment types (including
  `contract_to_hire`, distinct from `contract`) or `"unknown"`.
- **Location**: raw location, parsed city/state/country when the format
  supports it (e.g. "New York, NY"), `additional_locations`, remote
  type, and the raw work-arrangement text preserved verbatim (e.g.
  "Hybrid - Newark, NJ") — never a guessed metro-area/geographic
  relationship.
- **`required_skills` / `preferred_skills`** — explicitly separate
  lists, never collapsed into one (see "Required vs. preferred" below).
  Each `SkillRequirement` carries the AJI-009 canonical skill name,
  `evidence_text`, and `confidence`.
- **`required_experience` / `preferred_experience`** — years, an
  optional `area` (a canonical skill mentioned in the same clause) and
  `context` (e.g. "production", "leadership"), each with evidence. Only
  explicit "N years" patterns are captured; an unrelated number (a
  founding year, a team size) is never interpreted as experience.
- **`education`** / **`certifications`** — required/preferred degree or
  certification mentions with evidence; never inferred from what a
  company "usually" requires.
- **`responsibilities`** — always a separate list from every requirement
  list above (see "Responsibilities vs. requirements" below).
- **`authorization`** — sponsorship/citizenship/clearance/work-
  authorization signals, each one of the job's *observable* JD language,
  never a legal/immigration determination (this is job-side data;
  AJI-011's `Preference` fields are the user's own declared situation —
  the two are compared by `services.eligibility`, not by AJI-012).
- **`compensation`** — captured only when the `Job` row already has
  salary data; never fabricated.
- **`domain`** — AI-derived, with confidence and evidence.

### Required vs. preferred (never collapsed)

`deterministic.py` classifies every requirement clause independently
rather than doing one text-wide split. `iter_clauses_with_default_level`
clause-splits the *entire* text once and tracks a running section-level
default (flips from `required` to `preferred` only at a clause that
*is* a "Preferred Qualifications"/"Nice to Have"-style heading), then
`classify_level` checks each individual clause for an explicit inline
marker (`required`, `must`, `minimum`, ... vs. `preferred`, `nice to
have`, `bonus`, `plus`, ...), which always wins over the section
default.

This clause-first ordering matters: an earlier implementation ran
`services.job_matching.extractor.split_preferred_section` (a whole-text,
single-marker-position split) *before* clause-splitting, which cut a
sentence like *"Kubernetes experience is nice to have"* in two at the
marker's position — separating the skill from its own marker and
losing it entirely. Splitting into clauses first, then classifying each
clause independently, keeps an inline marker attached to the requirement
it modifies.

A skill/requirement classified as required anywhere in the JD is never
also listed as preferred (required always wins on conflict), and a
preferred marker never promotes a requirement to required.

### Responsibilities vs. requirements

`Job.responsibilities` (a separate column, populated by job discovery)
is scanned only for `ResponsibilityItem`s (`extract_responsibilities`);
`Job.description`/`Job.requirements` are scanned only for
skills/experience/education/certifications
(`requirement_text()` deliberately excludes `responsibilities`). A
responsibility is never automatically treated as a hard requirement —
the existing schema's own field separation makes this the natural,
minimal implementation rather than a new heuristic.

### AI safety: the evidence-substring check

The AI semantic decoding stage is deliberately narrow: it only decodes
`normalized_title`, `role_family`, `seniority` (when deterministic
extraction found nothing), and `domain` — every other field
(skills, experience, education, certifications, responsibilities,
authorization, compensation, location, employment) is always
deterministic, never re-decided by the AI.

`validator.py`'s `_evidence_supported()` is the concrete
anti-hallucination check: the AI is required to return a verbatim
evidence quote for every non-null field, and that quote must actually
appear (case/whitespace-insensitive substring match) in the raw JD text
before the field is trusted. An AI-claimed value whose evidence doesn't
match the source text is dropped (the field stays `null`) rather than
persisted — this is deliberately silent-and-safe, not a hard failure,
since one bad AI field must never discard an otherwise-valid snapshot.

### Snapshot/versioning and idempotency

`JobIntelligence` (`apps/api/models.py`) follows the same insert-only
versioning convention as `ResumeAIAnalysis` (see "Analysis/scoring
versioning convention" above): `analysis_version` / `analyzer_version` /
`prompt_version` / `model_provider` / `model_name`, since this is an
AI-derived artifact.

- **`content_fingerprint`** — a SHA-256 hash of every `Job` field that
  feeds extraction (title, description, requirements, responsibilities,
  location, country, remote/employment type, salary, contract fields),
  normalized (whitespace-collapsed, lowercased) before hashing. Computed
  by `service.compute_job_content_fingerprint()`.
- **`raw_jd_snapshot`** — a JSONB copy of those same fields at analysis
  time, independent of the live `Job` row, so a later job edit/
  rediscovery never silently changes what a historical snapshot says it
  analyzed.
- **Idempotency**: `generate_job_intelligence()` looks up an existing
  row keyed by `(job_id, content_fingerprint, analyzer_version,
  prompt_version)` before doing any extraction or AI call, exactly
  mirroring `analyze_resume_version()`'s cache lookup. Same job + same
  JD content + same pipeline version -> the existing row is returned,
  with zero re-parsing and zero AI calls. A changed JD (different
  fingerprint) or a bumped `ANALYZER_VERSION`/`PROMPT_VERSION` always
  produces a new, additional row — existing rows are never updated or
  overwritten.

### Partial extraction / failure handling

Deterministic extraction failing is a hard error: nothing is persisted
(`JobIntelligenceServiceError`, 503). A failed *AI* call (provider
error, timeout, invalid output) is different — it degrades to a
`extraction_status = "partial"` snapshot containing only the
deterministic fields (`identity.normalized_title`/`role_family`/`domain`
stay `null`), rather than discarding real, evidence-backed deterministic
data or corrupting the request. `extraction_status` is never anything
other than `"complete"` or `"partial"` — a fully failed extraction is
never persisted as if it were valid.

### Persistence and API

`JobIntelligence` is a single table (not over-normalized into one table
per requirement type) with typed top-level columns for the metadata
that needs indexing/filtering (`job_id`, `content_fingerprint`,
versions) and the full typed contract in one `structured_intelligence`
JSONB column — the same balance `ResumeAIAnalysis` and `JobMatchResult`
already strike.

- `GET /jobs/{job_id}/intelligence` — returns the newest snapshot only;
  never recomputes or calls the AI provider on a read (this is what
  keeps a jobs-list/detail view cheap at scale — see "Performance"
  below).
- `POST /jobs/{job_id}/intelligence` — computes-or-reuses (idempotent,
  per above).

Both require authentication like the rest of the per-job API surface,
but **Job Intelligence itself has no `user_id` column** — it is shared,
job-scoped data (see "Shared vs. personalized" immediately below), not
tied to the requesting user.

### Shared vs. personalized (do not mix these)

Job Intelligence is deliberately the same shared answer for every user
who looks at a given job — description, requirements, preferred
qualifications, responsibilities, skills, location, employment type,
salary, role, seniority, domain, and the job's own observable
authorization signals. It never stores or derives a
user-specific score: Hard Eligibility (AJI-011), Job Match (existing),
ATS Alignment (AJI-013), and Gap Analysis (AJI-015) all stay in their
own user-scoped tables/services and are never written into
`JobIntelligence.structured_intelligence`.

### Performance

`GET /jobs/{job_id}/intelligence` is a single indexed SELECT — no AI
call, no re-parsing. `POST` reuses the fingerprint-keyed cache described
above so viewing/recomputing the same unchanged job repeatedly costs one
AI call total, not one per request. AJI-012 intentionally does not
include a bulk/background discovery-time worker that pre-computes
Job Intelligence for every discovered job — that operationalization
work belongs to a later ticket, not this one.

### UNKNOWN/absence semantics

Every optional field's absence means exactly one thing: the JD did not
provide enough evidence, not "the job doesn't have this." `"unknown"` is
a first-class enum value (employment type, remote type, sponsorship,
citizenship, clearance, work authorization, compensation period) rather
than `null`, so a consumer can distinguish "we checked and it's not
disclosed" from a field that was never populated at all.

### Testing

`tests/test_job_intelligence_deterministic.py` unit-tests every
deterministic extractor with no database (identity/seniority,
employment, location, required-vs-preferred, skills, experience,
education, certifications, responsibilities-vs-requirements,
authorization, compensation). `tests/test_job_intelligence_contracts.py`
and `tests/test_job_intelligence_validator.py` cover the Pydantic
contract's own validation and the AI evidence-substring
anti-hallucination check. `tests/test_job_intelligence_provider.py`
mirrors `test_openai_provider.py`'s OpenAI-strict-schema regression
guard. `tests/test_job_intelligence_service.py` (mocked DB) and
`tests/test_job_intelligence_versioning.py` (real DB) cover
idempotency/versioning: same content reuses a snapshot, changed content
or a bumped analyzer version creates a new one without touching history,
and a failed AI call degrades to a partial snapshot rather than losing
the deterministic result. `tests/test_jobs_intelligence_api.py` covers
authentication, 404s, the shared-across-users behavior, and that no
personalized (eligibility/Job Match/ATS) field ever appears in the
response or the public `/jobs` listing.

## ATS Alignment (AJI-013)

ATS Alignment answers a different question from every other artifact in
the pipeline:

| | Question it answers |
|---|---|
| Hard Eligibility | "Can this job even be considered?" |
| Job Intelligence | "What does this job require?" |
| **ATS Alignment (this section)** | **"How well does this exact ResumeVersion demonstrate this exact JD's requirements?"** |
| Job Match (existing) | "How well does this job fit?" |

It is AJI's own estimate of how an ATS would read a resume against a
JD — never the employer's proprietary ATS score, never a prediction of
interview/hiring probability, and never merged into `JobMatchResult` or
`JobIntelligence` (see "Job Match vs. ATS Alignment" above, which this
section fulfills).

### Category taxonomy: two tiers, not three (a resolved conflict)

The AJI-013 product spec describes three requirement tiers (Must-Have /
Preferred / Nice-to-Have). The already-shipped AJI-012 `JobIntelligence`
contract only has two levels — `Level = Literal["required", "preferred"]`
(`apps/api/services/job_intelligence/contracts.py`) — and deliberately
folds "nice to have"/"bonus"/"a plus" phrasing into `preferred`
(`PREFERRED_MARKERS` in `deterministic.py`). This is a genuine conflict
between the AJI-013 spec and the already-approved AJI-012 data model, not
an oversight, and was resolved with the Project Owner during the AJI-013
build rather than silently choosing a side: **ATS Alignment reuses
AJI-012's two-tier taxonomy exactly** (`must_have` ==
AJI-012 `required`, `preferred` == AJI-012 `preferred`) rather than
forking a third tier on top of AJI-012's classification logic, which
would have meant either modifying AJI-012's shipped contract/tests or
re-implementing a slice of its clause classification inside AJI-013 (both
explicitly out of scope — "do not recreate the AJI-012 job-understanding
pipeline"). `services/ats_alignment/contracts.py::RequirementCategory`
therefore has exactly two values, not three.

### Package layout

- `services/ats_alignment/` — the pure, DB-free, AI-free engine, mirroring
  `services.job_matching`'s and `services.eligibility`'s DB/AI-free-core
  convention:
  - `contracts.py` — `JobRequirementItem` (input), `RequirementAlignment`
    (per-requirement output), `AtsAlignmentResult` (aggregate output).
  - `resume_adapter.py` — adapts an already-computed deterministic resume
    analysis (`apps.api.services.resume_ai.deterministic`, computed by the
    orchestration layer and passed in, never imported here) into a
    `ResumeEvidenceProfile`. Mirrors
    `services.job_matching.resume_adapter`'s existing convention exactly.
  - `engine.py` — `evaluate_ats_alignment()`: evaluates every requirement
    independently (skill/experience/education/certification) and
    aggregates a result. No database access, no AI call.
  - `scoring.py` — `compute_overall_score()`/`compute_overall_confidence()`,
    isolated behind small, independently-testable functions (see
    "Scoring: an explicit placeholder formula" below).
- `apps/api/services/ats_alignment_service.py` — the DB-touching
  orchestration layer (resume version resolution, Job Intelligence
  lookup/generation, idempotency, persistence), playing the same role
  `job_match_service.py` and `job_intelligence/service.py` play for their
  respective artifacts.

### Source data (reused, not recreated)

- **Job-side requirements** come entirely from AJI-012's persisted
  `JobIntelligence.structured_intelligence` (re-validated into
  `JobIntelligenceResult`), never from re-parsing raw JD text. If no
  snapshot exists yet for the job, `calculate_ats_alignment()` calls the
  same `generate_job_intelligence()` the `/jobs/{job_id}/intelligence`
  endpoint uses — idempotent/cached, so this never duplicates AJI-012's
  pipeline.
- **Resume-side evidence** comes from the existing deterministic resume
  analyzer (`apps.api.services.resume_ai.deterministic`, the same
  function `job_match_service.py` already reuses for Job Match) plus the
  user's declared `Profile.years_experience`. No second resume parser is
  introduced. Education and certification alignment are evaluated via a
  grounded keyword search directly against the resume's raw text — every
  `resume_evidence` string in a result is a literal substring of the
  resume, never an unverified claim.

### AI usage: v1 is entirely deterministic (a documented scope decision)

Unlike `ResumeAIAnalysis`/`JobIntelligence`, `AtsAlignmentResult` makes no
AI call of its own. The spec allows (but does not require) an AI
semantic-interpretation layer for ambiguous cases; this build does not
add one, because:

- Semantic-equivalence handling for skills (e.g. "GCP" ==
  "Google Cloud Platform") already happens once, upstream, in the shared
  canonical skill vocabulary (`services.skills`) both Job Intelligence and
  Resume Intelligence extraction already go through — exact-vs-synonym
  skill matching does not need its own AI call here.
- An AI call here would need the same evidence-substring
  anti-hallucination check AJI-012's `validator.py` already established
  ("a requirement must not be marked matched merely because the LLM
  believes the candidate probably has the capability" — spec section 7),
  which is exactly what the deterministic keyword-search approach
  guarantees for free, with zero risk of an unsupported resume fact.

This is a deliberate, minimal v1 scope decision, not an oversight — a
future ticket may layer AI semantic interpretation on top of this same
engine for genuinely ambiguous cases (e.g. a related-but-not-identical
skill) without changing its architecture.

### Matched / partial / missing

Every requirement gets an explicit, independently-evaluated result — see
`services/ats_alignment/engine.py`'s module docstring for the exact rule
per requirement type (skill/experience/education/certification). In
summary: `matched` requires direct or quantitatively-verified evidence;
`partial` requires *some* related evidence that doesn't fully satisfy the
requirement (skill listed only in a skills section, years below the
minimum, a lower degree than required, a certification whose name is only
partially present); `missing` means no such evidence exists in the
resume. No requirement is ever silently dropped from the result set.

### Scoring: an explicit placeholder formula (superseded by AJI-020)

The AJI-013 spec explicitly stated no Must-Have/Preferred weighting
formula had been approved yet, and instructed the Builder not to invent
one. `services/ats_alignment/scoring.py::compute_overall_score()`
therefore originally implemented the simplest defensible placeholder —
every requirement (regardless of category) counted equally — versioned
via `SCORING_VERSION = "placeholder-1.0"`, isolated behind one small
function specifically so the real, approved formula could replace its
body later without touching the engine, persistence, or API layers.

**This placeholder was replaced by the approved weighted formula in
AJI-020** (see that section below) — `compute_overall_score()` no longer
implements equal-weighting, and `SCORING_VERSION` is now
`"weighted-1.0"`. This subsection is kept for history (older
`AtsAlignmentResult` rows persisted under the placeholder formula are
never rewritten — see AJI-020's "Persistence and backward compatibility"
below).

### Persistence, versioning, and idempotency

`AtsAlignmentResult` (`apps/api/models.py`) is insert-only, like
`JobMatchResult`/`JobIntelligence`/`ResumeAIAnalysis` (see "Analysis/
scoring versioning convention" above). It is a purely deterministic
artifact (no AI call of its own), so it follows the single
`engine_version` convention `JobMatchResult` uses rather than the
analysis/analyzer/prompt/model split used by AI-derived artifacts.

Exact-input pinning: each row records `user_id`, `job_id`,
`resume_version_id`, `job_intelligence_id` (the exact `JobIntelligence`
snapshot used — not just the job), `job_content_fingerprint` (copied from
that snapshot so idempotency lookups don't require a join), and
`engine_version`. `calculate_ats_alignment()` looks up an existing row
keyed by all five before doing any work; a cache hit returns it
unchanged. A changed resume version, a new `JobIntelligence` snapshot (JD
edited, or the AJI-012 pipeline version bumped), or a bumped ATS
`engine_version` always produces a new, additional row — existing rows
are never overwritten, so a resume/JD edit never silently mutates a past
analysis.

### User isolation (personalized, unlike JobIntelligence)

Unlike `JobIntelligence` (shared, job-scoped, no `user_id`),
`AtsAlignmentResult` is personalized: the same job can be analyzed
against different resumes/users. Every read/write is always scoped to
the requesting user's own `user_id` (never derived from `job_id`/
`resume_version_id` alone) — `get_latest_ats_alignment()` filters on
`user_id` unconditionally, and `GET /jobs/{job_id}/ats` for a job another
user analyzed returns 404, not another user's data.

### API

- `GET /jobs/{job_id}/ats` — returns the authenticated user's newest
  result, never recomputing or calling the AI provider (Job Intelligence
  generation only ever happens from the POST path). Accepts an optional
  `resume_version_id` query parameter to pin the read to one exact
  version; omitted, it returns the newest result across any resume
  version for that user/job.
- `POST /jobs/{job_id}/ats` — computes-or-reuses (idempotent, per above).
  Accepts the same optional `resume_version_id` query parameter Job
  Match's `/jobs/{job_id}/match` already exposes, with the same default
  resume selection (most recent `Resume`, preferring its master
  `ResumeVersion`) when omitted — no new resume-selection UI/API is
  introduced (AJI-017 stays out of scope).

### Frontend

The Jobs list page (`apps/web/app/(app)/jobs/page.tsx`) already had an
"ATS Readiness — Not calculated" placeholder card next to the Job Match
card, and a dedicated `/ats` route with a "coming soon" empty state — the
existing architecture already required this surface (per the ticket's
"only if the existing architecture already requires an ATS analysis
surface" scoping rule). Both were wired to the real endpoints: the Jobs
list card now triggers `POST /jobs/{job_id}/ats` and renders the score,
confidence, and a per-requirement breakdown (grouped by must-have/
preferred, each showing status, explanation, and evidence) via a new
`AtsAlignmentPanel`. The standalone `/ats` page's copy was updated to
stop claiming the feature is unshipped and points to the Jobs page
instead of gaining its own job/resume-selection workflow (that belongs to
AJI-017, not this ticket).

### Testing

`tests/test_ats_alignment_engine.py` unit-tests the pure engine with no
database (skill exact/demonstrated/partial/missing, experience boundary
conditions, education degree-rank comparison including a higher-degree-
satisfies-lower-requirement case, certification partial matching,
evidence-grounding rules, and scoring boundary conditions).
`tests/test_ats_alignment_service.py` (real DB) covers idempotency/
versioning (same inputs reuse a row; a changed resume version, a new Job
Intelligence snapshot, or a bumped engine version each produce a new
row), resume version resolution/ownership, and error handling (job not
found, no resume, empty resume text, no analyzable requirements).
`tests/test_jobs_ats_api.py` covers authentication, 404s, user isolation
(another user can never read a result, and the same job scored for two
different resumes never leaks one user's resume content to the other),
idempotency over HTTP, and that the public `/jobs` listing never includes
ATS data.

## Job Match Reconciliation (AJI-014)

AJI-014 did not redesign Job Match or its scoring formula. It fixed one
specific pre-existing defect: `apps.api.services.job_match_service` built
its `JobRequirements` (must-have/preferred skills and experience) by
running its own text-splitting and skill extraction
(`services.job_matching.extractor.split_preferred_section`/
`build_job_requirements`) directly over raw
`Job.description`/`requirements`/`responsibilities` text — duplicating a
job-understanding pipeline that AJI-012 Job Intelligence already does
more thoroughly and correctly (clause-level required-vs-preferred
classification instead of one whole-text split point, and correctly
excluding `responsibilities` from requirements, since a responsibility is
never a hard requirement — see "Responsibilities vs. requirements"
above). This was exactly the kind of "already-approved-architecture
duplication" AJI-014 was scoped to find and fix, not a product-level
scoring change.

**What changed:** `calculate_job_match()` now reads job-side requirements
from the same persisted `JobIntelligence` snapshot AJI-013 already reuses
(via `get_latest_job_intelligence`/`generate_job_intelligence`), mapping
AJI-012's `required_skills`/`preferred_skills`/`required_experience`/
`preferred_experience` onto `services.job_matching.contracts.
JobRequirements` (`apps.api.services.job_match_service._build_job_requirements`,
a small, Job-Match-specific copy of the same mapping
`ats_alignment_service._build_job_requirements` already does — kept
separate rather than shared, since Job Match's `JobRequirements` shape
only carries skills/experience while ATS Alignment's flat requirement
list also covers education/certifications Job Match's scoring never
used). `services.job_matching.matcher`/`scorer` — the actual scoring
formula (must-have 35 / preferred 15 / experience 20 / role 15 /
location 10 / employment 5) — is completely unchanged.

**What did not change (an explicit non-decision, not an oversight):**
AJI-014 does **not** make ATS Alignment or Hard Eligibility inputs to the
Job Match score. This was already resolved by AJI-013's "Job Match vs.
ATS Alignment" section above (see also AJI-011's "Hard Eligibility vs.
Job Match vs. ATS Alignment" table): the three stay separate,
independently-computed artifacts, never merged into one score or one
table. No approved weighting formula for combining them exists anywhere
in this repository or ticket history, so none was invented here — per
the ticket's explicit instruction, this is called out rather than
silently decided. `JobMatchResult` gets no ATS/eligibility reference
column; the existing Jobs list UI (`apps/web/app/(app)/jobs/page.tsx`),
which already renders Hard Eligibility, Job Match, and ATS Alignment as
three clearly-labeled, independently-triggered panels for the same job,
remains how a user sees all three together.

**Idempotency:** `JobMatchResult` (`apps/api/models.py`) gained two
nullable columns — `job_intelligence_id` (FK to the exact
`JobIntelligence` snapshot used) and `job_content_fingerprint` (copied
from that snapshot, like `AtsAlignmentResult.job_content_fingerprint`, so
a lookup doesn't require a join) — via migration `2b9a1d6e4f3c`. Both are
`NULL` on rows persisted before AJI-014, which are never backfilled or
otherwise mutated. `calculate_job_match()` now looks up an existing row
keyed by `(user_id, job_id, resume_version_id, job_intelligence_id,
engine_version)` before doing any resume analysis or scoring — a cache
hit returns the existing row unchanged, exactly mirroring
`calculate_ats_alignment()`. A changed resume version, a new Job
Intelligence snapshot, or a bumped `services.job_matching.scorer.
ENGINE_VERSION` always produces a new, additional row. (Previously,
`calculate_job_match()` had no caching at all — every call inserted a new
row unconditionally; this is the first time Job Match participates in
the same idempotency convention every other AJI artifact already
follows.)

### Testing

`tests/test_job_match_intelligence_reconciliation.py` covers: a job's
required/preferred skills come from its `JobIntelligence` snapshot (not
from Job Match re-parsing `Job` text); a missing snapshot is generated
on demand; `Job.responsibilities`-only text is never treated as a
requirement; same-inputs idempotency (including that the row count
does not grow on repeated calls); a changed resume version, a new Job
Intelligence snapshot, or a bumped engine version each produce a new
row; and a Job Intelligence generation failure surfaces as a
`JobMatchServiceError`. All pre-existing Job Match tests
(`tests/test_jobs_match_api.py`, `tests/test_job_match_resume_version_selection.py`,
`tests/test_job_matching_*.py`) pass unchanged, since the pure scoring
engine and its 6-component/100-point weighting were not touched.

## Gap Analysis & Job-Specific Suggestions (AJI-015)

Gap Analysis answers a narrower question than every artifact before it:

| | Question it answers |
|---|---|
| Job Intelligence | "What does this job require?" |
| ATS Alignment | "How well does this exact resume demonstrate this exact JD?" |
| **Gap Analysis (this section)** | **"For each requirement this resume does not fully demonstrate, why is it a gap, and what could the candidate truthfully do about it?"** |
| Job Match (existing) | "How well does this job fit?" |

The originally-sketched roadmap (written during AJI-012's build, see that
section) called this "AJI-014 Gap Analysis" + "AJI-015 Suggestions" as two
separate tickets. By the time this work started, AJI-014 had already been
delivered as the Job Match/Job Intelligence reconciliation fix (see that
section above), so this single ticket — AJI-015 — covers both gap
analysis and job-specific suggestions together, since a suggestion has no
meaning independent of the gap it addresses.

### Canonical sources (reused, never reimplemented)

Gap Analysis introduces no new requirement extraction and no new
alignment scoring:

- **Which requirements are gaps, and why** comes entirely from an
  existing AJI-013 `AtsAlignmentResult` — the canonical requirement-
  alignment source. `apps/api/services/gap_analysis/engine.py::
  select_gap_candidates()` reads `requirement_results` from that row and
  keeps only the entries whose `status` is `partial` or `missing`; a
  `matched` requirement is not a gap. Every field on a gap candidate
  (`requirement_type`, `category`, `requirement_text`, `jd_evidence`,
  `resume_evidence`) is copied verbatim — nothing here re-runs ATS
  Alignment's skill/experience/education/certification evaluation, and
  the AJI-012/AJI-013 Must-Have/Preferred two-tier taxonomy is preserved
  as-is (`category` stays `must_have`/`preferred`, unchanged).
- **The Job Intelligence snapshot and Job Match score** are untouched.
  Gap Analysis never calls `services.job_matching` and never writes to
  `JobMatchResult` — see "Job Match vs. ATS Alignment" above, which this
  ticket does not revisit.
- If no `AtsAlignmentResult` exists yet for the requested (user, job,
  resume version),
  `apps/api/services/gap_analysis/service.py::generate_gap_analysis()`
  calls `apps.api.services.ats_alignment_service.calculate_ats_alignment()`
  directly — the same resume-version resolution (with ownership
  enforcement), Job Intelligence generation-if-missing, and idempotent
  caching `POST /jobs/{job_id}/ats` already uses. This is a direct
  function call, not a duplicated implementation: Gap Analysis never
  re-derives resume evidence or re-scores a requirement itself.

### AI usage: narrow, evidence-constrained, and never authoritative over safety

Unlike ATS Alignment (AJI-013, entirely deterministic), Gap Analysis does
use an AI stage — but only for two fields per gap: `explanation` (why
this is a gap, in plain language) and `suggestion_text` (what the
candidate could do about it). Everything else is deterministic:

- **`suggestion_type` is never AI-derived.**
  `apps/api/services/gap_analysis/engine.py::default_suggestion_type()`
  maps `status` to `suggestion_type` in code, not by prompting: a
  `missing` requirement (ATS Alignment's own engine guarantees zero
  resume evidence for this status) always gets `ADD_IF_TRUE`; a `partial`
  requirement (ATS Alignment guarantees *some* resume evidence for this
  status) always gets `REPHRASE_EXISTING`. This mapping is applied in
  `apps/api/services/gap_analysis/validator.py` regardless of what an AI
  response proposes — the concrete, mechanical implementation of "missing
  candidate evidence must produce an ADD_IF_TRUE-style recommendation
  rather than fabricated resume content." A unit test
  (`tests/test_gap_analysis_validator.py::
  test_suggestion_type_for_missing_is_always_add_if_true_even_if_ai_disagrees`)
  asserts this holds even when the AI's own suggestion text reads as if
  the candidate already has the skill.
- **Evidence-substring grounding**, mirroring AJI-012's
  `_evidence_supported()` anti-hallucination check exactly in shape but
  narrower in scope: the AI must return a verbatim `explanation_evidence`
  quote, and it is checked as a case/whitespace-insensitive substring of
  *that one gap's own* `jd_evidence` + `resume_evidence` — never the full
  raw JD or resume text. This keeps the AI's grounding scoped to the
  single requirement it was asked about. An unsupported quote drops both
  the AI `explanation` and `suggestion_text` for that gap; the
  deterministic template (`engine.py::deterministic_explanation()` /
  `deterministic_suggestion_text()`) is used instead — the same
  silent-and-safe degrade pattern AJI-012 established.
- **A second, ADD_IF_TRUE-specific safety net**: even when the evidence
  check passes, an `ADD_IF_TRUE` gap's AI-authored `suggestion_text` is
  only accepted if it contains an explicit hedging/conditional phrase
  (`validator.py::_HEDGE_PHRASES` — "if you have", "if accurate", "if
  applicable", etc.). A flat assertion ("Add your Kubernetes experience
  to the resume") is rejected and replaced with the deterministic
  template even though it passed evidence grounding, since an
  `ADD_IF_TRUE` gap by definition has no resume evidence to assert
  anything from.
- `explanation_source` / `suggestion_source` (`"ai"` or
  `"deterministic"`) are persisted on every gap, so which fields actually
  came from the AI vs. the safe fallback is never hidden in the stored
  result.
- A fully failed AI call (provider error, timeout, no API key) degrades
  every gap to the deterministic template and persists
  `generation_status = "partial"` — mirroring `JobIntelligence.
  extraction_status`. A job with zero gaps needs no AI call at all and is
  `generation_status = "complete"` (there is nothing to enrich, not a
  degraded result).

### Package layout

`apps/api/services/gap_analysis/` mirrors `job_intelligence`'s colocated
layout (DB-free deterministic + AI pipeline modules colocated with DB
orchestration), not `ats_alignment`'s top-level `services/` layout —
because, like Job/Resume Intelligence and unlike ATS Alignment, this
pipeline has an AI stage of its own:

- `contracts.py` — the `GapSuggestion` / `GapAnalysisResult` Pydantic
  contract.
- `engine.py` — pure, DB-free, AI-free: `select_gap_candidates()`,
  `default_suggestion_type()`, and the deterministic explanation/
  suggestion templates.
- `prompts.py` / `providers/openai_provider.py` / `providers/factory.py`
  / `interpreter.py` — the AI enrichment stage, structured exactly like
  `job_intelligence`'s equivalent modules (OpenAI Structured Outputs via
  `client.responses.parse`, a closed `extra="forbid"` schema per
  provider-schema convention).
- `validator.py` — merges deterministic gap candidates with (optional)
  validated AI enrichment into the final contract; the concrete
  anti-hallucination and suggestion-type-enforcement logic (see "AI
  usage" above).
- `service.py` — the DB-touching orchestration layer (calling
  `calculate_ats_alignment()`, idempotency, persistence), the same role
  `job_intelligence/service.py` plays for Job Intelligence.

### Persistence, versioning, and idempotency

`GapAnalysis` (`apps/api/models.py`) is insert-only, like every other
AI/scoring artifact (see "Analysis/scoring versioning convention"
above). It is AI-derived (deterministic gap selection feeds an
evidence-constrained AI enrichment stage), so it follows the
analysis/analyzer/prompt + `model_provider`/`model_name` convention, like
`JobIntelligence`, rather than ATS Alignment's single `engine_version`.

Exact-input pinning: each row records `user_id`, `job_id`,
`resume_version_id`, `job_intelligence_id`, and `ats_alignment_id` — the
exact AJI-013 `AtsAlignmentResult` every gap was derived from, and the
concrete "tied to the specific Resume Version and Job Intelligence
snapshot" requirement, since `AtsAlignmentResult` itself already pins
both. `job_content_fingerprint` is copied from that result so idempotency
lookups don't require a join, mirroring `AtsAlignmentResult.
job_content_fingerprint`'s own convention.
`generate_gap_analysis()` looks up an existing row keyed by `(user_id,
job_id, ats_alignment_id, analyzer_version, prompt_version)` before doing
any AI call — a cache hit returns the existing row unchanged. Because
`AtsAlignmentResult` is itself immutable, a changed resume version or a
new/edited JD always produces a new `AtsAlignmentResult` first (never a
mutation), which in turn always produces a new, additional `GapAnalysis`
row; existing rows are never overwritten.

### User isolation

Like `AtsAlignmentResult` (unlike the shared, job-scoped
`JobIntelligence`), `GapAnalysis` is personalized: the same job can be
analyzed against different resumes/users. `get_latest_gap_analysis()`
filters on `user_id` unconditionally, and `GET /jobs/{job_id}/gap-analysis`
for a job another user analyzed returns 404, not another user's data —
including another user's resume content, since a gap's `resume_evidence`
is always that exact user's own text.

### API

- `GET /jobs/{job_id}/gap-analysis` — returns the authenticated user's
  newest result, never recomputing, never calling
  `calculate_ats_alignment()`, and never calling an AI provider (AI calls
  only ever happen from the POST path). Accepts the same optional
  `resume_version_id` query parameter ATS Alignment exposes.
- `POST /jobs/{job_id}/gap-analysis` — computes-or-reuses (idempotent,
  per above), delegating resume-version resolution and ATS Alignment
  computation to `calculate_ats_alignment()` exactly as `POST
  /jobs/{job_id}/ats` does.

### Scope

Per the AJI-015 ticket's explicit scope boundary, this ticket does not
implement resume rewriting, automatic resume editing, priority ranking
across gaps or jobs, or any change to Job Match scoring, ATS Alignment
scoring, or the Must-Have/Preferred taxonomy — all of those remain
out of scope for a future ticket.

### Testing

`tests/test_gap_analysis_engine.py` unit-tests the pure engine with no
database (gap selection excludes `matched` requirements, the
status->suggestion_type mapping, deterministic template content).
`tests/test_gap_analysis_contracts.py` covers the Pydantic contract's own
validation. `tests/test_gap_analysis_validator.py` is the dedicated AI-
safety suite: `suggestion_type` is never taken from the AI even when it
disagrees, unsupported AI evidence is rejected, the evidence check is
case/whitespace-insensitive, an `ADD_IF_TRUE` suggestion without hedging
language is rejected even with valid evidence, and a fully failed AI call
still produces a complete, safe result. `tests/test_gap_analysis_provider.py`
mirrors `test_job_intelligence_provider.py`'s OpenAI-strict-schema
regression guard. `tests/test_gap_analysis_service.py` (real DB) covers
idempotency/versioning (same inputs reuse a row and make exactly one AI
call; a changed resume version, a new ATS Alignment result, or a bumped
analyzer version each produce a new row; a prior row's stored result is
never mutated by a later regeneration) and ATS Alignment error
propagation (job not found, no resume, another user's resume version
rejected). `tests/test_jobs_gap_analysis_api.py` covers authentication,
404s, that GET never invokes the AI provider, user isolation (including
that another user's resume content never leaks through a gap's
`resume_evidence`), idempotency over HTTP, that the public `/jobs`
listing never includes Gap Analysis data, and that `GET /jobs/{job_id}/ats`
continues to work unchanged alongside Gap Analysis. All pre-existing ATS
Alignment, Job Intelligence, and Job Match tests pass unchanged, since
none of their engines, schemas, or scoring were touched.

## Job Discovery operationalization

Job Discovery (`services/job_discovery`, AJI-006) existed and was fully
unit-tested from its original ticket, but nothing in the running
application ever invoked `run_discovery_pipeline` - the only documented
path was a manual Python snippet in `services/job_discovery/README.md`.
This section records what closed that gap and why, without changing the
pipeline itself (source adapter -> normalize -> validate -> deduplicate ->
persist is unchanged).

**What was added:** `apps/api/services/job_discovery_service.py` (the
DB-touching orchestration layer, mirroring every other `*_service.py` in
this codebase) and `POST /internal/job-discovery/run`
(`apps/api/routers/job_discovery.py`). See
`services/job_discovery/README.md`'s "Operationalizing discovery" section
for the full configuration and trigger-mechanism writeup.

**Why an HTTP trigger, not a background worker/task queue:** the current
deployment has no existing worker/queue infrastructure, and discovery for
one board is a single, fast, synchronous HTTP call. Introducing
Celery/RQ/Redis/Kafka now would add real operational surface (a broker,
worker processes, retry/dead-letter handling) for a job that does not yet
need any of that - there is exactly one source adapter and no requirement
for concurrent multi-board fetches, retries-with-backoff, or horizontal
worker scaling. An authenticated endpoint plus an external scheduler
(cron, the hosting platform's scheduled-task feature) gets "runs on a
schedule without a developer manually invoking Python" with zero new
infrastructure. Revisit this decision when there is more than one board
to ingest, or when a fetch failure needs automatic retry-with-backoff
rather than waiting for the next scheduled run.

**Why unconfigured by default:** which real company's Greenhouse board to
ingest is a product/legal decision (whose public postings AJI has
permission to aggregate) - not the Builder's to make by picking a company
and hardcoding it into shared config. `JOB_DISCOVERY_GREENHOUSE_BOARD_TOKEN`
/ `JOB_DISCOVERY_GREENHOUSE_COMPANY_NAME` are unset by default; the
endpoint hard-503s until an operator sets them (and the trigger token).

**Why a shared-secret header, not a user JWT:** this is a system-to-system
action (a scheduler calling the API), not a per-user one, and `User` has
no admin/role concept to gate it with. Do not add an `is_admin` flag to
`User` just to protect this one endpoint - if a real admin-role need
emerges later across multiple features, that is its own ticket.

## Application Tracking (the final workflow stage)

Application Tracking was the last stage of the approved core workflow
with no implementation - only the unused, reserved `SavedJob` model (see
"Legacy models removed" above: it was kept specifically for this) and a
"coming soon" frontend stub. Building it required a product decision this
document could not answer on its own (there was no existing spec, ticket,
or Figma review for it): the Product Owner chose the **full pipeline**
option - `saved -> applied -> interviewing -> offer -> rejected ->
withdrawn`, with a persisted status history and an Application Detail
view - over a minimal saved/applied binary or deferring the feature
entirely.

**Model:** `SavedJob` (`apps/api/models.py`) is the single row that
carries one (user, job) pair through the pipeline - `status`,
`applied_at` (set the first time status becomes `"applied"`, never
overwritten by a later status change), `created_at`/`updated_at`. A new
unique constraint on `(user_id, job_id)` is the hard guarantee behind
"saving a job is idempotent, never a duplicate row" -
`create_application()` returns the existing row unchanged on a repeat
save rather than erroring. `ApplicationStatusEvent` is a new, separate
append-only table (one row per status transition, including the initial
`"saved"` one) so the Application Detail view has a real timeline instead
of only ever showing the current status; it is never updated or deleted,
matching every other insert-only history table in this codebase.

**Why extend `SavedJob` rather than add a separate `Application` table:**
the model's own field (`status`, defaulting to `"saved"`) already
signaled this was the intended design - a job is "saved" and then
progresses through the same row's status, not two parallel concepts. A
second table would have duplicated the (user, job) identity and ownership
checks for no benefit.

**API** (`apps/api/routers/applications.py`, all authenticated,
ownership-scoped exactly like every other per-user resource in this
codebase - a 404, never another user's data, for anything not owned):
`POST /applications` (idempotent save), `GET /applications` (the current
user's list), `GET /applications/{id}` (detail + status history),
`PATCH /applications/{id}` (status update, Pydantic-`Literal`-validated
against the six statuses). No `DELETE` - not asked for by the approved
scope, and removing tracking history was never part of the spec decision.

**NERO never auto-applies:** every status transition is a user action
recording something that happened outside NERO (they applied elsewhere,
heard back, etc.) - there is no code path that submits an application on
a user's behalf, and the Application Detail UI says so explicitly next to
the status control.

**Dashboard integration:** `GET /dashboard`'s `applications` field is now
real (`apps/api/services/application_service.py::count_active_applications`)
instead of the previous fixed `{"available": false, "active_count": 0}`.
"Active" is deliberately `applied`/`interviewing`/`offer` only - a
merely-saved-but-not-yet-applied job is not yet a pursued application, and
a terminal `rejected`/`withdrawn` outcome is no longer active. This mirrors
the "honest empty/pending state, never fabricated" rule the rest of the
Dashboard already follows (see the Dashboard docstring in
`apps/api/routers/dashboard.py`).

## Provider Scorecard Workflow (AJI-018)

Job Discovery (above) has exactly one production source adapter
(Greenhouse). Before building a second one, the approved workflow is:

```
Provider -> Same NERO search scenarios -> Raw results -> Normalize ->
Deduplicate -> Measure -> Provider Scorecard -> Product Owner decision ->
Implementation
```

`services/provider_scorecard/` (see its own README for the full writeup)
implements everything left of "Product Owner decision" - a pure, DB-free
evaluation harness that runs an identical, shared list of
`SearchScenario`s against one or more candidate providers and produces a
`ProviderScorecard` of objective, descriptive metrics per provider. It
answers "how does this candidate's raw data compare once it goes through
the same normalize/deduplicate steps real discovery would apply?", not
"which provider should we build." No field on `ProviderScorecard` ranks
or recommends a provider - that judgment call, and everything right of it
in the diagram (approving a provider, then building its
`JobSourceAdapter`), stays a human/future-ticket step, the same way
AJI-013 declined to invent an unapproved Must-Have/Preferred weighting
formula (see "Scoring: an explicit placeholder formula" above) rather
than silently encoding a product decision nobody had made yet.

**Reuse, not a parallel pipeline:** normalization
(`services/provider_scorecard/normalize.py`) applies
`services.job_discovery.normalizer`'s existing field rules verbatim;
deduplication reuses `services.job_discovery.deduplicator.build_job_fingerprint`
unchanged; and the validation pass rate reuses
`services.job_discovery.validator.validate_discovered_job`. This is the
same "no source-specific/eval-specific logic belongs outside the shared
primitives" rule the Job Discovery README already states for a second
`JobSourceAdapter` - a provider's raw data is expected to look like Job
Discovery source-adapter output *before* normalization (an adapter here
implements `ProviderSearchAdapter.search(scenario) -> list[DiscoveredJob]`,
mirroring `JobSourceAdapter.fetch_jobs()`), so evaluating it exercises the
exact rules production discovery would apply, not a second set invented
for this workflow. Unlike the real discovery pipeline, an invalid job is
never dropped here (there is nothing to persist) - it is counted, since
the point of this stage is measuring a provider's data quality, not
filtering a result set.

**The scenario list is a product decision, left unset by default** - the
same posture Job Discovery already takes with which Greenhouse board to
ingest (see "Why unconfigured by default" above). `services/provider_scorecard/scenarios.py::EXAMPLE_SCENARIOS`
exists only so the pipeline is runnable/testable before a
Product-Owner-approved scenario list exists; it is explicitly documented
as illustrative, not canonical. Whatever list is actually used, every
candidate provider must be run against the identical list -
`compare_providers()` takes one shared `scenarios` argument for exactly
this reason, since "Same NERO search scenarios" is what makes the
resulting scorecards comparable at all.

**No DB persistence, no HTTP endpoint (a documented scope decision,
contrasted with Job Discovery's own operationalization above):** this is
an occasional decision-support tool run by whoever is evaluating a new
candidate provider, not a production data path a user or a schedule ever
touches - Job Discovery needed a persisted, schedulable, authenticated
endpoint because it ingests jobs a user will actually see; a provider
comparison has no such consumer. Adding a table/endpoint/auth here would
be infrastructure this workflow does not need yet - revisit only if a
concrete future need emerges to track scorecards over time or expose them
outside engineering, and treat that as its own ticket rather than folding
it into this one.

### Evaluation-only adapters for real candidates (not yet run)

`services/provider_scorecard/eval_adapters/` (Adzuna, Jooble, USAJOBS, The
Muse) and `services/provider_scorecard/run_eval.py` exist so a real
comparison can be run - see the package README's "Evaluating real
candidate providers" section for required credentials per provider and
each adapter's documented data-quality gaps. These are explicitly **not**
production `services.job_discovery.sources` adapters. They have not been
executed against live data: the session they were authored in has an
egress policy that denies all four hosts outright, and none of the three
that require an API key had one configured - this is a stated fact about
what has and hasn't happened, not a scorecard result to act on. Run
`run_eval.py` in an environment with network access to those hosts and
the real credentials to get an actual comparison.

### AJI-018C: offline ingestion for the Product Owner comparison table

A follow-up ticket asked for the actual comparison table (Greenhouse +
the four candidates) as evidence for a Product Owner provider-selection
decision. Confirmed at the time: this session's egress policy denies all
**five** hosts outright, including `boards-api.greenhouse.io` - not only
the four candidates - so no path in this repository could populate the
table by calling any of these APIs directly.

`services/provider_scorecard/report.py` (`ProviderReport`,
`build_provider_report`, `render_markdown_table`) and
`services/provider_scorecard/ingest.py` close that gap without ever
opening network access from this environment: `ingest.py` takes raw API
responses fetched by someone who *does* have real access (their own
machine, a CI runner with an open policy) and runs them through the same
normalize/deduplicate/validate primitives every other part of this
workflow already uses, adding `report_metrics.py`'s AI/ML keyword
heuristic, FT/Contract/Remote counts, salary/application-URL rates, and
posting-freshness/API-reliability metrics the table asked for. Every
`eval_adapters/*.py` module gained a `parse_response()` method (split out
of `search()`, same behavior, covered by the pre-existing adapter tests
unchanged) so ingestion reuses the exact same field-mapping logic a live
call would use rather than a second, ingestion-only implementation.

Global deduplication for this table is deliberately across every
scenario for a provider, not per scenario (unlike `ScenarioMeasurement`,
which is per-scenario) - the same posting surfacing under two scenario
searches must count once in "Unique jobs," not twice. A scenario that was
attempted and failed is recorded as `{"_error": "..."}` in the input
bundle rather than omitted, which is what makes "API reliability" a real
measurement instead of unconditionally reading 100%. `ProviderReport` has
no score/rank/winner field, per the ticket's explicit "no automatic score
or winner" requirement - the rendered table is numbers only, and the
Product Owner/Planner decision stays a separate, human step exactly like
every other placeholder-vs-decision boundary in this document (see
"Scoring: an explicit placeholder formula" above).

### Testing

`tests/test_provider_scorecard_contracts.py` covers `ProviderScorecard`'s
weighted-average aggregation (weighted by `fetched_count`, and that a
failed scenario is excluded from the average rather than counted as a
zero). `tests/test_provider_scorecard_metrics.py` covers field-completeness
counting (blank strings and `None` both count as missing) and the shared
rate helper. `tests/test_provider_scorecard_pipeline.py` covers the full
raw-results -> normalize -> deduplicate -> measure flow with a fake
in-memory adapter: duplicate counting by fingerprint, that normalization
actually runs before validation/completeness are measured (un-normalized
input like `"Fully Remote"`/`"full time"` still passes), that an invalid
job is counted rather than dropped, that an adapter exception degrades to
a failed measurement instead of raising and aborting the whole provider
comparison, and that `compare_providers()` runs the identical scenario
list against every adapter. `tests/test_provider_scorecard_us_location.py`
and `tests/test_provider_scorecard_eval_adapters.py` cover the four
evaluation-only adapters against canned fixture payloads (not live calls,
per the section above): each adapter's `from_env()` skip/build behavior,
field mapping into `DiscoveredJob`, the country heuristic's word-boundary
fix (a Muse location like `"Flexible / Remote"` no longer false-positives
on the `"FL"` marker the way a raw-substring version would), and that The
Muse's adapter never sends `scenario.keywords` as a query parameter (its
public API has nothing to map it onto).

`tests/test_provider_scorecard_report_metrics.py` covers the AJI-018C
AI/ML keyword heuristic, employment/remote-type counting against
normalized values, salary/application-URL presence, and freshness
(including that it returns `None` rather than a fabricated `0` when no
job discloses a posting date, and that mixed aware/naive datetimes from
different providers don't raise).
`tests/test_provider_scorecard_report.py` covers `build_provider_report()`'s
global (cross-scenario) deduplication, that validity reuses the shared
validator, that reliability accounts for recorded error scenarios (and is
`None` rather than a misleading `0%`/`100%` when nothing was attempted),
and that the rendered table has one column per provider, every requested
row, and no score/rank/winner language anywhere in it.
`tests/test_provider_scorecard_ingest.py` covers parsing a multi-provider
response bundle (including that Greenhouse's entry requires
`meta.greenhouse_company_name` and raises without it, since Greenhouse's
own API response carries no company name), that an absent provider is
left out of the report list rather than shown as zeroes, and the CLI
entry point end to end via a temp file.

## ATS Real Scoring Engine (AJI-020)

AJI-013 shipped ATS Alignment's per-requirement evidence engine
(matched/partial/missing verdicts for skill/experience/education/
certification requirements) with an explicitly-documented placeholder
score aggregation — every requirement counted equally, pending an
approved weighting formula (see "Scoring: an explicit placeholder
formula" above). AJI-020 delivers that approved formula. It does not
touch requirement-level evidence evaluation
(`services/ats_alignment/engine.py`'s `_evaluate_skill`/
`_evaluate_experience`/`_evaluate_education`/`_evaluate_certification`),
Job Match, Gap Analysis, or Job Intelligence — only how the per-
requirement verdicts already produced are aggregated into
`AtsAlignmentResult.overall_score`.

### Architecture: AI understands, deterministic engine scores

The pipeline this ticket implements against is unchanged: an AI stage
(AJI-012 Job Intelligence) turns unstructured JD text into structured,
evidence-backed requirements; a wholly deterministic stage (AJI-013's
engine, now AJI-020's scoring) turns those requirements plus a
deterministically-parsed resume into a score. AJI-020 adds no AI call of
its own — the four weighted components below are pure functions of
already-extracted, already-evidence-checked data (per-requirement
statuses, canonical skill lists, resume structural signals), consistent
with AJI-013's "AI usage: v1 is entirely deterministic" decision, which
this ticket does not revisit.

### The four weighted components

`services/ats_alignment/weights.py::SCORE_WEIGHTS` is the single,
centralized source of truth for the approved baseline weights (deliberately
isolated from `scoring.py` itself so a future re-weighting touches exactly
one module, mirroring how `services/job_matching/scorer.py` keeps its own
component `max_score` values as the one place Job Match's weighting
lives):

| Component | Weight | What it measures |
|---|---|---|
| Requirement Coverage | 40% | Breadth: the share of *every* extracted requirement (must-have and preferred; skill/experience/education/certification) the resume matches or partially matches. The direct successor to AJI-013's placeholder formula, now scoped to one of four dimensions instead of standing in for the whole score. |
| Keyword & Terminology Alignment | 25% | A raw, presence-only keyword-scan signal: what fraction of the JD's required/preferred skill vocabulary appears anywhere in the resume's own canonical skill list. Deliberately boolean (present/absent), not a mention count, and deliberately a different signal from Requirement Coverage's structural matched/partial/missing verdicts — it models the literal keyword-matching behavior real ATS parsers are known for. |
| Resume Evidence & Experience | 25% | Depth: for skill and experience requirements specifically (not education/certification, which have no "demonstrated vs. skills-only" distinction), how strongly the resume demonstrates them — reusing the engine's existing `matched` (demonstrated professional/project usage, or years at/above the minimum) vs. `partial` (skills-section-only mention, or years below the minimum) verdicts rather than re-deriving evidence strength. |
| Structure & Parseability | 10% | A fixed, five-check, presence-only checklist of whether a resume is legible to an ATS parser at all: contact info present, an Experience section heading detected, a Skills section heading detected, bullet-point formatting used, and no detected heading-style inconsistency. Every check is a boolean derived from AJI-010's existing `analyze_resume_deterministically()` output (sections/emails/phones/bullets/structural findings) — no second resume-structure parser was introduced. |

`services/ats_alignment/scoring.py::compute_overall_score()` computes all
four components unconditionally (a component with nothing to check, e.g.
no skill keywords in the JD, returns full credit rather than penalizing —
the same "no requirements -> full credit" convention
`services/job_matching/scorer.py` already uses) and sums
`weight * component.score` into a weighted total before the guardrail
below is applied.

### Exact/normalized/acronym/semantic matching (reused, not reinvented)

Keyword & Terminology Alignment's "exact, normalized, acronym, and
semantic matching, without conflating related-but-different technologies"
requirement is satisfied entirely by the canonical skill vocabulary
`services.skills` already established (AJI-009) and that both Job
Intelligence extraction and Resume Intelligence extraction already
resolve every skill mention through before AJI-020 ever sees them:
`"python3"`/`"python 3"` -> `python` (normalized), `"k8s"` -> `kubernetes`
(acronym), `"Google Cloud Platform"`/`"GCP"` -> `gcp` (semantic alias) all
resolve to one canonical identity upstream, while curating each canonical
skill's alias set individually is exactly what keeps a related-but-
different technology (e.g. `python` vs. `pytorch`) from ever being
silently conflated — `services/skills/canonical.py`'s own design note
("Unknown skills are normalized conservatively... rather than being
mapped to a potentially incorrect known skill") already states this
principle. AJI-020 therefore does not add a second, parallel matching
implementation; `compute_keyword_alignment()` is a thin presence-overlap
check over identifiers both sides already canonicalized.

### The required-requirement guardrail (a ceiling, not an invented penalty)

The AJI-020 ticket explicitly disallows inventing an arbitrary scoring
penalty for missing must-have requirements. Rather than subtracting a
made-up point value, `compute_must_have_ceiling()` computes a
mathematical ceiling: **the overall score can never exceed the resume's
own must-have coverage percentage** (the same `matched=1.0`/`partial=0.5`/
`missing=0.0` point scale Requirement Coverage already uses, scoped to
must-have requirements only). A resume missing a required skill cannot
score highly overall merely because its keywords, evidence, or resume
formatting look good elsewhere. This mirrors the precedent already
established for Hard Eligibility vs. Job Match/ATS Alignment above ("a
high ATS/Job Match score must never override a hard eligibility
constraint") — applied here *within* the ATS score itself as a ceiling
rather than a separate pass/fail gate, since ATS Alignment (unlike Hard
Eligibility) always produces a graded score. When a job has no must-have
requirements at all, `must_have_ceiling` is `None` and no ceiling is
applied — there is nothing to gate on.

### Resume-length neutrality

Every one of the four components is presence/ratio-based, never a
function of word count, mention count, or page count:
Requirement Coverage and Resume Evidence & Experience use boolean
per-requirement statuses; Keyword & Terminology Alignment uses set
membership, not mention frequency; Structure & Parseability uses boolean
section/contact/bullet presence. `tests/test_ats_scoring_engine.py`
asserts this directly — an identical resume padded with several times its
own content (repeated bullets, or the entire document duplicated) scores
identically to the unpadded version, both at the component level and the
full `evaluate_ats_alignment()` level.

### Persistence and backward compatibility

No schema/migration change was needed: `AtsAlignmentResult.result`
(`apps/api/models.py`) was already a flexible JSONB column, so the new
`score_components` (the four `ScoreComponent` breakdowns) and
`must_have_ceiling` keys are simply additional entries in that same
column, alongside the pre-existing `requirement_results`/
`must_have_total`/etc. keys.

`services/ats_alignment/engine.py::ENGINE_VERSION` was bumped
(`"1.0.0"` -> `"2.0.0"`) because the scoring formula changed in a way
that produces a different result for the same input — per the
"Analysis/scoring versioning convention" above, this guarantees every
`AtsAlignmentResult` persisted under the old placeholder formula is left
untouched (insert-only, never rewritten), and that rechecking any job
always computes a fresh row under the new formula rather than reusing a
placeholder-scored cache hit (`apps/api/services/ats_alignment_service.py`'s
idempotency lookup is keyed on `engine_version`). Reading an old,
placeholder-scored row back through `GET /jobs/{job_id}/ats` still works —
`_ats_alignment_to_response()` uses `.get("score_components", [])` and
`.get("must_have_ceiling")` specifically so a historical row missing
those keys degrades to an empty breakdown instead of a `KeyError`, rather
than being silently migrated or discarded.

### API and frontend

`GET`/`POST /jobs/{job_id}/ats` (unchanged routes) now include
`score_components` (the four-entry breakdown, each with `name`, `weight`,
`score`, `weighted_score`, `explanation`) and `must_have_ceiling` in their
response body. The Jobs list page's existing `AtsAlignmentPanel`
(`apps/web/app/(app)/jobs/page.tsx`, already present since AJI-013) gained
a small four-tile breakdown row rendering these percentages next to the
existing must-have/preferred requirement list — no new route, page, or
workflow was introduced.

### Known limitations / explicit non-decisions

- **Structure & Parseability's five checks are a Builder-level, defensible
  implementation of the concept**, not a Planner-approved enumeration —
  the AJI-020 spec names the 10% weight for this dimension but does not
  specify which exact structural signals to check. The checklist was
  built entirely from AJI-010's existing, already-tested extraction
  (sections/contact/bullets/structural findings) rather than inventing new
  resume parsing, and each of the five checks is weighted equally (no
  invented sub-weighting between them). Revisit if the Planner specifies a
  different or more granular checklist.
- **The "24 evaluation scenarios" referenced by the AJI-020 task
  description were not found anywhere in this repository** (no ticket
  file, spec document, or prior ARCHITECTURE.md section enumerates them).
  `tests/test_ats_scoring_engine.py` and the additions to
  `tests/test_ats_alignment_service.py`/`tests/test_jobs_ats_api.py`
  instead implement comprehensive scenario coverage against this
  document's own stated requirements (each weighted component in
  isolation, exact/normalized/acronym/semantic keyword matching,
  related-but-different-skill non-conflation, the must-have guardrail,
  score bounds, determinism, resume-length neutrality, historical
  preservation, job isolation, and resume-version isolation) rather than
  a specific numbered list. If an authoritative 24-scenario document
  exists outside this repository, it should be reconciled against this
  test suite in a follow-up.

## Requirement Intelligence Model (AJI-020A)

Requirement Intelligence is a finer-grained **model of a JD's
requirement language** — not a replacement for, and not merged with,
AJI-012 `JobIntelligence`. AJI-012 already answers "what does this
specific job require?" for AJI-013 (ATS Alignment), AJI-014 (Job Match
Reconciliation), and AJI-015 (Gap Analysis); this ticket does not change
any of that pipeline, and AJI-013 still deliberately reuses AJI-012's
two-tier (required/preferred) taxonomy rather than forking a third (see
the AJI-013 section above). Requirement Intelligence exists to model
what that two-tier shape does not attempt: a four-tier importance
taxonomy (required/preferred/contextual/informational), explicit
hard-requirement/gating semantics, AND/OR/MIN_COUNT/EQUIVALENT
relationships between requirements, character-offset provenance,
per-item ambiguity, and JD-level quality/security diagnostics
(duplicate detection, contradiction detection, prompt-injection
signals). Per the ticket's explicit scope boundary, it does not score,
arbitrate evidence, match against a resume, compute gaps, or generate
suggestions — those remain out of scope here.

### Package layout and why it has no database table (yet)

`apps/api/services/requirement_intelligence/` mirrors `job_intelligence`'s
colocated deterministic + AI pipeline module layout (`contracts.py`,
`deterministic.py`, `prompts.py`/`providers/`/`interpreter.py`,
`validator.py`), with one deliberate difference: **it has no ORM model,
no Alembic migration, and no API router.** AJI-020A's scope is the
requirement model and its extraction pipeline, not a new persisted/
queryable entity — `service.py`'s `build_requirement_intelligence()` is a
pure function (`RawRequirementSource` in, a validated
`RequirementIntelligenceResult` out) with no DB session dependency.
Every result still carries `analysis_version`/`analyzer_version`/
`prompt_version`/`model_provider`/`model_name` (see "The contract"
below), so a future persistence/API layer (AJI-020B, if/when a real
consumer needs one) has everything it needs to key and version snapshots
exactly the way `JobIntelligence` does, without this ticket guessing at
a schema for a consumer that does not exist yet.

### The contract

`RequirementIntelligenceResult` (`contracts.py`) is a single closed
Pydantic schema (`extra="forbid"` on every nested model), so a malformed
deterministic/AI merge is a validation error, never a silently-accepted
extra field:

- **`requirements`** — a flat, typed list of `RequirementItem`s
  (`requirement_type`: skill/experience/education/certification/
  responsibility). Each carries `importance` (the four-tier taxonomy),
  `hard_requirement` (a model-validated invariant: only ever true when
  `importance == "required"`), `canonical_terms`, a `source_span`
  (verbatim provenance into the exact raw text the pipeline was given,
  itself validated to actually bound its own `text`), `confidence`, and
  `ambiguous`/`ambiguity_reason`. A responsibility is permanently
  forbidden (by a model validator, not just convention) from ever being
  `required`/`preferred` — the same "responsibilities are never a scored
  requirement" rule AJI-012 established, generalized to the wider tier
  set.
- **`relationships`** — `RequirementGroup`s expressing AND/OR/MIN_COUNT/
  EQUIVALENT logic between `requirements` entries by id. Referential
  integrity (every `member_ids` entry must name a real requirement,
  `minimum_count` may not exceed the member count, member ids may not
  repeat) is enforced by model validators on both `RequirementGroup` and
  the top-level result, not by convention. An EQUIVALENT relationship
  whose JD-stated alternative could not be resolved to a second
  canonical requirement (e.g. "AWS or equivalent cloud platform
  experience") is never fabricated as a second structured requirement —
  the alternative's text is kept verbatim on the item's
  `equivalent_alternatives` instead (see "do not fabricate taxonomy
  equivalences" below).
- **`screening_constraints`** — pass/fail gating conditions (work
  authorization, sponsorship, citizenship, clearance, background/drug
  screening, minimum age, driver's license) kept in their own list,
  never mixed into `requirements` — mirrors AJI-012's
  `AuthorizationSignals` being separate from skills/experience,
  generalized to the wider set of screening gates a JD can state.
- **`quality`** — `duplicate_groups` (same requirement mentioned more
  than once; the highest-importance occurrence is kept in
  `requirements`, every occurrence is recorded here) and
  `contradictions` (conflicting importance for the same requirement,
  conflicting experience-year ranges for the same area, or an explicit
  "not required" statement contradicting a genuine requirement of the
  same skill elsewhere in the JD) — deliberately conservative,
  pattern-based diagnostics, not exhaustive NLU-level contradiction
  reasoning.
- **`security`** — see "JD prompt-injection handling" below.
- **`identity`/`domain`** — title/seniority/role-family/domain, same
  deterministic-extraction-wins/AI-fills-the-gap shape and evidence-
  substring anti-hallucination check as AJI-012's `JobIdentity`/
  `DomainInfo`.

### Related-but-different technology protection

`deterministic.find_protected_skills()` wraps `services.skills.
find_skills()` (unmodified — this module does not alter shared
infrastructure other tickets depend on) with a small, explicit exclusion
list (`_PROTECTED_COMPOUND_EXCLUSIONS`, e.g. `"react" -> ("react
native",)`) so a JD clause naming a distinct, related technology never
gets misattributed to the base skill it merely shares a word with. The
check is conservative in both directions: it strips known compound-
phrase occurrences from the clause and only keeps crediting the base
skill if it is still independently detectable in what remains — so
"React Native experience required" extracts nothing (React Native is not
itself in the canonical vocabulary, and fabricating an entry for it is
out of scope — see "do not fabricate taxonomy equivalences" in the
ticket), while "React and React Native experience required" still
credits "react".

### JD prompt-injection handling

The raw JD text is untrusted, attacker-influenceable input. The defense
is structural, not a text-mutation step: `prompts.py`'s system prompt
explicitly instructs the AI stage to treat the JOB DESCRIPTION block as
data to describe, never as instructions, and `validator.py`'s evidence-
substring check (identical mechanism to AJI-012's) drops any AI-claimed
field whose "evidence" does not verbatim-match the source text —
regardless of what an embedded instruction asked the model to output.
Deterministic extraction is immune by construction (it only ever
pattern-matches structure, never executes JD content).
`deterministic.detect_prompt_injection_signals()` additionally flags
known injection phrasing (e.g. "ignore previous instructions", "you are
now...", "mark this candidate as...") into `SecurityDiagnostics` for
audit visibility — this is diagnostic only, the JD text is never
stripped/altered before being sent to the AI stage, since "cleaning"
attacker-controlled text is its own injection surface and risks
destroying legitimate JD content that happens to match a pattern.

### Failure handling and idempotency-readiness

Mirrors AJI-012: deterministic extraction failing is a hard error
(`RequirementIntelligenceServiceError`, 503) — nothing is returned. A
failed AI call degrades to `extraction_status = "partial"` (only
deterministic fields populated; `identity.normalized_title`/
`role_family`/`domain` stay unset) rather than discarding real,
evidence-backed deterministic data. Security diagnostics are always
present even in a partial result, since detection is a deterministic
pass independent of the AI stage. `analysis_version`/`analyzer_version`/
`prompt_version` are fixed constants today (no caller-facing
idempotency/caching exists yet, since there is no DB row to key) but are
carried on every result specifically so a future persistence layer can
reuse the exact `(source_id, content_fingerprint, analyzer_version,
prompt_version)` cache-key shape `JobIntelligence` already established,
without re-deriving it.

### Testing

`tests/test_requirement_intelligence_contracts.py` covers every model
validator (`SourceSpan` bounds, `RequirementItem` hard-requirement/
responsibility invariants, `RequirementGroup` relationship-arity rules,
top-level referential integrity). `tests/test_requirement_intelligence_
deterministic.py` covers provenance-span accuracy, all four importance
tiers, hard-requirement detection, AND/OR/MIN_COUNT/EQUIVALENT
extraction (including that a MIN_COUNT clause is never double-counted as
a plain requirement, and that a MIN_COUNT group is never fabricated
below its evidenced member count), experience constraints (at-least/at-
most/range operators), education/certification extraction,
responsibilities-vs-requirements separation, seniority-from-title,
screening constraints staying separate from scored requirements,
duplicate detection/merging, all three contradiction types, ambiguity
flags, and related-but-different technology protection (React vs. React
Native, Node.js vs. Node-RED, Java vs. JavaScript staying distinct).
`tests/test_requirement_intelligence_validator.py` covers the evidence-
substring anti-hallucination check and deterministic-wins-over-AI
precedence. `tests/test_requirement_intelligence_provider.py` mirrors
`test_job_intelligence_provider.py`'s OpenAI-strict-schema regression
guard. `tests/test_requirement_intelligence_service.py` covers the full
pipeline (success, AI-failure-degrades-to-partial, deterministic-failure-
raises), including that a malicious AI response fabricated in response
to injected JD text is still dropped by the evidence check.
`tests/test_requirement_intelligence_security.py` covers prompt-
injection signal detection directly and confirms legitimate extraction
is unaffected by injection-like text elsewhere in the JD.

### Deferred to AJI-020B

Persistence (an ORM model/Alembic migration), an API router, idempotent
caching keyed off a real `content_fingerprint`, and wiring this model
into any consumer (ATS Alignment or otherwise) are all explicitly left
for a follow-up ticket — see the package-layout note above for why.

### Contract semantics clarification (supervisor review pass)

A follow-up review pass asked for the contract's semantics to be made
explicit so downstream NERO systems cannot interpret requirements
inconsistently. No behavior changed in this pass — it is documentation
only (`contracts.py` docstrings are the authoritative, in-code version
of everything below; this section summarizes them). The full detail
lives on `ImportanceTier`, `RequirementItem`, `RequirementGroup`, and
`ScreeningConstraint` in `contracts.py`.

**Importance tiers** (`required`/`preferred`/`contextual`/
`informational`) answer "how did the JD weight this?" and are metadata
only — AJI-020A never scores or screens with them itself (see
"Downstream contract" below). `required`: the JD states this is needed.
`preferred`: wanted, not mandatory. `contextual`: the JD mentions it to
describe the job/team/stack, not as something the candidate must
demonstrate. `informational`: purely descriptive JD content (this is the
tier every `responsibility` item is confined to, alongside
`contextual`, by a model validator — a responsibility can never be
`required`/`preferred`). `hard_requirement` is a **separate, orthogonal**
field: it is `True` only when the JD used explicit strict/gating
language (`deterministic.HARD_REQUIREMENT_MARKERS`) for that specific
item, never merely because `importance == "required"`. The one enforced
relationship between the two: `hard_requirement=True` requires
`importance == "required"` (the reverse does not hold — most `required`
items are not `hard_requirement`). Neither field affects screening;
screening is modeled exclusively by `screening_constraints` (see below).

**`hard_requirement`** qualifies when a `RequirementItem`
(skill/experience/education/certification — never a responsibility, and
never a screening constraint, which has no such field) used unusually
strict JD language. It is classification metadata for a future
consumer's own scoring/gating decision, not an instruction this module
carries out itself. Not every hard requirement is a screening
constraint, and screening constraints are never represented as
requirements (see the `RequirementItem`/`ScreeningConstraint` boundary
below) — the two model types are disjoint by construction.

**`RequirementItem` vs. `screening_constraints`**: screening constraints
(work authorization, sponsorship, citizenship, security clearance,
background check, drug screening, minimum age, driver's license, or
`other`) are pass/fail gates extracted by their own, separate
deterministic pass (`extract_screening_constraints`) and are never
converted into, or mixed into, `requirements`. A clause can legitimately
produce both a `RequirementItem` and a `ScreeningConstraint` when it
genuinely names both kinds of thing (e.g. "must have AWS certification
and pass a background check"), but a screening-only clause never
produces a skill/experience/education/certification item for the same
gate. `RequirementGroup.member_ids` can never reference a
`ScreeningConstraint.id`. The `ScreeningConstraintType` enum above is
the complete supported taxonomy today — there is no `location` type
(location/eligibility comparison is AJI-011 Hard Eligibility's
user-side concern, not JD requirement language); this pass documents
that boundary rather than expanding it.

**Relationships** (`AND`/`OR`/`MIN_COUNT`/`EQUIVALENT`) are flat,
order-independent sets of `RequirementItem` ids — order in `member_ids`
never carries meaning, and nesting (a group referencing another group)
is not supported. `AND`: every member required. `OR`: any one member
suffices. `MIN_COUNT`: an explicit `minimum_count` (schema-enforced
`1 <= minimum_count <= len(member_ids)`) of the listed members suffices;
the deterministic extractor never fabricates a group, or pads
`member_ids`, below the JD's own evidenced member count. `EQUIVALENT`:
created *only* by the deterministic extractor matching an explicit JD
phrase ("... or equivalent ...") — never by an AI judgment call or a
similarity heuristic (the AI stage's output schema has no field capable
of expressing a relationship at all, so it cannot produce or influence
one). It represents an equivalence the JD itself explicitly stated, and
must not be read as "similar technology", "related technology", or "the
AI thinks these are close" — that boundary is distinct from, and does
not weaken, the related-but-different technology protection described
above (React vs. React Native, etc.). Every `member_ids` entry is
validated against the result's own `requirements` list; a dangling or
out-of-scope reference (including one aimed at a screening constraint)
fails validation rather than being silently kept.

**Downstream contract**: AJI-020A produces normalized requirement
intelligence — a structured, versioned reading of the JD — and nothing
more. Future consumers (ATS Alignment, Job Match, Gap Analysis, a future
Priority Ranking ticket) are expected to consume this contract rather
than independently re-parsing or re-interpreting raw JD language
themselves, mirroring the "one canonical reading, many consumers"
principle AJI-012 `JobIntelligenceResult` already established. Wiring
any such consumer to this contract remains explicitly out of scope here
(AJI-020B or later).

`tests/test_requirement_intelligence_contracts.py` carries the
executable proof of the above: that `importance` and `hard_requirement`
remain independently representable (a `required` item may or may not be
`hard_requirement`; a non-`required` item can never be
`hard_requirement`), that a `RequirementGroup` can never reference a
`ScreeningConstraint.id`, that `MIN_COUNT` enforces its explicit
minimum/member bounds, that the AI decoding stage's schema cannot carry
a relationship (so `EQUIVALENT` cannot silently become general
AI-judged similarity), and that every relationship reference is
validated.

## Requirement Intelligence Persistence & API (AJI-020B)

AJI-020B adds persistence and an authenticated API around AJI-020A's
pure, DB-free pipeline — it does not touch AJI-020A's contract,
extraction, or validation logic at all (every file under
`apps/api/services/requirement_intelligence/` from AJI-020A is
unmodified; this ticket only adds new files alongside them). It also
does not wire Requirement Intelligence into ATS Alignment, Job Match, or
Gap Analysis — those remain future work.

### Persistence architecture

`apps/api/models.py`'s `RequirementIntelligence` is a single table
(mirroring `JobIntelligence`'s balance of typed top-level columns for
what needs indexing/filtering plus one JSONB column for the full
contract) rather than decomposed into per-requirement/per-relationship/
per-screening-constraint tables: the AJI-020A result is already a single
structured, closed-schema (`extra="forbid"`) contract, and every other
AI-derived artifact in this system (`JobIntelligence`, `AtsAlignmentResult`,
`GapAnalysis`) persists its full result the same way. `structured_intelligence`
holds `RequirementIntelligenceResult.model_dump(mode="json")` verbatim —
nothing is re-derived, summarized, or dropped in persistence, and a
persisted row can be re-validated straight back through
`RequirementIntelligenceResult.model_validate(...)` to prove nothing was
lost (see `test_full_ajI_020a_result_survives_persistence_without_loss`).

**Personalized, unlike `JobIntelligence`**: this ticket's spec
explicitly requires the row to be associated with a `user_id` (not just
`job_id`), and requires that "a user must never be able to read another
user's snapshot." `RequirementIntelligence` is therefore built on the
same personalized shape as `AtsAlignmentResult`/`GapAnalysis`
(`user_id` + `job_id`, both `ForeignKey(..., ondelete="CASCADE")`,
indexed), not `JobIntelligence`'s shared/job-scoped shape — even though
AJI-020A's own extraction never reads resume/user data and so would
produce byte-identical output for every user who analyzes the same job.
This is a product decision handed down by the ticket, not a claim that
the requirement *content* itself varies by user — see the model's
docstring in `apps/api/models.py`.

### Snapshot identity / content fingerprint

`persistence_service.compute_requirement_content_fingerprint(job)`
hashes exactly the four `Job` fields AJI-020A's pipeline reads
(`title`/`description`/`requirements`/`responsibilities`), normalized
(whitespace-collapsed, lowercased, newline-joined) and SHA-256'd — the
same canonicalization convention `job_intelligence.service.
compute_job_content_fingerprint` already established, but **deliberately
scoped narrower**: `JobIntelligence`'s fingerprint additionally covers
location/salary/employment-type/contract fields AJI-020A never reads, so
reusing it here would create a spurious "new snapshot" on a `Job` edit
that cannot possibly change this pipeline's output. No timestamp, random
value, or model-generated text ever feeds it (see
`test_irrelevant_job_edit_does_not_create_a_new_snapshot` and
`test_fingerprint_scoped_to_pipeline_relevant_fields_only`).

### Idempotency and uniqueness

A snapshot is looked up (and reused, skipping AJI-020A's pipeline and
any AI call entirely) by
`(user_id, job_id, content_fingerprint, analyzer_version, prompt_version,
model_provider, model_name)` — wider than `JobIntelligence`'s four-part
key, per this ticket's explicit instruction that a changed "model/
provider configuration" must also be able to produce a new snapshot.
`model_provider`/`model_name` for the lookup are read directly off
`apps.api.config.settings` (no network call, no provider-specific
import — see `persistence_service._prospective_model_identity`), so a
cache hit is decided before AJI-020A's pipeline (and any AI call) ever
runs.

A `UniqueConstraint` on that same seven-column tuple
(`uq_requirement_intelligence_identity`) backstops the application-level
lookup against a concurrent double-insert. Existing insert-only tables in
this codebase (`JobIntelligence`, `AtsAlignmentResult`, `GapAnalysis`)
rely on the lookup-before-insert alone with no DB constraint; this ticket
adds one where the AJI-020B spec explicitly asked for it ("use an
explicit uniqueness constraint where appropriate") — a legitimate
divergence, not new precedent forced onto AJI-020A's own tables, which
this ticket does not touch.

### Versioning and immutability

`analysis_version`/`analyzer_version`/`prompt_version`/`model_provider`/
`model_name` are copied verbatim from the AJI-020A result onto the row —
never recomputed or replaced by a persistence-layer constant — so a
historical row keeps whatever version actually produced it even after
AJI-020A's own constants are bumped later. Rows are insert-only, exactly
like every other AI-derived artifact in this system: a changed JD
(different fingerprint), a bumped analyzer/prompt version, or a changed
AI provider/model configuration always produces a new, additional row;
existing rows are never updated, overwritten, or exposed through any
edit endpoint (there isn't one — see "API boundary" below).

One implementation note worth recording: `persistence_service.py`
imports `apps.api.services.requirement_intelligence.service` as a
*module* (`requirement_intelligence_service.ANALYZER_VERSION`/
`.PROMPT_VERSION`), not via `from ... import ANALYZER_VERSION`. AJI-020A's
`build_requirement_intelligence()` reads those two names as its own
module globals at call time; a `from...import` copy taken once at import
time would silently drift out of sync with whatever that function
actually stamps onto a result if the source module's attribute changes
after import (this was caught by
`test_analyzer_version_bump_creates_new_snapshot`/
`test_prompt_version_bump_creates_new_snapshot` during development,
which raised a real `UniqueViolation` under the naive `from...import`
form). Referencing the module keeps the lookup key and the stamped
result permanently reading the same single source of truth.

### Known limitation: partial-result self-healing vs. row growth

Because `model_provider`/`model_name` are part of the idempotency key, a
"partial" row (AI stage failed/unavailable) always has both `NULL` — and
Postgres never treats `NULL` as equal to `NULL`, so this key can never
match an existing partial row. Effect: every subsequent request
*retries* AJI-020A's AI stage rather than permanently serving a stale
partial result once cached (an improvement over `JobIntelligence`'s
narrower key, which can get stuck serving a partial snapshot forever).
The cost: repeated requests for the same job while the AI provider stays
down each create one additional partial row rather than reusing a single
one. This is a direct, disclosed consequence of the ticket's own
instruction to key on model/provider configuration, not an oversight;
smoothing it further (e.g. a short-lived "don't retry more than once a
minute" rule) is out of this ticket's scope (no rate limiting, no Redis,
no background worker — see the ticket's own scope-protection list) and
is flagged here rather than silently invented.

### Service layer

`apps/api/services/requirement_intelligence/persistence_service.py` is
the sole DB-touching orchestration layer, mirroring
`apps.api.services.job_intelligence.service`'s and `apps.api.services.
ats_alignment_service`'s DB/pure-core split: `get_latest_requirement_
intelligence` (read-only, never recomputes) and `generate_requirement_
intelligence` (idempotent create-or-reuse). All business logic
(extraction, AI decoding, validation) stays in AJI-020A's own
`service.build_requirement_intelligence()`; this layer only resolves the
`Job`, computes the fingerprint/idempotency key, and persists the
result. No AI provider is imported or hardcoded here — `settings.
ai_provider`/`settings.ai_model` are the only provider-related values
this module ever reads directly (see "AI provider boundary" below).

### API

Two authenticated endpoints on the existing `/jobs` router (same file,
same `get_current_user` dependency, same 404/error-shape conventions as
every other per-job endpoint):

- `GET /jobs/{job_id}/requirement-intelligence` — returns the
  authenticated user's newest snapshot; 404s if none exists yet. Never
  recomputes or calls the AI provider on a read (mirrors `GET .../
  intelligence` and `GET .../ats`).
- `POST /jobs/{job_id}/requirement-intelligence` — computes-or-reuses
  (idempotent, per above).

No PUT/PATCH/DELETE — snapshots are immutable and insert-only, so there
is nothing to edit and nothing a generic CRUD surface would add (per the
ticket's explicit "not a generic database-management API" instruction).

### Authorization

Every request requires authentication (`Depends(get_current_user)`);
`user_id` is always the resolved authenticated user's own id, never
taken from a request parameter or body. A job lookup miss and a
not-yet-generated snapshot both 404 identically for any authenticated
user, and `get_latest_requirement_intelligence`/`generate_requirement_
intelligence` always filter by the caller's own `user_id` — there is no
code path that can return another user's row (`test_requirement_
intelligence_is_not_visible_to_other_users`,
`test_different_users_get_independent_requirement_intelligence_records`).
The public `/jobs` listing never includes Requirement Intelligence data
(`test_public_jobs_listing_never_includes_requirement_intelligence`).
`Job.id`/`User.id` are always server-resolved database values; the
original JD text remains untrusted input exactly as AJI-020A already
handles it (evidence-substring anti-hallucination check, prompt-
injection diagnostics) — this ticket adds no new trust boundary.

### AI provider boundary

No new AI provider is introduced. `persistence_service.py` never imports
`OpenAIRequirementIntelligenceProvider` or any OpenAI-specific symbol —
it only reads the generic `settings.ai_provider`/`settings.ai_model`
values (the same ones AJI-020A's own
`providers.factory.create_requirement_intelligence_provider` reads) to
compute the prospective idempotency key before invoking AJI-020A's
pipeline. A provider failure is handled exactly as AJI-020A already
handles it — degrade to `extraction_status = "partial"`, never lose the
deterministic result, never raise — so this ticket introduces no new
fallback behavior.

### Migration

`apps/api/alembic/versions/8a040c819900_add_requirement_intelligence.py`
(`down_revision = '6fdd95443549'`, the prior head) creates the
`requirement_intelligence` table with FKs to `jobs`/`users`
(`ondelete="CASCADE"`), indexes on `user_id`/`job_id`/
`content_fingerprint`, and the `uq_requirement_intelligence_identity`
unique constraint described above. Verified against a real local
Postgres 16 instance: fresh-database `alembic upgrade head` (the full
chain from `a6f4cbc0a2a0` through this migration), `downgrade -1`
(cleanly drops the table/indexes), and re-`upgrade head` all succeed; no
other table is touched.

### Deferred consumers

Wiring Requirement Intelligence into ATS Alignment, Job Match, Gap
Analysis, or a future Priority Ranking ticket is explicitly out of scope
for both AJI-020A and AJI-020B — this ticket only makes the contract
persistable and retrievable. Any such consumer is future work.

### Testing

`tests/test_requirement_intelligence_persistence_service.py` (FakeDB,
mirrors `test_job_intelligence_service.py`) covers wiring: persist a new
snapshot, reuse a cached one without invoking AJI-020A's pipeline, a
missing job, a propagated `RequirementIntelligenceServiceError`, and
fingerprint determinism/scoping. `tests/test_requirement_intelligence_
persistence_versioning.py` (real DB, mirrors `test_job_intelligence_
versioning.py`) covers the actual SQL filtering: same-content reuse,
changed-JD versioning without touching history, that an irrelevant `Job`
edit does *not* bust the cache, analyzer/prompt/model-configuration
version bumps each producing a new row, `get_latest` returning the
newest row, raw JD snapshot immutability across versions, and a full
AJI-020A-result-survives-persistence-losslessly round trip (including
provenance spans re-verified against the job's own text, and the
persisted JSON re-validated through `RequirementIntelligenceResult`
itself). `tests/test_jobs_requirement_intelligence_api.py` (real DB +
`TestClient`, mirrors `test_jobs_ats_api.py`) covers authentication,
404s, response shape, idempotency, user isolation, the public listing
exclusion, and both AJI-020A failure modes (provider failure degrading
to a 200 "partial" response, deterministic failure surfacing as 503)
through the actual HTTP layer.

### Architecture lock (AJI-020B final review)

The following is a final, reviewed architecture decision for AJI-020B
and must not be changed without a new ticket:

A `RequirementIntelligence` snapshot is immutable and uniquely
identified by the 7-dimension tuple `user_id`, `job_id`,
`content_fingerprint`, `analyzer_version`, `prompt_version`,
`model_provider`, `model_name` (see "Idempotency and uniqueness" above
for the lookup/`UniqueConstraint` mechanics). A change to any one of
these dimensions may produce a new, additional snapshot; existing
snapshots are never overwritten, edited, or deleted by any code path in
this system (see "Versioning and immutability" above). The
partial-row-growth behavior under a sustained provider/model-configuration
change (see "Known limitation" above) is an accepted trade-off for this
ticket, not a defect to fix here.

Explicitly not introduced, and out of scope for AJI-020B: cleanup jobs
for old/partial rows, overwrite-in-place behavior, provider fallback
logic beyond AJI-020A's own existing degrade-to-partial handling, Redis
or any other external cache, new caching infrastructure beyond the
database persistence described above, and AI provider-selection logic
(this layer only reads `settings.ai_provider`/`settings.ai_model`; it
never chooses or overrides a provider). Introducing any of these is a
new ticket's scope, not a fix or extension of AJI-020B.

## ATS Alignment / Requirement Intelligence Integration (AJI-020C)

AJI-020C makes ATS Alignment (AJI-013) consume the normalized,
persisted AJI-020A/B `RequirementIntelligence` contract instead of
independently re-deriving requirements from AJI-012 `JobIntelligence`.
AJI-020A's and AJI-020B's own semantics are unmodified — every file
under `apps/api/services/requirement_intelligence/` is untouched by
this ticket; AJI-020C only adds an adapter around them.

**A reported discrepancy, addressed head-on rather than guessed at, and
since resolved by a parallel ticket:** at the time AJI-020C was built,
the ticket's own architecture diagram and scoring instructions referred
to an "AJI-020 real ATS scoring engine" with four named weighted
components that did not exist anywhere in this repository — a
repository-wide search for those component names returned nothing, and
`services/ats_alignment/scoring.py`'s own module docstring stated
explicitly that no Must-Have/Preferred weighting formula had been
approved and instructed the Builder not to invent one. AJI-020C was
therefore built to integrate Requirement Intelligence up to and
including the existing placeholder, equal-weight `services.
ats_alignment.scoring` engine, entirely unchanged, rather than inventing
that engine — reported per the ticket's own "if a scoring change appears
necessary, STOP and report it instead of changing the product policy"
instruction, not silently decided. **AJI-020 ("ATS Real Scoring Engine",
see the section immediately above this one) was delivered separately
and merged into this branch afterward**, implementing exactly that
approved four-component formula. AJI-020C's own code never modified
`scoring.py`/`weights.py`/`resume_adapter.py` and needed no changes to
absorb AJI-020's engine: `_build_job_requirements_from_requirement_
intelligence` produces the same `JobRequirementItem` shape either engine
consumes, so AJI-020's weighted scoring runs against Requirement-
Intelligence-sourced requirements automatically. The `hard_requirement`/
`ambiguous`/`ambiguity_reason`/`relationships`/`screening_constraints`
additions described below remain exactly as AJI-020C defined them: still
never read by any scoring computation, AJI-020's four components
included.

### Integration boundary and data flow

```
Job (title/description/requirements/responsibilities)
        |
        v
RequirementIntelligence (AJI-020A extraction, AJI-020B persistence)
        |
        v
_build_job_requirements_from_requirement_intelligence  (AJI-020C adapter)
        |
        v
services.ats_alignment.engine.evaluate_ats_alignment  (matching logic - unmodified by AJI-020C)
        |
        v
AtsAlignmentResult  (persisted; scored by whichever engine/scoring.py version is current - see AJI-020 above)
```

`apps/api/services/ats_alignment_service.py`'s
`_build_job_requirements_from_requirement_intelligence` is the sole new
adapter: it reads a `RequirementIntelligenceResult` and produces the
same `JobRequirementItem` list `services.ats_alignment.engine` already
consumed pre-AJI-020C. AJI-020C itself never modifies the engine's
per-type evaluators or `services.ats_alignment.scoring`'s aggregation —
it only threads three new metadata fields through them (see "Importance
/ hard_requirement" below) and adds two new, purely descriptive result
sections (see "Relationship handling" and "Screening constraint
separation" below). Whichever scoring formula is current in `scoring.py`
(the AJI-013 placeholder, or AJI-020's four-component weighted formula —
see above) runs unchanged against Requirement-Intelligence-sourced
requirements, since both engines consume the identical
`JobRequirementItem`/`RequirementAlignment` shape.

`JobIntelligence` (AJI-012) generation/fetch is retained unchanged in
`calculate_ats_alignment` — every new row still populates
`job_intelligence_id`/`job_content_fingerprint` — purely for
backward-compatible lineage. Its *content* (required_skills, etc.) is no
longer read to build the scored requirement list; `RequirementIntelligence`
is. This was a deliberate choice to minimize blast radius (no schema
change to an existing NOT NULL column, no ripple into whatever else
might reference it) rather than a claim that `JobIntelligence` remains
architecturally necessary for ATS Alignment going forward — a future
ticket may reconsider whether this column should be deprecated once
nothing else depends on it.

### Requirement mapping

Every AJI-020A `RequirementItem` with `importance in {"required",
"preferred"}` maps 1:1 onto a `JobRequirementItem`
(`must_have`/`preferred`, exactly AJI-012's old two-tier taxonomy —
`RequirementCategory` still has only two values). `contextual`/
`informational` items, and every `requirement_type == "responsibility"`
item, are excluded before reaching the engine at all — AJI-020A's own
locked contract already forbids a responsibility from ever being
`required`/`preferred`, and a `contextual`/`informational` item is, by
AJI-020A's own locked definition, not something the candidate must
demonstrate — so there is nothing to invent a scored category for. This
is the same "exclude, don't force a category" treatment AJI-012's
`responsibilities` field already received.

Preserved fields: `requirement_id` (now the originating AJI-020A
`RequirementItem.id` verbatim, replacing the old synthetic
`f"skill:{...}"`-style key — every scored requirement is traceable back
to the exact Requirement Intelligence item it came from),
`requirement_type`, `requirement_text` (reconstructed per type, same
format as the old AJI-012-based mapping), `jd_evidence` (the item's
`raw_text` clause — the provenance a consumer already gets; the
character-offset `source_span` itself is not additionally threaded
through, judged not essential on top of the verbatim clause text),
`canonical_skill`/`minimum_years`/`area`/`degree_level`/
`field_of_study`/`certification_name` (same per-type fields as before,
now read from AJI-020A's typed `experience`/`education`/`certification`
sub-objects). Two new fields added to `JobRequirementItem`/
`RequirementAlignment` because the existing contract had no place for
them: `hard_requirement: bool` and `ambiguous: bool` +
`ambiguity_reason: str | None` (AJI-020A metadata, carried through
unchanged — see "Importance / hard_requirement" below).

### Relationship handling — reported architecture gap, not invented

AJI-020A's `RequirementGroup`s (AND/OR/MIN_COUNT/EQUIVALENT) have no
representation in the pre-existing `AtsAlignmentResult` contract — there
is no concept anywhere in `services.ats_alignment.scoring` of "this
OR-group counts as one satisfied requirement," and AJI-020C does not
invent one (per the ticket's explicit "if the current ATS result
contract has no appropriate representation for group-level fulfillment,
STOP and report the architecture gap instead of inventing one"
instruction). Computing a derived group-level verdict — e.g. deciding
an OR-group is "satisfied" once any one member matches, or an
AND-group only once every member does, and feeding *that* into
`overall_score`/`must_have_total` — is left to a future ticket.

What AJI-020C does instead: every member of a relationship group is
still scored fully independently, exactly like any other requirement
(never collapsed, never promoted/demoted based on its groupmates' verdicts
— "Python OR Java" never becomes "Python AND Java", and "3 of 5
technologies" never becomes 5 mandatory requirements, because neither is
converted into anything at all). The group itself is surfaced
separately and descriptively: `services.ats_alignment.contracts.
RequirementRelationshipGroup` (`group_id`, `relationship`,
`member_requirement_ids`, `minimum_count`, `description`) is a
verbatim, unevaluated pass-through of AJI-020A's own `RequirementGroup`,
returned on `AtsAlignmentResult.relationships` and persisted in
`AtsAlignmentResult.result["relationships"]`/exposed on the API
response — visible to a consumer, never read by
`compute_overall_score`/`compute_overall_confidence`. A relationship
group may reference a member id that does not appear in
`requirement_results` when that member was itself `contextual`/
`informational` (and therefore excluded from scoring, per "Requirement
mapping" above) — this is passed through as-is from AJI-020A rather
than filtered, since inventing filtering logic here would itself be an
unrequested decision.

### Screening constraint separation

AJI-020A's `ScreeningConstraint`s (work authorization, sponsorship,
citizenship, clearance, background/drug screening, age, license) are
never scored as technical requirements and never appear in
`requirement_results`/`must_have_total`/`preferred_total`. Mirroring the
relationship treatment above, `services.ats_alignment.contracts.
ScreeningConstraintInfo` is a verbatim, descriptive-only pass-through,
surfaced on `AtsAlignmentResult.screening_constraints` /
`result["screening_constraints"]` / the API response, never read by any
scoring function. The existing ATS contract had no mechanism for
screening constraints at all pre-AJI-020C (same "no representation,
report rather than invent scoring behavior" situation as relationships)
— this section exists precisely so they are preserved as separate
intelligence rather than silently dropped or, worse, folded into the
scored skill/experience/education/certification list.

### Importance / hard_requirement

`importance` (required/preferred/contextual/informational) and
`hard_requirement` remain the distinct, orthogonal concepts AJI-020A
locked: `category` (must_have/preferred) is derived from `importance`
alone; `hard_requirement` is carried onto every `JobRequirementItem`/
`RequirementAlignment` as metadata and is never read by
`services.ats_alignment.scoring` or any evaluator's status/confidence
decision. No product rule for how `hard_requirement` should affect
scoring (a penalty, a gate, a ceiling) has been approved anywhere in
this codebase, and AJI-020C does not invent one — per the ticket's
explicit "do not invent a weighting or penalty" instruction, this is
reported here as an open product decision for a future ticket, not
resolved. Two requirements that are otherwise identical except for
`hard_requirement` score identically today (see
`test_hard_requirement_true_is_preserved_but_never_changes_scoring`).

### Fallback behavior

There is no approved fallback to raw-JD parsing if Requirement
Intelligence is unavailable — and this was not invented for AJI-020C.
The pre-existing, already-approved pattern for exactly this situation
already exists one line above it: if `JobIntelligence` generation fails,
`calculate_ats_alignment` has always propagated an
`ATSAlignmentServiceError` carrying the underlying status code rather
than falling back to anything. Requirement Intelligence generation
failure is handled by the identical pattern — reused, not reinvented —
so a Requirement Intelligence outage surfaces as a clean error response
(503 in practice, from `RequirementIntelligencePersistenceError`) rather
than either a silent raw-JD reinterpretation or an unhandled exception.

### Versioning / historical preservation

The ATS Alignment idempotency key grows from
`(user_id, job_id, resume_version_id, job_intelligence_id,
engine_version)` to
`(user_id, job_id, resume_version_id, job_intelligence_id,
requirement_intelligence_id, engine_version)` — AJI-020C adds
`requirement_intelligence_id`, it does not remove or loosen any existing
dimension (per the ticket's "inspect the existing persistence identity
before changing it" instruction). A new migration
(`apps/api/alembic/versions/
c3f6a1d47e21_add_requirement_intelligence_to_ats.py`, `down_revision =
'8a040c819900'`) adds two nullable columns to the existing
`ats_alignment_results` table — `requirement_intelligence_id` (FK to
`requirement_intelligence.id`, `ondelete="CASCADE"`, indexed) and
`requirement_intelligence_fingerprint` (mirroring `job_content_fingerprint`'s
role) — nullable only because they were added to a table that may
already hold rows from before this ticket; every row AJI-020C's code
creates populates both. `AtsAlignmentResult` rows remain insert-only and
immutable, exactly as before: a new Requirement Intelligence snapshot
(edited JD, or a bumped AJI-020A analyzer/prompt/model configuration —
see AJI-020B's locked idempotency key above) produces a new, additional
ATS row rather than mutating history; resume-version isolation and
job/user isolation are both unchanged and still enforced by the same
query filters as before (see
`test_changed_requirement_intelligence_snapshot_creates_new_analysis_and_new_score`,
which additionally proves the score itself now genuinely changes,
unlike the old JobIntelligence-only dimension which changed the row's
identity without changing its content).

### AI vs. deterministic responsibility

AJI-020C introduces no new AI call. AJI-020A owns AI interpretation,
ambiguity handling, evidence validation, and relationship extraction
(all upstream, already complete by the time `RequirementIntelligence` is
persisted). AJI-020C's own code
(`_build_job_requirements_from_requirement_intelligence`,
`services.ats_alignment.engine`) is 100% deterministic: it reads an
already-validated `RequirementIntelligenceResult`, maps it, and runs the
existing deterministic evidence-matching engine against the resume —
the same division of responsibility ATS Alignment already had with
`JobIntelligence` before this ticket, just with a different upstream
source.

### API

No new endpoint. `GET`/`POST /jobs/{job_id}/ats` are unchanged in shape
and behavior; the JSON response gains `requirement_intelligence_id`,
`relationships`, and `screening_constraints` (additive — a historical
row's `result` JSON predating this migration reads back as `[]` for the
latter two via `.get(..., [])` in `_ats_alignment_to_response`), and
each `requirement_results` entry gains `hard_requirement`/`ambiguous`/
`ambiguity_reason`. No frontend changes.

### Known limitations

- At the time AJI-020C was built, the weighted "AJI-020 real ATS scoring
  engine" the ticket describes did not exist in this codebase (see the
  top of this section) and was flagged rather than built, per the
  ticket's own instruction; it has since been delivered separately as
  AJI-020 (see that section above) and merged in — this note is kept for
  the historical record of AJI-020C's own scope boundary.
- `hard_requirement` has no approved scoring effect yet (see
  "Importance / hard_requirement" above) — open product decision.
- A relationship group can reference a member id absent from
  `requirement_results` when that member was `contextual`/
  `informational` (see "Relationship handling" above) — intentional,
  not filtered.
- AJI-020A's `ExperienceConstraint.operator` can be `at_most`/`exact`/
  `range`, but the unmodified engine's `_evaluate_experience` only ever
  compares `years >= minimum_years` (an implicit "at least" semantic) —
  this pre-dates AJI-020C (AJI-012's own experience shape never modeled
  operators either) and is not fixed here, since changing
  `_evaluate_experience`'s matching logic is a scoring-engine change
  outside AJI-020C's scope.
- `job_intelligence_id` is retained on every new `AtsAlignmentResult`
  row purely for lineage even though its content no longer drives
  scoring (see "Integration boundary" above) — a deliberate, disclosed
  minimal-blast-radius choice, not an oversight.
