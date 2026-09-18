"""Minimal in-memory rate limiting for sensitive auth endpoints.

This is a fixed-window limiter keyed by an arbitrary string (typically a
combination of client IP and, where applicable, the target email address)
so that repeated failed attempts against a single account/IP are throttled
without needing an external store (Redis, etc.) for a single-process API.

Not a substitute for a distributed limiter behind a load balancer with
multiple API processes/replicas, but it stops the unbounded brute-force/
account-enumeration case this API previously had zero protection against.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


_attempts: dict[str, list[float]] = defaultdict(list)


def reset_rate_limits() -> None:
    """Clear all recorded attempts. Used by tests for isolation."""
    _attempts.clear()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(
    key: str,
    *,
    max_attempts: int,
    window_seconds: float,
) -> None:
    now = time.monotonic()
    window_start = now - window_seconds

    attempts = _attempts[key]
    attempts[:] = [ts for ts in attempts if ts > window_start]

    if len(attempts) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )

    attempts.append(now)


def rate_limit_login(request: Request, email: str) -> None:
    ip = _client_ip(request)
    enforce_rate_limit(
        f"login:ip:{ip}", max_attempts=20, window_seconds=15 * 60
    )
    enforce_rate_limit(
        f"login:email:{email.lower()}",
        max_attempts=10,
        window_seconds=15 * 60,
    )


def rate_limit_register(request: Request) -> None:
    enforce_rate_limit(
        f"register:ip:{_client_ip(request)}",
        max_attempts=30,
        window_seconds=60 * 60,
    )


def rate_limit_forgot_password(request: Request, email: str) -> None:
    ip = _client_ip(request)
    enforce_rate_limit(
        f"forgot:ip:{ip}", max_attempts=30, window_seconds=60 * 60
    )
    enforce_rate_limit(
        f"forgot:email:{email.lower()}",
        max_attempts=10,
        window_seconds=60 * 60,
    )


def rate_limit_reset_password(request: Request) -> None:
    enforce_rate_limit(
        f"reset:ip:{_client_ip(request)}",
        max_attempts=30,
        window_seconds=60 * 60,
    )
