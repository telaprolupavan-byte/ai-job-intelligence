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
(ATS Alignment), AJI-014 (Gap Analysis), AJI-015 (Suggestions), and
AJI-016 (Priority Ranking) all consume — none of them re-parse the raw
JD text themselves.

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
ATS Alignment (AJI-013, future), and Suggestions (AJI-015, future) all
stay in their own user-scoped tables/services and are never written
into `JobIntelligence.structured_intelligence`.

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
