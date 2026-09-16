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
