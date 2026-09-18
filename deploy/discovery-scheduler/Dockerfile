# Job Discovery scheduler: a minimal container whose only job is to call
# the existing POST /internal/job-discovery/run endpoint on an interval.
# See run_scheduler.sh for why this is a plain loop and not cron/Celery/
# a task queue.
FROM alpine:3.20

RUN apk add --no-cache curl

COPY run_scheduler.sh /usr/local/bin/run_scheduler.sh
RUN chmod +x /usr/local/bin/run_scheduler.sh

ENTRYPOINT ["/usr/local/bin/run_scheduler.sh"]
