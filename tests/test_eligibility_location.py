from services.eligibility.location import location_token_matches, parse_location


def test_parse_location_city_state_abbreviation():
    parsed = parse_location("Newark, NJ")

    assert parsed.city == "newark"
    assert parsed.state == "new jersey"


def test_parse_location_bare_state_name():
    parsed = parse_location("New Jersey")

    assert parsed.city is None
    assert parsed.state == "new jersey"


def test_parse_location_bare_city_only():
    parsed = parse_location("Remote")

    assert parsed.city == "remote"
    assert parsed.state is None


def test_parse_location_missing_returns_none():
    assert parse_location(None) is None
    assert parse_location("") is None
    assert parse_location("   ") is None


def test_location_token_matches_exact_string():
    assert location_token_matches("Austin, TX", "Austin, TX") is True


def test_location_token_matches_state_name_to_abbreviation():
    assert location_token_matches("New Jersey", "Newark, NJ") is True


def test_location_token_matches_multiple_state_tokens():
    assert location_token_matches("New York", "Newark, NJ") is False
    assert location_token_matches("New Jersey", "Newark, NJ") is True


def test_location_token_same_state_different_city_does_not_match():
    assert location_token_matches("Seattle, WA", "Tacoma, WA") is False


def test_location_token_does_not_match_different_state():
    assert location_token_matches("Seattle, WA", "Austin, TX") is False


def test_location_token_matches_bare_exclusion():
    assert location_token_matches("California", "California") is True


def test_location_token_missing_job_location_never_matches():
    assert location_token_matches("New York", None) is False
    assert location_token_matches("New York", "") is False


def test_location_token_blank_token_never_matches():
    assert location_token_matches("", "Austin, TX") is False
    assert location_token_matches("   ", "Austin, TX") is False


def test_location_token_matches_remote_string_literally():
    # "Remote" as a location string is matched like any other bare
    # token — the location engine does not special-case "remote" (that
    # is services/eligibility's separate remote_arrangement constraint,
    # driven by Job.remote_type, not Job.location).
    assert location_token_matches("Remote", "Remote") is True
    assert location_token_matches("Remote", "Austin, TX") is False


def test_location_token_matches_with_trailing_country_suffix():
    # A job location with an extra trailing segment (e.g. a country)
    # still matches via substring containment.
    assert location_token_matches("Austin, TX", "Austin, TX, USA") is True


def test_parse_location_ignores_extra_trailing_segments_without_crashing():
    # More than two comma-separated segments is malformed relative to
    # the "City, ST" shape this parser targets; it must not crash, and
    # only the first two segments are used (no attempt to interpret a
    # trailing country/region segment).
    parsed = parse_location("Springfield, IL, USA")

    assert parsed.city == "springfield"
    assert parsed.state == "illinois"


def test_parse_location_malformed_commas_only_returns_none():
    assert parse_location(",,") is None
    assert parse_location(" , , ") is None


def test_location_token_matches_handles_malformed_job_location_gracefully():
    # A job location that is just stray punctuation/whitespace must not
    # crash the matcher and must never be treated as a match.
    assert location_token_matches("New York", ",,") is False
    assert location_token_matches("New York", "   ") is False
