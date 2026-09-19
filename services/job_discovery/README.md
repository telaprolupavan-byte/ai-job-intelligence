# Job Discovery Pipeline

```
Source Adapter -> Validate -> Deduplicate -> Persist -> GET /jobs -> Frontend
```

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

Adding another provider (e.g. Lever) means implementing the same
`JobSourceAdapter` interface (`services/job_discovery/sources/base.py`) and
reusing the existing normalizer/validator/deduplicator/persistence/pipeline —
no source-specific logic belongs in the generic pipeline.

## TheirStack source adapter (AJI-021)

`services/job_discovery/sources/theirstack.py` calls the TheirStack Jobs
Search API (`POST https://api.theirstack.com/v1/jobs/search`), a paid,
authenticated, cross-company search API — unlike Greenhouse's
unauthenticated per-company board API. It is enabled independently of
Greenhouse and goes through the exact same
normalize/validate/deduplicate/persist pipeline once it has produced
`DiscoveredJob`s; nothing in the pipeline is TheirStack-specific.

**Field-mapping disclaimer:** this environment's outbound network access
could not reach `theirstack.com` while building this adapter, so the
per-job response field names in `_to_discovered_job` (`job_title`/`title`,
`company.name`/`company_name`, `url`/`final_url`, `date_posted`, `remote`,
`employment_statuses`, …) are based on TheirStack's published
documentation and third-party integration write-ups, not a live response
inspected directly. The adapter is written defensively — a missing or
renamed field always comes through as `None` (then rejected by the
existing validator if required) rather than a fabricated value — but the
exact field names should be confirmed against one real response before
relying on TheirStack data quality in production. See "Real local
discovery run" below for how to do that.

Configuration (all read from `apps.api.config.settings`, `.env`/
environment variables — see `.env.example`):

| Variable | Purpose | Default |
|---|---|---|
| `THEIRSTACK_ENABLED` | Turns the provider on/off independently of Greenhouse. | `false` |
| `THEIRSTACK_API_KEY` | Bearer token for the TheirStack API. Server-side only — never read by frontend code, never included in an API response, log line, database row, or git commit. | unset |
| `THEIRSTACK_MAX_RESULTS` | Hard ceiling on jobs fetched in one discovery run for this provider. Discovery never pulls an unbounded number of results. | `50` |
| `THEIRSTACK_PAGE_SIZE` | Results requested per search page (paginates up to `THEIRSTACK_MAX_RESULTS`). | `25` |
| `THEIRSTACK_TIMEOUT_SECONDS` | Per-request HTTP timeout. | `15` |
| `THEIRSTACK_MAX_RETRIES` | Bounded retries for transient failures (timeouts, HTTP 5xx, HTTP 429) only. Authentication/configuration errors (401/403) are never retried. | `2` |
| `THEIRSTACK_POSTED_AT_MAX_AGE_DAYS` | TheirStack requires at least one search filter per request; this lets discovery run without pinning to a specific company/domain. | `7` |
| `THEIRSTACK_JOB_TITLES` | Optional comma-separated job title filter (`job_title_or`). | unset (unfiltered) |
| `THEIRSTACK_COUNTRY_CODES` | Comma-separated country codes (`job_country_code_or`). Defaults to `US` since the existing validator only accepts United States jobs today. | `US` |

If `THEIRSTACK_ENABLED=true` but `THEIRSTACK_API_KEY` is unset, TheirStack
is skipped for that discovery run (logged as a warning) rather than
blocking Greenhouse — see `build_configured_sources` in
`apps/api/services/job_discovery_service.py`.

### Real local discovery run

With a real `THEIRSTACK_API_KEY`, run discovery against the real API and
confirm jobs appear through the existing `GET /jobs` endpoint:

```bash
# 1. Configure (.env or exported in your shell)
export THEIRSTACK_ENABLED=true
export THEIRSTACK_API_KEY=<your real TheirStack API key>
export THEIRSTACK_MAX_RESULTS=5          # keep a first run small
export JOB_DISCOVERY_TRIGGER_TOKEN=<any long random string>

# 2. Start the API (with a Postgres DB migrated via alembic) and trigger
#    a real discovery run
curl -X POST http://localhost:8000/internal/job-discovery/run \
  -H "X-Discovery-Trigger-Token: $JOB_DISCOVERY_TRIGGER_TOKEN"

# 3. Inspect the run's outcome (per-provider status/counts, never the API
#    key)
curl http://localhost:8000/internal/job-discovery/runs \
  -H "X-Discovery-Trigger-Token: $JOB_DISCOVERY_TRIGGER_TOKEN"

# 4. Confirm the jobs are visible through the existing public endpoint
curl "http://localhost:8000/jobs?page=1&page_size=20" | jq '.jobs[] | select(.source=="theirstack")'
```

A `runs[].source == "theirstack"` entry with `status: "succeeded"` and
`inserted > 0` (step 2/3), together with `theirstack` rows returned from
step 4, is what "real TheirStack jobs are visible through NERO's existing
/jobs API" looks like in practice. If step 4 returns TheirStack jobs with
implausible field values (e.g. every job missing `location` or
`description`), that's the field-mapping disclaimer above surfacing for
real — inspect one raw response body TheirStack returned (temporarily,
outside of any committed file or log) and adjust the field names in
`_to_discovered_job`.

### Known limitations (identified rather than silently worked around)

- **No cross-provider deduplication.** `services/job_discovery/deduplicator.py`
  builds each job's identity fingerprint from `source` + the provider's own
  ID (or `source` + company/title/location/URL as a fallback), and
  `services/job_discovery/persistence.py` always scopes its existing-job
  lookup by `Job.source`. This means dedup only ever happens *within* one
  provider's postings — the same real-world job posted to both a
  Greenhouse board and returned by TheirStack will persist as two separate
  `Job` rows, not one. This is the existing architecture's behavior for
  any two sources, not something introduced by TheirStack, and this
  change does not alter it — inventing a TheirStack-specific merge
  strategy was explicitly out of scope. Real cross-source deduplication
  (e.g. canonicalizing by company + title + location, independent of
  `source`) is a separate, deliberate design decision for a future
  ticket.
- **No stale-job deactivation.** Nothing in the existing pipeline ever
  sets `Job.is_active = False` — a job that stops being returned by its
  source (closed on Greenhouse, or absent from a later TheirStack search)
  stays `is_active=True` forever. This is a pre-existing gap in the
  Greenhouse pipeline too, not one this change introduces or attempts to
  silently patch for TheirStack only.

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
/inserted/updated/rejected counts, and a safe/truncated error message on
failure). `GET /internal/job-discovery/runs` (same trigger-token auth)
returns the most recent runs, newest first, so an operator or the
external scheduler can check run history without grepping application
logs.
