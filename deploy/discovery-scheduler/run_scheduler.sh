#!/bin/sh
# Job Discovery scheduler.
#
# This process does exactly one thing: wait on an interval, then call the
# EXISTING, already-authenticated discovery trigger
# (POST /internal/job-discovery/run) over HTTP using the shared trigger
# token. It is not a second discovery execution path - it knows nothing
# about Greenhouse, normalization, validation, deduplication, or
# persistence. All of that lives in the FastAPI app; this script is only
# "what calls it, and when."
#
# A plain loop (rather than real cron) was chosen because this
# deployment is a single Docker Compose stack with no host-level cron
# and no CI/CD platform already configured (see docs/ARCHITECTURE.md and
# services/job_discovery/README.md) - this is the smallest mechanism
# that is fully self-contained in the existing docker-compose.yml, needs
# no extra OS-level cron daemon quirks to get right, and is directly
# runnable/inspectable as plain POSIX sh.
set -u

DISCOVERY_API_URL="${DISCOVERY_API_URL:-http://api:8000}"
# Initial operational default, not a product requirement - see
# services/job_discovery/README.md. Change via DISCOVERY_INTERVAL_SECONDS.
INTERVAL_SECONDS="${DISCOVERY_INTERVAL_SECONDS:-21600}"
INITIAL_DELAY_SECONDS="${DISCOVERY_INITIAL_DELAY_SECONDS:-30}"

log() {
    printf '%s discovery-scheduler: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

run_once() {
    if [ -z "${JOB_DISCOVERY_TRIGGER_TOKEN:-}" ]; then
        log "JOB_DISCOVERY_TRIGGER_TOKEN is not set - skipping this run (nothing to authenticate with). Will retry next interval."
        return 0
    fi

    url="${DISCOVERY_API_URL}/internal/job-discovery/run"
    body_file="$(mktemp)"

    status=$(curl -sS -o "$body_file" -w '%{http_code}' --max-time 120 -X POST "$url" \
        -H "X-Discovery-Trigger-Token: ${JOB_DISCOVERY_TRIGGER_TOKEN}" 2>>"$body_file")
    curl_exit=$?

    if [ "$curl_exit" -ne 0 ]; then
        log "POST $url failed before completing (curl exit ${curl_exit}) - will retry next interval."
    else
        log "POST $url -> HTTP ${status}"
    fi

    if [ -s "$body_file" ]; then
        log "response body: $(cat "$body_file")"
    fi
    rm -f "$body_file"

    # A failure here - network error, 502/503 from the API (source
    # unreachable, not configured, DB outage), 409 from an overlapping
    # run - is expected operational behavior, not a scheduler crash. Any
    # run the API actually attempted is already recorded as a
    # DiscoveryRun row; this script's only job is to try again at the
    # next interval, which it always does regardless of this outcome.
    return 0
}

log "starting. interval=${INTERVAL_SECONDS}s target=${DISCOVERY_API_URL} (initial operational default - change DISCOVERY_INTERVAL_SECONDS to adjust)"

sleep "$INITIAL_DELAY_SECONDS"

while true; do
    run_once
    sleep "$INTERVAL_SECONDS"
done
