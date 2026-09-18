from services.provider_scorecard.eval_adapters._us_location import looks_like_us_location


def test_none_is_not_us():
    assert looks_like_us_location(None) is False


def test_empty_string_is_not_us():
    assert looks_like_us_location("") is False


def test_state_abbreviation_matches():
    assert looks_like_us_location("New York, NY") is True


def test_full_country_name_matches():
    assert looks_like_us_location("Remote - United States") is True


def test_flexible_remote_does_not_false_positive_on_florida():
    # "Flexible" starts with "fl" but is not the word "fl" - must not match.
    assert looks_like_us_location("Flexible / Remote") is False


def test_foreign_city_does_not_match():
    assert looks_like_us_location("London, UK") is False


def test_state_abbreviation_matches_as_a_whole_word():
    assert looks_like_us_location("Columbus, OH") is True


# Note: standalone two-letter state codes that are also common English
# words (e.g. "OR", "IN", "HI", "OK", "ME") are an inherent ambiguity this
# heuristic - like Greenhouse's own - does not attempt to resolve; the
# word-boundary fix here only removes the *word-fragment* false positives
# (e.g. "Flexible" matching "FL"), not this separate, harder class.
