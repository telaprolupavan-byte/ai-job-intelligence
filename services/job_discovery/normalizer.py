from __future__ import annotations

import re
from urllib.parse import urlsplit


EMPLOYMENT_TYPE_ALIASES = {
    "full time": "full_time",
    "full-time": "full_time",
    "fulltime": "full_time",
    "full_time": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
    "parttime": "part_time",
    "part_time": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "contract position": "contract",
    "contract work": "contract",
    "internship": "internship",
    "intern": "internship",
    "temporary": "temporary",
    "temp": "temporary",
}


REMOTE_TYPE_ALIASES = {
    "remote": "remote",
    "fully remote": "remote",
    "100% remote": "remote",
    "work from home": "remote",
    "wfh": "remote",
    "hybrid": "hybrid",
    "hybrid work": "hybrid",
    "on-site": "onsite",
    "on site": "onsite",
    "onsite": "onsite",
    "in office": "onsite",
}


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = re.sub(r"\s+", " ", value).strip()

    return normalized or None


def normalize_employment_type(value: str | None) -> str | None:
    normalized = normalize_text(value)

    if normalized is None:
        return None

    key = normalized.lower()

    return EMPLOYMENT_TYPE_ALIASES.get(key)


def normalize_remote_type(value: str | None) -> str | None:
    normalized = normalize_text(value)

    if normalized is None:
        return None

    key = normalized.lower()

    return REMOTE_TYPE_ALIASES.get(key)


# Provider URLs are rendered as links in the Jobs UI, so anything other
# than an absolute http(s) URL (e.g. `javascript:`, `data:`, a relative
# path) is treated as unknown rather than stored.
_ALLOWED_URL_SCHEMES = {"http", "https"}


def normalize_url(value: str | None) -> str | None:
    normalized = normalize_text(value)

    if normalized is None:
        return None

    try:
        parts = urlsplit(normalized)
    except ValueError:
        return None

    if parts.scheme.lower() not in _ALLOWED_URL_SCHEMES or not parts.netloc:
        return None

    return normalized