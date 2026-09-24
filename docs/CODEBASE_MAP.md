# Codebase Map

A navigation guide for developers (AJI-032B). It describes where things
live today and which boundaries to respect. It does not propose a new
architecture. For each ticket's scope and history, see
`docs/ARCHITECTURE.md` and `docs/TICKETS.md`.

## 1. Repository layout

| Path | What it is |
|---|---|
| `apps/api/` | FastAPI backend: routers, orchestration services, AI capability packages, models, migrations |
| `apps/web/` | Next.js frontend |
| `services/` | Deterministic domain engines and offline tooling, mostly DB-free |
| `tests/` | Backend pytest suite, plus shared helpers in `tests/support/` |
| `deploy/discovery-scheduler/` | The scheduler container: a shell loop that calls the discovery trigger endpoint |
| `docs/` | Architecture record, ticket register, AI evaluation baseline, this map |
| `alembic.ini`, `docker-compose.yml` | Migration config and the local/deploy stack (`api`, `discovery-scheduler`) |

## 2. Backend (`apps/api`)

| Path | Responsibility |
|---|---|
| `main.py` | App factory; mounts every router |
| `routers/` | HTTP layer, one module per area: `auth`, `profile`, `preferences`, `resumes`, `general_resume`, `dashboard`, `jobs`, `job_discovery`, `applications` |
| `services/*.py` | Orchestration services, one per feature: `ats_alignment_service`, `job_match_service`, `eligibility_service`, `priority_ranking_service`, `application_service`, `job_discovery_service`, `job_listing`, `job_access`, `resume_service`, `resume_parser`, `resume_validation`, `resume_fingerprint`, `email_service` |
| `services/<package>/` | Capability packages (see section 4), plus `job_submission/` (AJI-022) and `resume_improvement/` (AJI-021) |
| `models.py` | All SQLAlchemy models, in one module |
| `schemas.py` | Pydantic request/response schemas (the API contracts) |
| `alembic/versions/` | Migrations. There is one head, and CI checks it |
| `config.py` | `Settings` from the environment: database, JWT, AI provider and timeouts, discovery provider/token |
| `security.py` | Password hashing, reset tokens, JWT create/decode |
| `dependencies.py` | `get_db`, `get_current_user`, `get_optional_current_user` |
| `rate_limit.py` | In-memory rate limiting for sensitive auth endpoints |
| `database.py` | Engine and `SessionLocal` |

`routers/jobs.py` (about 1,270 lines, 18 endpoints) holds every per-job
endpoint: search, detail, submit, eligibility, intelligence, requirement
intelligence, match, ATS, gap analysis, resume improvement and priority.

## 3. Deterministic domain engines (top-level `services/`)

These are mainly pure, offline domain engines. Given the same input, they
give the same result, with no AI and usually no database.

| Package | Role |
|---|---|
| `skills/` | Canonical skill identity and normalization, shared by resume, job and ATS code |
| `job_matching/` | Requirement extraction, skill normalization, matcher, scorer, evidence, resume adapter, `JobMatchingService` |
| `ats_alignment/` | ATS scoring engine: weights, components, resume adapter |
| `eligibility/` | Hard Eligibility engine: job signals, location |
| `priority_ranking/` | Job priority ordering (AJI-025) |
| `job_discovery/` | Discovery pipeline and adapters (see section 5) |
| `provider_scorecard/` | Offline provider comparison workflow and evaluation adapters (AJI-018) |
| `ai_evaluation/` | Offline AI evaluation framework, dataset and baselines (AJI-031) |

**Known exceptions.** These packages depend on application code:

- `job_discovery/persistence.py` and `job_discovery/pipeline.py` import
  `apps.api.models` (`Job`, `Company`), because they write jobs.
- `ai_evaluation/` imports the production AI capability packages
  (`pipelines.py`, `runner.py`, `grounding.py`,
  `evaluators/general_resume.py`) so that it evaluates the real code
  paths. It is a consumer, not a dependency, of the app.

Dependencies also run the other way: `apps/api` capability packages import
`services.skills`, `services.job_matching` and `services.eligibility`, and
`job_intelligence` also imports `services.job_discovery`.

## 4. AI capability packages (`apps/api/services/`)

Each package follows the same layout: `contracts.py` (Pydantic result
schema), `deterministic.py` or `engine.py` (non-AI evidence), `prompts.py`,
`interpreter.py`, `validator.py` (evidence grounding),
`providers/factory.py` + `providers/openai_provider.py`, and
`service.py` (orchestration and persistence).

| Package | Responsibility |
|---|---|
| `resume_ai/` | Resume Intelligence (AJI-005/010). Deterministic resume analysis plus an AI interpretation per resume version. Its deterministic module is reused by Job Match and General Resume |
| `job_intelligence/` | Job Intelligence (AJI-012). Structured job semantics from a JD. Deterministic extraction comes first, then AI with evidence validation. Job Match reads it (AJI-014) |
| `requirement_intelligence/` | Requirement Intelligence (AJI-020A/B). Per-user, per-job requirement items, relationships and screening constraints. ATS Alignment scores against it (AJI-020C). `persistence_service.py` owns the stored snapshot |
| `gap_analysis/` | Gap Analysis (AJI-015). Selects gap candidates from the ATS Alignment result and adds AI job-specific suggestions |
| `general_resume/` | General Resume Intelligence (AJI-027). Job-independent score (`scoring.py`), resume-level improvements, approve/reject, `Refined N` versions, recheck and readiness. The AI provider only explains the improvements |

These packages are **intentionally not consolidated**. The provider,
factory and interpreter code is repeated across them. Section 10 lists this
as a follow-up.

## 5. Job discovery

The flow from source to downstream features:

1. **Provider abstraction.** `services/job_discovery/sources/base.py`
   defines the adapter contract: fetch raw records, then normalize each one.
2. **Adapters.** `sources/greenhouse.py` (real, but needs a configured
   board), `sources/test_fixture.py` (tests and local development), and
   `sources/development_dataset.py` + `.json` (AJI-030 synthetic U.S.
   dataset). `sources/non_production.py` is the single set of source values
   that are never production data.
3. **Shared HTTP.** `source_http.py` provides retry, backoff and throttling.
   `pagination.py` provides bounded paging (both AJI-028).
4. **Normalization.** `normalizer.py`.
5. **Validation.** `validator.py`.
6. **Deduplication.** `deduplicator.py`.
7. **Persistence.** `persistence.py` writes `Job`/`Company`, including
   `expires_at`. `attribution.py` is the source attribution registry.
8. **Orchestration and runs.** `pipeline.py` chains the steps.
   `apps/api/services/job_discovery_service.py` resolves the configured
   provider and records a `DiscoveryRun` row for each run.
   `routers/job_discovery.py` exposes `POST /internal/job-discovery/run`
   (token-protected) and a user-facing status endpoint.
9. **Scheduler.** `deploy/discovery-scheduler/run_scheduler.sh` calls that
   trigger on an interval (6 hours by default). It is not a second
   execution path.
10. **Downstream.** `routers/jobs.py` handles search and detail
    (`job_listing`, `job_access`). From there the flow goes to Job
    Intelligence, Requirement Intelligence, Eligibility, Job Match, ATS,
    Gap Analysis and Resume Improvement, then priority ranking, then
    Application Tracking (`application_service`, `routers/applications.py`).
    User-submitted jobs enter through `services/job_submission/`.

See `services/job_discovery/README.md` for provider research status and
rules.

## 6. Resume flow

| Step | Where |
|---|---|
| Upload and storage | `routers/resumes.py`, then `services/resume_service.py` (file checks, `store_resume_file`, `resolve_stored_file`) |
| Parsing | `services/resume_parser.py` |
| Validation | `services/resume_validation.py` |
| Fingerprinting | `services/resume_fingerprint.py` (`compute_content_fingerprint`, used for versioning and idempotency) |
| Deterministic analysis | `services/resume_ai/deterministic.py` |
| AI resume check | `services/resume_ai/service.py` |
| General resume intelligence | `services/general_resume/`, `routers/general_resume.py` |
| Job-specific improvement | `services/resume_improvement/` (approve, recheck, new resume version) |
| Matching integration | `services/job_match_service.py` with `services/job_matching/resume_adapter.py`, and `services/ats_alignment/resume_adapter.py` |

## 7. Frontend (`apps/web`)

- **Next.js App Router** in `app/`. The public pages are `page.tsx`
  (landing), `login`, `register`, `forgot-password` and `reset-password`.
  The authenticated pages sit under the `(app)` route group:
  `layout.tsx` + `auth-gate.tsx`, then `dashboard` (with its own
  `components/`), `jobs` (+ `jobs/submit`), `resume`, `ats`,
  `applications` (+ `[id]`) and `settings`.
- **`components/app/`** holds a flat mix of app feature sections (such as
  `gap-analysis-section`, `general-resume-section`, `job-details`,
  `job-priority-list`, `resume-improvement-section`), shared layout and
  state primitives (such as `panel`, `page-header`, `empty-state`,
  `error-state`, `skeleton`) and landing-page sections (the `nero-*`
  sections, plus `problem-section` and `student-section`).
- **`components/ui/`** holds shadcn-style primitives. Today it contains
  only `button.tsx`.
- **`lib/`** holds API clients per domain, built on `api.ts`
  (`apiRequest`, `ApiError`): `jobs`, `job-search`, `job-discovery`,
  `job-decision`, `job-priority`, `resumes`, `general-resume`,
  `applications`, `dashboard` and `auth`. It also holds helpers
  (`job-format`, `nav-items`, `utils`).
- The frontend is **not reorganized** by this ticket.

## 8. Tests

**Backend** (`tests/`, pytest). `conftest.py` puts the repo root on
`sys.path`. It also provides a `db` fixture, which is a session inside a
SAVEPOINT that is always rolled back, and it resets rate limits. Tests are
flat `test_<area>_<aspect>.py` files and need Postgres at `DATABASE_URL`
(CI runs `alembic upgrade head` first).

**`tests/support/`** holds shared test infrastructure (added in AJI-032B).
Import from here instead of from another `test_*.py` module.

| Module | Contents | Used by |
|---|---|---|
| `general_resume.py` | AJI-027 resume texts (`STRONG_RESUME`, `WEAK_RESUME`, `WEAK_BULLET_*`), `FakeProvider`, `make_user`, `make_version` | `test_general_resume_*`, `test_resume_general_assessment_api` |
| `job_discovery.py` | AJI-028 synthetic paged provider (`ExamplePagedSource`, `PagedTransport`, `example_record`). Never registered with the app | `test_job_source_contract`, `test_job_expiration` |
| `requirement_intelligence.py` | `make_requirement_intelligence` (validated through the real contract), `ri_skill_item`, `ri_experience_item` | ATS Alignment, RI integration, Gap Analysis, Resume Improvement tests |
| `job_intelligence.py` | `make_job_intelligence`, `skill_item`, `experience_item` (legacy `JobIntelligence` rows) | ATS Alignment, Gap Analysis, Job Match reconciliation tests |

Rules for `tests/support/`: helpers may import models, contracts and
services, but never routers or `apps.api.main`. Keep the modules
lightweight, and move a helper here only when more than one test module
shares it.

**Frontend.** Vitest (`npm test`) uses `*.test.ts(x)` files placed next to
their code in `app/`, `components/app/` and `lib/`. CI also runs `tsc`,
`eslint` and `next build`.

## 9. Architectural boundaries

- **Routers** handle HTTP only: auth dependencies, request parsing, error
  mapping. They delegate to services.
- **`apps/api/services`** holds application and orchestration logic:
  database access, versioning and idempotency, and cross-feature wiring.
- **Top-level `services/`** holds reusable deterministic domain logic.
  Keep it free of `apps.api` imports, apart from the exceptions in
  section 3.
- **AI capability packages** hold capability-specific AI logic: contract,
  prompts, provider, interpreter, validator. Their deterministic evidence
  comes first, and AI output is validated against it.
- **`tests/support/`** holds shared test infrastructure and never
  imports routers.

## 10. Not reorganized yet, and follow-ups

These areas were left as they are on purpose. Each needs its own ticket.

- **AI infrastructure.** The five capability packages each have their own
  `providers/factory.py`, `openai_provider.py` and interpreter code.
  Consolidating them is a future ticket.
- **`routers/jobs.py`** is large and holds every per-job feature. It has
  not been split yet.
- **`models.py` and `schemas.py`** are single modules.
- **Frontend.** `components/app/` mixes landing, layout and feature
  components. The `lib/` API clients have not been consolidated.
- **Test factories.** `_make_user`/`make_user` (24 definitions),
  `make_job`/`_make_job` (20), `_auth_headers`/`_auth`, `make_resume_version`
  and `_discovery_settings` are still repeated in each test module. They
  differ in small ways (email prefixes, profile or preference rows,
  defaults), so combining them needs a semantics check. A future ticket
  can move them into `tests/support/`.
- **Other repeated test doubles.** Per-module `FakeProvider`,
  `FakeJobIntelligenceProvider`, `FakeGapAnalysisProvider` and
  `FailingProvider` classes, and the shared `client` fixture (defined 23
  times), are candidates for `tests/support/`.
- **Protected areas** (AI prompts and behavior, `services/ai_evaluation/`,
  Job Discovery implementation (AJI-028/030), models and migrations, API
  contracts, auth, frontend, Docker, CI): change these only under a ticket
  that is scoped for them.
