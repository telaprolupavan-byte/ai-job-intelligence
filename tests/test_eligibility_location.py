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
