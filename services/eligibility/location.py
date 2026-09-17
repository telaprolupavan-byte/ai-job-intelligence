from __future__ import annotations

from dataclasses import dataclass


# Full state/territory name (lowercase) -> two-letter abbreviation
# (lowercase). Used only for exact, deterministic name<->abbreviation
# resolution — never fuzzy/approximate matching.
US_STATE_ABBREVIATIONS: dict[str, str] = {
    "alabama": "al",
    "alaska": "ak",
    "arizona": "az",
    "arkansas": "ar",
    "california": "ca",
    "colorado": "co",
    "connecticut": "ct",
    "delaware": "de",
    "district of columbia": "dc",
    "florida": "fl",
    "georgia": "ga",
    "hawaii": "hi",
    "idaho": "id",
    "illinois": "il",
    "indiana": "in",
    "iowa": "ia",
    "kansas": "ks",
    "kentucky": "ky",
    "louisiana": "la",
    "maine": "me",
    "maryland": "md",
    "massachusetts": "ma",
    "michigan": "mi",
    "minnesota": "mn",
    "mississippi": "ms",
    "missouri": "mo",
    "montana": "mt",
    "nebraska": "ne",
    "nevada": "nv",
    "new hampshire": "nh",
    "new jersey": "nj",
    "new mexico": "nm",
    "new york": "ny",
    "north carolina": "nc",
    "north dakota": "nd",
    "ohio": "oh",
    "oklahoma": "ok",
    "oregon": "or",
    "pennsylvania": "pa",
    "rhode island": "ri",
    "south carolina": "sc",
    "south dakota": "sd",
    "tennessee": "tn",
    "texas": "tx",
    "utah": "ut",
    "vermont": "vt",
    "virginia": "va",
    "washington": "wa",
    "west virginia": "wv",
    "wisconsin": "wi",
    "wyoming": "wy",
}

US_STATE_NAMES: dict[str, str] = {
    abbreviation: name
    for name, abbreviation in US_STATE_ABBREVIATIONS.items()
}


def _resolve_state(fragment: str) -> str | None:
    """
    Resolve a plain state name or abbreviation to its canonical full name.

    Returns None when the fragment is not exactly a recognized state name
    or abbreviation (never guessed from a partial/fuzzy match).
    """
    normalized = fragment.strip().lower()

    if normalized in US_STATE_ABBREVIATIONS:
        return normalized

    if normalized in US_STATE_NAMES:
        return US_STATE_NAMES[normalized]

    return None


@dataclass
class ParsedLocation:
    raw: str
    city: str | None
    state: str | None


def parse_location(location: str | None) -> ParsedLocation | None:
    """
    Parse a free-form location string into an optional city/state.

    Supports "City, ST", "City, State", a bare state name/abbreviation,
    or a bare city/region name. This is intentionally limited to comma-
    separated "City, State" shapes and exact state resolution — it never
    guesses geography beyond that.
    """
    if not location:
        return None

    normalized = location.strip()

    if not normalized:
        return None

    parts = [part.strip() for part in normalized.split(",") if part.strip()]

    if not parts:
        return None

    city: str | None = None
    state: str | None = None

    if len(parts) >= 2:
        city = parts[0].lower()
        state = _resolve_state(parts[1])
    else:
        state = _resolve_state(parts[0])

        if state is None:
            city = parts[0].lower()

    return ParsedLocation(raw=normalized.lower(), city=city, state=state)


def location_token_matches(
    token: str,
    job_location: str | None,
) -> bool:
    """
    Determine whether a user-configured location token (an accepted or
    excluded location entry) matches a job's location.

    The caller is responsible for handling a missing ``job_location``
    (this function is only meaningful when a job location string is
    present) — it always returns False for a missing/blank location or
    token so a caller cannot accidentally treat "no information" as a
    match.

    Matching rules, in order:
    1. Case-insensitive substring match either direction (covers
       "Remote", multi-word cities, and exact "City, ST" equality).
    2. The token resolves to a US state (by name or abbreviation) that
       equals the job's parsed state — but only when the token does not
       also specify a city, or when it specifies the same city.
    """
    if not job_location or not token or not token.strip():
        return False

    token_norm = token.strip().lower()
    job_raw = job_location.strip().lower()

    if token_norm in job_raw or job_raw in token_norm:
        return True

    token_parsed = parse_location(token)
    job_parsed = parse_location(job_location)

    if token_parsed and job_parsed:
        if (
            token_parsed.state
            and job_parsed.state
            and token_parsed.state == job_parsed.state
        ):
            if token_parsed.city is None:
                return True

            if (
                job_parsed.city is not None
                and token_parsed.city == job_parsed.city
            ):
                return True

    return False
