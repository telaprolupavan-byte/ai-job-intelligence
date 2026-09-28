# NERO Codebase Map

A navigation guide: where things live, and which way dependencies are
allowed to point. It records the structure as it is (AJI-032A inspection,
AJI-032B). For the reasoning behind each feature, see
`docs/ARCHITECTURE.md`. For ticket IDs, see `docs/TICKETS.md`.

## 1. Top level

| Path | What it is |
|---|---|
| `apps/api/` | FastAPI backend: routers, orchestration services, AI capabilities, ORM models, migrations |
| `services/` | Top-level Python packages: pure domain engines, the job discovery pipeline, and offline evaluation tools |
| `apps/web/` | Next.js frontend |
| `tests/` | Backend test suite (pytest, real PostgreSQL) |
| `docs/` | `ARCHITECTURE.md` (decisions per ticket), `TICKETS.md`, `AI_EVALUATION_BASELINE.md`, this file |
| `deploy/discovery-scheduler/` | Container that calls `POST /internal/job-discovery/run` on an interval |
| `docker-compose.yml`, `apps/api/Dockerfile` | `api`, `discovery-scheduler`, `db` (postgres:16) |
| `.github/workflows/ci.yml` | Backend (single Alembic head, `alembic upgrade head`, pytest) and web (vitest, tsc, eslint, build) |
| `alembic.ini` | Points at `apps/api/alembic` |

The backend is imported from the repository root as `apps.api.*` and
`services.*`. Run Python commands from the root.

## 2. Backend (`apps/api/`)

| Path | Responsibility |
|---|---|
| `main.py` | App, CORS, router registration |
| `config.py` | `Settings`. Reads `.env` at the repo root (path resolved relative to this file) |
| `database.py`, `dependencies.py` | Engine, `get_db`, `get_current_user` / `get_optional_current_user` |
| `security.py`, `rate_limit.py` | Password hashing, JWT, reset tokens; in-memory auth rate limits |
| `models.py` | All ORM tables (one metadata source for Alembic) |
| `schemas.py` | Pydantic request/response models for auth, profile, preferences, resumes, applications, job submission. AI features keep their result contracts in `services/<capability>/contracts.py`; jobs responses are built as dicts in `routers/jobs/` |
| `alembic/versions/` | Migrations (single head, enforced in CI) |
| `routers/` | HTTP layer: `auth`, `profile`, `preferences`, `resumes`, `general_resume`, `jobs`, `job_discovery`, `applications`, `dashboard` |
| `services/` | Orchestration (database access around the pure engines) and every AI capability (sections 4–6) |

Router notes:
- `routers/jobs/` serves the job catalog plus every per-job capability,
  one module each (AJI-034): `search` (`GET /jobs`), `submissions`,
  `priority`, `details` (`GET /jobs/{job_id}`), `match`, `eligibility`,
  `intelligence` (Job and Requirement Intelligence), `alignment` (ATS and
  Gap Analysis), `resume_improvement`. `common.py` holds the shared
  visibility check and job response. `__init__.py` includes them in a
  fixed order, and that order is behavior: `priority` must stay before
  `details`, or "priority" is read as a job id.
  `tests/test_jobs_routes.py` pins the route table and resolution.
- `routers/resumes.py::upload_resume` holds the upload, duplicate-detection
  and version-naming flow directly in the route.
- `routers/dashboard.py` aggregates existing results only; it never
  computes analysis.
- `profile` and `preferences` are simple CRUD with no service layer.

Flat orchestration modules in `apps/api/services/` follow the
`*_service.py` convention: `application_service`, `ats_alignment_service`,
`eligibility_service`, `email_service`, `job_discovery_service`,
`job_match_service`, `priority_ranking_service`. Shared job query rules
live in `job_access.py` (visibility, `active_jobs_filter`) and
`job_listing.py` (`job_listing_query`).

## 3. Domain engines (top-level `services/`)

These packages hold deterministic domain logic. They are free of database
and AI access, with the exceptions listed below.

| Package | Responsibility | Orchestrated by |
|---|---|---|
| `skills/` | Canonical skill vocabulary; all skill normalization goes through it | used everywhere |
| `job_matching/` | Job Match engine (extractor, evidence, matcher, scorer) | `apps/api/services/job_match_service.py` |
| `eligibility/` | Hard Eligibility pre-filter | `eligibility_service.py` |
| `ats_alignment/` | ATS Alignment engine and scoring | `ats_alignment_service.py` |
| `priority_ranking/` | Priority ordering (not a score) | `priority_ranking_service.py` |
| `job_discovery/` | Discovery pipeline (section 5) | `job_discovery_service.py` |
| `provider_scorecard/` | Offline job-source provider evaluation (AJI-018). Only tests consume it | CLI `run_eval.py` |
| `ai_evaluation/` | AI quality evaluation (AJI-031). Only tests and its CLI consume it | CLI `run_eval.py` |

Known exceptions to "no database, no app imports":
- `job_discovery/persistence.py` and `job_discovery/pipeline.py` import
  `apps.api.models` (they write jobs).
- `ai_evaluation/` imports production modules from `apps.api.services`
  on purpose: it measures production code instead of copying it.

## 4. AI capabilities (`apps/api/services/<capability>/`)

Each capability is a self-contained package with the same shape:
`prompts.py`, `providers/openai_provider.py` (closed Structured Outputs
schema and OpenAI call), `providers/factory.py` (chooses a provider from
`settings.ai_provider`), `interpreter.py` (`PROMPT_VERSION`), `validator.py`
(grounding checks on AI output), a deterministic part, and `service.py`.
If the AI call fails, Job Intelligence, Requirement Intelligence, Gap
Analysis and General Resume keep their deterministic result and record a
partial status. Resume Intelligence (`resume_ai`) instead returns an
error for that request.

| Package | Capability |
|---|---|
| `resume_ai/` | Resume Intelligence. `deterministic.py` is also the shared resume analyzer used by General Resume, ATS Alignment, Job Match and resume fingerprinting |
| `job_intelligence/` | Job/JD Intelligence (AJI-012) |
| `requirement_intelligence/` | Requirement Intelligence (AJI-020A/B). `service.py` is database-free; `persistence_service.py` stores results |
| `gap_analysis/` | Gap Analysis & job-specific suggestions (AJI-015), built on ATS Alignment |
| `general_resume/` | General Resume Intelligence (AJI-027): job-independent score, improvements, review, recheck, readiness. The AI only writes explanations |

AI configuration (`ai_provider`, `ai_model`, `openai_api_key`) is in
`config.py`. There is no shared AI client module: each provider builds
its own OpenAI client (`timeout=60.0`; only `resume_ai` also sets
`max_retries=1`). This duplication is known and was deliberately left as
it is (section 10).

Non-AI capability packages in the same folder: `resume_improvement/`
(job-specific approve/recheck, AJI-021) and `job_submission/` (user-pasted
jobs, AJI-022).

## 5. Job flow

```
Provider -> adapter -> normalize -> validate -> deduplicate -> persist (jobs)
  -> active_jobs_filter / visible_jobs_filter -> GET /jobs, GET /jobs/{id}
  -> Job Intelligence / Requirement Intelligence
  -> Hard Eligibility -> Job Match -> ATS Alignment -> Gap Analysis -> Priority
  -> Application Tracking
```

| Step | Location |
|---|---|
| Provider selection | `apps/api/services/job_discovery_service.py::build_configured_source()` (one switch; an unknown provider returns 503) |
| Adapter contract | `services/job_discovery/sources/base.py` |
| Adapters | `sources/greenhouse.py`, `sources/test_fixture.py`, `sources/development_dataset.py` + `.json` (AJI-030) |
| Shared HTTP policy, pagination | `source_http.py`, `pagination.py` (AJI-028) |
| Normalize / validate / deduplicate | `normalizer.py`, `validator.py`, `deduplicator.py` |
| Persist | `persistence.py`, driven by `pipeline.py::run_discovery_pipeline` |
| Runs, lock, status | `job_discovery_service.py`, `DiscoveryRun`, `routers/job_discovery.py` |
| Scheduler | `deploy/discovery-scheduler/` |
| Test-data isolation | `sources/non_production.py::NON_PRODUCTION_SOURCES`, applied by `job_access.visible_jobs_filter()` and the `is_test_data` flags |
| Expiration | `jobs.expires_at` + `job_access.active_jobs_filter()` (evaluated at query time) |
| Attribution | `services/job_discovery/attribution.py` |
| User-submitted jobs | `apps/api/services/job_submission/` (reuses the discovery normalizer and persistence) |
| Job API | `routers/jobs/`, `job_listing.py` |
| Applications | `application_service.py`, `routers/applications.py` (`SavedJob`, `ApplicationStatusEvent`) |

## 6. Resume flow

| Step | Location |
|---|---|
| Upload and versioning | `routers/resumes.py` (`Resume`, `ResumeVersion`) |
| File checks and storage | `apps/api/services/resume_service.py` (`uploads/resumes/`, resolved from this file's location) |
| Parsing (PDF/DOCX) | `resume_parser.py` |
| Validation | `resume_validation.py` |
| Fingerprint (duplicate detection) | `resume_fingerprint.py` |
| Deterministic analysis | `resume_ai/deterministic.py` |
| Resume Intelligence (AI) | `resume_ai/` |
| General Resume Score, improvements, approval, recheck, readiness | `general_resume/` + `routers/general_resume.py` |
| Job-specific improvement and recheck | `resume_improvement/`, exposed under `/jobs/{id}/resume-improvement` |
| Matching input | `services/job_matching/resume_adapter.py`, `services/ats_alignment/resume_adapter.py` |

`general_resume` must not import job-specific modules;
`tests/test_general_resume_boundaries.py` enforces this. It does reuse
`sanitize_user_content` and two limits from `resume_improvement`, which
themselves import nothing job-specific.

## 7. Frontend (`apps/web/`)

| Path | Contents |
|---|---|
| `app/page.tsx` | Landing page |
| `app/login`, `register`, `forgot-password`, `reset-password` | Auth pages |
| `app/(app)/` | Authenticated shell (`layout.tsx`, `auth-gate.tsx`): `dashboard` (with its own `components/`), `jobs` (+ `submit`), `resume`, `applications` (+ `[id]`), `settings`, `ats` (static placeholder) |
| `components/app/` | Application-wide primitives shared across pages: `app-button`, `badge`, `container`, `panel`, `skeleton`, `empty-state`, `error-state`, `page-header`, `section-label`, `nero-brand`, `mobile-nav`, `nero-character-state`, `nero-error-card` |
| `components/landing/` | Landing-page sections and visuals, used only by `app/page.tsx`: `landing-nav`, `parallax-controller`, `scroll-cue`, `section-heading`, `nero-*-section`/`-visual`/`-figure`, `problem-section`, `student-section`, `consultancy-section`, `discover-jobs-section`, `resume-intelligence-section` |
| `components/jobs/` | Job feature components for the Jobs page: `job-details`, `job-priority-list`, `job-decision-panel`, `gap-analysis-section`, `source-attribution-link` |
| `components/resume/` | Resume feature components: `general-resume-section` (Resume page), `resume-improvement-section` and `resume-version-selector` (Jobs page) |
| `components/ui/button.tsx` | shadcn button; currently not imported anywhere |
| `lib/` | API clients, types and pure helpers. `api.ts` (`apiRequest`, and the shared transport primitives below), `auth.ts`, `jobs.ts`, `job-*.ts`, `general-resume.ts`, `resumes.ts` (including `authenticatedRequest` and `fetchResumeVersionFile`, used by the Resume page), `profile.ts` and `preferences.ts` (Settings page), `applications.ts`, `dashboard.ts`, `nav-items.ts`, `utils.ts`. Pages call the API through `lib/`, not directly (AJI-033) |

Note that `resume-intelligence-section.tsx` is a landing-page section,
not the Resume Intelligence feature. The jobs and resume pages keep many
sub-components inline (`app/(app)/jobs/page.tsx` is the largest file in
the frontend).

### Frontend request transport (AJI-035)

`apps/web/lib/api.ts` holds two shared low-level primitives that every
JSON/Blob-returning client in `lib/` is built on — `grep -rn "fetch("
apps/web/lib` finds raw `fetch()` calls only in this one file:

- **`requestJson(url, options)`** — `fetch` plus a safe
  `.json().catch(() => null)` parse. It takes a fully-assembled URL and
  `RequestInit` and returns `{ response, data }` without throwing on a
  non-ok HTTP response; only a genuine transport failure (network error,
  or a caller's own `AbortController` firing) throws, unmodified. It has
  no opinion on auth headers, timeouts, base-URL/env resolution, or what
  counts as success — those stay with each caller, on purpose, since they
  differ across clients (see below).
- **`blobRequest(url, options, errorMessage)`** — the separate Blob
  transport for file responses, which must never be JSON-parsed. On a
  non-ok response it throws `ApiError(errorMessage, status)` using the
  caller-supplied message, never the backend's own error detail.

`apps/web/lib/auth.ts` holds one shared, "silent, optional auth" header
builder, `authHeaders()`: no token means `{}` (the request proceeds
unauthenticated) rather than an error. `lib/jobs.ts`, `lib/profile.ts`,
`lib/preferences.ts`, `lib/general-resume.ts` and
`lib/resumes.ts::fetchResumeVersionFile` all build on it instead of each
defining or inlining their own copy. `lib/applications.ts`,
`lib/dashboard.ts` and `lib/job-discovery.ts` deliberately keep their own,
different, throwing behavior ("Not authenticated" when signed out) —
that is an intentional second contract, not leftover duplication, and was
not touched.

**What stayed deliberately different, per capability, even after this
consolidation** — none of this was "cleanup," each is a preserved,
observable behavior:

| Client | Timeout | Thrown error type |
|---|---|---|
| `apiRequest` (`api.ts`) | optional per-call `timeoutMs`, none by default | `ApiError` (carries `status`) |
| `lib/jobs.ts`'s `getJobs` | 20s (fixed) | `ApiError`, via `apiRequest` |
| `lib/jobs.ts`'s `submitJob` | 300s (fixed) | `ApiError`, via `apiRequest` |
| `lib/jobs.ts`'s other 10 functions (Job/Requirement Intelligence, Eligibility, ATS, Job Match, Gap Analysis) | none | plain `Error` (no status), or `ResumeImprovementError(message, code)` for the three Resume Improvement calls |
| `lib/general-resume.ts` | 150s (fixed, not configurable) | `GeneralResumeError(message, code, status)` |
| `lib/resumes.ts::fetchResumeVersionFile` | none | `ApiError` with a fixed generic message, never the backend's own detail |

`lib/jobs.ts` also keeps its own `API_BASE_URL` constant
(`process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`, `||`),
separate from `api.ts`'s `API_URL` (`?? "http://localhost:8000"`, `??`).
`requestJson` takes a full URL rather than owning env resolution itself,
so this divergence did not need to be resolved to share the fetch
mechanics — it is unchanged, not overlooked.

## 8. Tests

**Backend** (`tests/`, pytest). This is one flat folder of `test_*.py`
files. The prefix tells you the layer:
- `test_jobs_*_api.py`, `test_*_api.py`: HTTP tests through `TestClient`
- `test_*_service.py`: database-level tests
- engine, contract, validator and provider modules: pure unit tests
- `test_ai_evaluation_*.py`: AJI-031, including the regression check
  against the committed baseline

`tests/conftest.py` provides the `db` fixture. Each test runs inside a
transaction that is always rolled back.

**`tests/support/`** holds shared test infrastructure (AJI-032B). A
helper goes here only when more than one test module uses it.

| Module | Contents | Used by |
|---|---|---|
| `general_resume.py` | AJI-027 resume texts, `FakeProvider`, `make_user`, `make_version` | `test_general_resume_*`, `test_resume_general_assessment_api` |
| `job_discovery.py` | AJI-028 synthetic paged source (test double) | `test_job_expiration`, `test_job_source_contract` |
| `requirement_intelligence.py` | `ri_skill_item`, `make_requirement_intelligence` | ATS Alignment, Gap Analysis and Resume Improvement service tests; the ATS / Requirement Intelligence integration test |

Rules for `tests/support/`: do not import `apps.api.main` or routers,
and do not name a module `test_*`. Test modules should import shared
helpers from here, never from another test module.

**Frontend**: vitest tests sit next to the code they test (`*.test.ts` in
`lib/`, `*.test.tsx` next to components and pages). The node environment
is the default; component tests opt into jsdom with a file comment.

## 9. Dependency direction

```
routers  ->  apps/api/services (orchestration, AI capabilities)  ->  services/ (domain engines)  ->  services/skills
                         \-> models, config
services/ai_evaluation   ->  apps/api/services (evaluation consumes production code)
tests/support            ->  models, services (never routers)
```

- Routers handle HTTP (parsing, auth, status codes, serialization) and
  call services. No service imports a router.
- Orchestration services load and store rows and call the pure engines.
- Domain engines take plain inputs and return plain results.
- AI capability packages own their prompts, schemas, providers and
  validation. AI output never overrides the deterministic safety checks.
- There are no import cycles.

## 10. Not reorganized yet (intentional)

The following were reviewed in AJI-032A and deliberately left in place.
Moving them would put protected work or path-sensitive code at risk.

- **Job discovery, AJI-028, AJI-030** (`services/job_discovery/**`,
  `job_discovery_service.py`, `job_access.py`): protected, including the
  persistence/pipeline import of `apps.api.models`.
- **AI evaluation, AJI-031** (`services/ai_evaluation/**`, baselines,
  dataset): protected. It imports production modules by path, including
  `job_intelligence.validator._evidence_supported`.
- **AI capability packages and flat `*_service.py` modules**: tests patch
  them by module path, and AJI-031 imports them.
- **`resume_service.py`**: its upload directory is derived from its own
  file location.
- **`models.py`, `schemas.py`, `alembic/`, `config.py`.**

Follow-up opportunities, not done here, each requiring its own ticket and
Project Owner approval:
- Share one OpenAI call helper and one evidence-grounding helper across
  the AI capabilities. Each capability's current `max_retries` must be
  kept, or deliberately changed.
- Consolidate the remaining per-file test builders (`_make_user`,
  `_make_job`, auth headers, `_make_resume_version`, discovery settings).
  Their variants differ, for example some create a `Profile`.
