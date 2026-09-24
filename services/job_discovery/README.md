# Job Discovery Pipeline

```
Provider -> fetch_raw_jobs() -> normalize_raw_job() -> Validate
         -> Deduplicate -> Persist -> GET /jobs -> Frontend
```

AJI-024 formalized the adapter boundary (`sources/base.py`), added the
double-gated synthetic test provider (`sources/test_fixture.py`), and
added per-run `normalized`/`accepted`/`duplicates` counters - see
docs/ARCHITECTURE.md "Job Discovery Product Pipeline (AJI-024)".

AJI-028 added the provider-independent foundation every future approved
source builds on - see "Foundation for new sources (AJI-028)" below. No
new real provider was added or enabled; `JOB_DISCOVERY_PROVIDER` stays
unset by default.

### Local development with the test provider

```
JOB_DISCOVERY_PROVIDER=test_fixture
JOB_DISCOVERY_ENABLE_TEST_PROVIDER=true   # never in production
JOB_DISCOVERY_TRIGGER_TOKEN=<any local secret>

curl -X POST localhost:8000/internal/job-discovery/run \
  -H "X-Discovery-Trigger-Token: <same secret>"
```

The fixture's jobs are synthetic, labelled "Test data" in the UI, and
hidden from every user-facing query once the enable flag is off.

### Development dataset (AJI-030)

`JOB_DISCOVERY_PROVIDER=development_dataset` (same enable flag) loads
`sources/development_dataset.json`: 17 realistic, synthetic U.S. jobs
plus one duplicate and two invalid records, through the same adapter
pipeline. Dates are relative to the run day, so active/expired never go
stale. Every source in `sources/non_production.py::NON_PRODUCTION_SOURCES`
is labelled "Test data" and hidden while the flag is off. See
docs/ARCHITECTURE.md "Job Intelligence Development Dataset (AJI-030)".

## Running the pipeline

```python
from apps.api.database import SessionLocal
from services.job_discovery.pipeline import run_discovery_pipeline
from services.job_discovery.sources.greenhouse import GreenhouseJobSource

source = GreenhouseJobSource(
    board_token="example",       # from https://boards.greenhouse.io/<board_token>
    company_name="Example Inc",
)

db = SessionLocal()
try:
    result = run_discovery_pipeline(db, source.fetch_jobs())
    db.commit()  # the pipeline flushes but does not commit; the caller decides
finally:
    db.close()

print(len(result.inserted), len(result.updated), len(result.rejected))
```

## Greenhouse source adapter

`services/job_discovery/sources/greenhouse.py` reads a company's public,
unauthenticated Greenhouse board API
(`https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`).
No API key or login is required.

Configuration (constructor arguments, not hardcoded):

| Argument       | Description                                                        |
|----------------|----------------------------------------------------------------------|
| `board_token`  | The company's Greenhouse board slug, e.g. `example` for `https://boards.greenhouse.io/example` |
| `company_name` | Display name to store on discovered jobs (Greenhouse's job list does not include it) |

The project does not ship a hardcoded board token — pick a board you have
permission to ingest and pass it in when constructing `GreenhouseJobSource`,
e.g. from an environment variable in whatever script/cron job invokes the
pipeline (suggested names: `GREENHOUSE_BOARD_TOKEN`, `GREENHOUSE_COMPANY_NAME`).

Fields the adapter deliberately leaves `None`/rejects rather than guesses:
- `salary_min` / `salary_max` / `salary_currency` — not present in the public API.
- `country` — only set to `"USA"` when the location text unambiguously
  indicates the U.S. (state abbreviation, "United States", "USA"); otherwise
  the job is rejected by the validator rather than assumed to be U.S.
- `employment_type` / `remote_type` — only populated from the board's own
  custom metadata fields when present; otherwise left `None`.

Adding another (approved) provider means implementing the same
`JobSourceAdapter` interface (`services/job_discovery/sources/base.py`:
`fetch_raw_jobs()` + deterministic `normalize_raw_job()`), adding one
branch to `build_configured_source()`, and reusing the existing
normalizer/validator/deduplicator/persistence/pipeline — no
source-specific logic belongs in the generic pipeline.

## Foundation for new sources (AJI-028)

Everything a new, approved adapter needs, so it only has to map its
provider's records onto `DiscoveredJob`:

| Module | What it provides |
|---|---|
| `source_http.py` | `SourceHttpClient` + `HttpPolicy`: bounded timeout, retry with exponential backoff on 429/500/502/503/504, network errors and timeouts (other 4xx never retried), `Retry-After` (seconds or HTTP-date; a longer wait than `max_retry_after_seconds` fails the request rather than retrying early), response-size cap (declared and actual bytes), a minimum-interval throttle, query strings stripped from every error message, per-attempt logs and `stats`. Every failure is a `SourceHttpError` (a `JobSourceFetchError`), so a run records it as failed/502. |
| `pagination.py` | `fetch_bounded_pages()`: newest first, stops on an empty or short page, and never reads more than `MAX_PAGES_PER_RUN = 5` pages per run (the approved ceiling - a code constant, not a setting). A failed page fails the run; nothing is half-written. |
| `attribution.py` | `SourceAttribution` registry keyed by `source`: display name, homepage, and whether the source's terms require a visible link back. The API returns it per job as `source_attribution`; the Jobs UI shows "Job via X" (linked to the posting) only when required. Every real provider must be registered; the test fixture is not. |
| `persistence.py` + `jobs.expires_at` | The provider-stated closing time is stored (naive UTC) and mirrored on every sighting. |
| `apps/api/services/job_access.py::active_jobs_filter()` | The one definition of an open job: `is_active` and not past `expires_at`. Used by GET /jobs, GET /jobs/priority (through `job_listing_query`) and the dashboard. |

Rules that come with it (see `sources/base.py`):

- `expires_at` is set only from an expiry the provider states. Nothing
  infers that a posting closed because a run did not see it, and there is
  no "not seen for N days" rule.
- Expiry is enforced at query time; an expired job remains readable by id
  (e.g. from an application the user is tracking).
- U.S. eligibility must be explicit in the provider's data. A worldwide
  posting with no location restriction is not treated as U.S.-eligible.
- A confirmed remote-only source may set `remote_type="remote"`.
- An eventual source should initially pull its newest explicitly
  U.S.-eligible jobs, with no keyword filtering.
- The scheduler interval is unchanged (every 6 hours).

`tests/job_discovery_fakes.py` has a synthetic paged adapter built only
from these pieces; `tests/test_job_source_contract.py` runs one contract
over every adapter (Greenhouse, the test fixture, and that double).

### Source research status (not approved)

AJI-028 researched zero-cost sources against the Product Owner's
constraints ($0, no business/provider account, no paid provider, no
scraping, and automated access and use must be permitted for NERO's use
case - publicly visible is not the same as permitted). Findings came from
search excerpts of each provider's official pages; the sandbox that did
the research could not reach the provider sites directly, so **none of
this is verified and none of it justifies production use**:

| Source | Finding | Status |
|---|---|---|
| Himalayas API | Documented, free, no key; display in your own app allowed with a visible link back and credit; no resubmission to other job boards; 60 req/min, 20 jobs/request; states an expiry date. Full terms (storage, AI processing, signup-gated display) not yet read. | **Not approved.** Candidate for a future provider ticket once the full terms are reviewed. |
| USAJOBS API | Free key, but terms tie data use to "the requesting company identified on the … Registration Form" and restrict derivative works. | Not pursued. |
| The Muse API | Free; link back required; storage/AI use unclear; no employment type or salary. | Not pursued. |
| Remotive, Jobicy | Terms forbid showing their jobs behind a signup/login. | Excluded. |
| Greenhouse / Lever / Ashby boards | Public, but documented as the employer's own careers-site tool. | Only with the specific employer's permission. |
| CareerOneStop / NLx, Adzuna, Jooble, paid APIs, LinkedIn/Indeed/Google Jobs | Organization approval, business programs, cost, or no permitted API. | Excluded. |

## Operationalizing discovery (running it without a developer manually
## invoking Python)

Until this was addressed, this pipeline existed and was fully unit-tested
but nothing in the running application ever called it — the only
documented invocation path was the manual snippet above. That gap is now
closed by `apps/api/services/job_discovery_service.py` (the DB-touching
orchestration layer, mirroring every other `*_service.py` in this
codebase) and `POST /internal/job-discovery/run`
(`apps/api/routers/job_discovery.py`).

**Configuration** (`.env`, see `.env.example`):

| Variable | Purpose |
|---|---|
| `JOB_DISCOVERY_GREENHOUSE_BOARD_TOKEN` | Which company's Greenhouse board to ingest. **Unset by default** — which real company's postings AJI has permission to aggregate is a product/legal decision, not the Builder's to make by hardcoding a company into shared config. |
| `JOB_DISCOVERY_GREENHOUSE_COMPANY_NAME` | Display name stored on discovered jobs. |
| `JOB_DISCOVERY_TRIGGER_TOKEN` | Shared secret required in the `X-Discovery-Trigger-Token` header. There is no admin/role concept on `User` to gate this endpoint with instead — it is a system-to-system credential for whatever calls it (cron, a platform scheduled task), never handed to a user. |

The endpoint is a hard `503` until both the source and the trigger token
are configured — it never runs with an implicit/guessed source, and it
never returns a fabricated "success" when unconfigured or when the
upstream board can't be reached (a real fetch failure surfaces as `502`
with the underlying error, e.g. DNS/timeout/HTTP-status details).

**Trigger mechanism — the trade-off that was made:** the smallest
mechanism that satisfies "must eventually support scheduled/controlled
discovery without requiring a developer to manually run a Python
snippet" is an authenticated HTTP endpoint plus an *external* scheduler
that calls it. That scheduler is now implemented as its own tiny service
in `docker-compose.yml` (`discovery-scheduler` — see
`deploy/discovery-scheduler/`, AJI-017.1): a minimal Alpine container
running `run_scheduler.sh`, a plain POSIX-sh loop that does nothing but
`sleep`, then `curl -X POST .../internal/job-discovery/run` with the
same `JOB_DISCOVERY_TRIGGER_TOKEN` the `api` service is configured with,
forever. It is not a second discovery execution path — it only calls the
one existing endpoint, exactly as an operator's own crontab entry would:

```
# what discovery-scheduler does every DISCOVERY_INTERVAL_SECONDS (21600 = 6h by default)
curl -fsS -X POST http://api:8000/internal/job-discovery/run \
  -H "X-Discovery-Trigger-Token: $JOB_DISCOVERY_TRIGGER_TOKEN"
```

If you'd rather use your platform's own scheduled-task feature or a
`cron` entry on a host that can reach the API instead of the bundled
`discovery-scheduler` container, that continues to work unchanged — the
container is just the default so discovery runs automatically out of the
box with `docker compose up`, without an operator having to set up
scheduling themselves. Either way the initial frequency (every 6 hours)
is an operational default, not a product requirement — change
`DISCOVERY_INTERVAL_SECONDS` (or your own cron expression) per
environment without a code change.

**Why a plain loop, not cron-inside-the-container:** real cron
(`crond`) was the first option considered, since it's the standard
"platform-native" primitive for scheduled execution on Linux. It was set
aside in favor of a plain `while true; do …; sleep …; done` loop because
env-var propagation from a container's process environment into a cron
job's environment is a well-known footgun (`crond` does not hand its own
environment to jobs it spawns) that adds real failure surface for no
benefit here — this scheduler has exactly one job to run, so a loop that
inherits the container's environment directly is simpler and strictly
more predictable than getting cron's environment handling right for a
one-line crontab.

**Why not Redis/Celery/Kafka/RabbitMQ/Kubernetes/a worker fleet:** none
of that is justified by what this scheduler actually needs to do — wait
on an interval, then make one outbound HTTP call. `discovery-scheduler`
doesn't touch the database, doesn't know about Greenhouse, and doesn't
retry with backoff
(a failed call just waits for the next interval, and the failure is
already recorded as a `DiscoveryRun` row by the API). Introducing a
broker or task queue for that would add real operational surface (a
broker to run and monitor, worker processes, retry/dead-letter handling)
that nothing here needs yet. Revisit when there is more than one board to
schedule independently, or when a failed fetch needs automatic
retry-with-backoff rather than waiting for the next scheduled run.

**Concurrency — avoiding overlapping runs:** `run_configured_discovery`
(`apps/api/services/job_discovery_service.py`) is guarded by an
in-process `threading.Lock`, so a second trigger (the scheduler firing
while a manual trigger is still in flight, or a misconfigured second
scheduler) is rejected with `409` rather than running concurrently. A
plain in-process lock is correct *only* because `api` runs as a single
uvicorn worker process (see `apps/api/Dockerfile` — no `--workers` flag);
scaling `api` to multiple worker processes or containers would require
replacing this with a DB-level lock (e.g. a Postgres advisory lock)
instead of reaching for distributed-locking infrastructure. Separately,
`discovery-scheduler` itself is a single sequential loop, so it can never
overlap with itself by construction — the lock exists for *other*
callers of the same endpoint, not to protect against the scheduler.

**Observability:** every invocation of `POST /run` records one
`DiscoveryRun` row (source, status, started/completed timestamps, fetched
/normalized/inserted/updated/rejected/duplicate counts, and a safe/truncated error message on
failure). `GET /internal/job-discovery/runs` (same trigger-token auth)
returns the most recent runs, newest first, so an operator or the
external scheduler can check run history without grepping application
logs.
