from __future__ import annotations

import re

# Same intent as services.job_discovery.sources.greenhouse's own "only
# accept postings whose location text unambiguously reads as U.S."
# heuristic, but NOT a byte-for-byte copy: that function matches state
# abbreviations as raw substrings (" fl" etc.), which false-positives on
# any word starting with those two letters preceded by a space - e.g. The
# Muse's "Flexible / Remote" location text spuriously matches " fl"
# (Florida). This version tokenizes into whole words first and only
# treats an exact-word match against a state abbreviation as a hit, so
# "Flexible" is never mistaken for "FL". Duplicated (not imported) since
# that function is a private implementation detail of the Greenhouse
# *production* adapter, and this eval-only package should not create a
# dependency on it - see this package's __init__.py docstring.
US_FULL_NAME_MARKERS = {"united states", "usa", "u.s.", "u.s.a."}

US_STATE_ABBREVIATIONS = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    "dc",
}

_WORD_PATTERN = re.compile(r"[a-z]+")


def looks_like_us_location(location: str | None) -> bool:
    if not location:
        return False

    normalized = location.strip().lower()

    if any(marker in normalized for marker in US_FULL_NAME_MARKERS):
        return True

    words = _WORD_PATTERN.findall(normalized)

    return any(word in US_STATE_ABBREVIATIONS for word in words)
