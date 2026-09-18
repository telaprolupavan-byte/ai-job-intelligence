from __future__ import annotations

import json
import urllib.error
import urllib.request


class EvalHttpError(RuntimeError):
    """Raised when an eval adapter's HTTP call to a candidate provider fails."""


def get_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 15.0):
    request = urllib.request.Request(
        url,
        headers=headers or {"Accept": "application/json"},
    )

    return _read_json_response(request, timeout=timeout)


def post_json(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
):
    merged_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    merged_headers.update(headers or {})

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=merged_headers,
        method="POST",
    )

    return _read_json_response(request, timeout=timeout)


def _read_json_response(request: urllib.request.Request, *, timeout: float):
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise EvalHttpError(f"Unable to reach {request.full_url}: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise EvalHttpError(f"{request.full_url} returned invalid JSON.") from exc
