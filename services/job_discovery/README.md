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
(a `cron` entry, the hosting platform's native scheduled-task/cron
feature, or a scheduled CI workflow) that calls it, e.g.:

```
# crontab -e, on whatever host/runner can reach the API
0 */6 * * * curl -fsS -X POST https://api.your-domain.example/internal/job-discovery/run \
  -H "X-Discovery-Trigger-Token: $JOB_DISCOVERY_TRIGGER_TOKEN"
```

This was chosen over adding an in-process scheduler, a task queue
(Celery/RQ), or a message broker (Redis/Kafka) because:
- The current deployment (`docker-compose.yml`: one `api` container, one
  `db` container) has no existing worker/queue infrastructure, and
  discovery for one board is a single, fast, synchronous HTTP call — it
  does not need background execution, retries-with-backoff infrastructure,
  or horizontal worker scaling at this stage.
- An external scheduler keeps "when to run" (an ops concern that changes
  per environment/cadence) out of the application's own deployment
  unit — no code change is needed to change the schedule, add a second
  board, or pause discovery.
- If/when discovery needs to run against many boards on independent
  schedules, retry failed fetches with backoff, or run as a true
  background job decoupled from a request/response cycle, that is the
  point to introduce a task queue — not before there is more than one
  board to ingest.
