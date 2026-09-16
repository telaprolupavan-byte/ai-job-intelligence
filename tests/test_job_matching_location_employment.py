from services.job_matching.scorer import (
    score_employment_type,
    score_location,
)


def test_matching_remote_preference_gets_full_score():
    assert score_location(
        job_remote_type="remote",
        job_location=None,
        preferred_remote_type="remote",
    ) == 10


def test_mismatched_remote_preference_gets_zero():
    assert score_location(
        job_remote_type="onsite",
        job_location="New York, NY",
        preferred_remote_type="remote",
    ) == 0


def test_unknown_remote_type_gets_partial_credit():
    assert score_location(
        job_remote_type=None,
        job_location=None,
        preferred_remote_type="remote",
    ) == 5


def test_matching_location_gets_full_score():
    assert score_location(
        job_remote_type="onsite",
        job_location="Newark, NJ",
        preferred_location="Newark, NJ",
    ) == 10


def test_unknown_location_gets_partial_credit():
    assert score_location(
        job_remote_type="onsite",
        job_location=None,
        preferred_location="Newark, NJ",
    ) == 5


def test_matching_employment_type():
    assert score_employment_type(
        job_employment_type="full_time",
        preferred_employment_type="full_time",
    ) == 5


def test_mismatched_employment_type():
    assert score_employment_type(
        job_employment_type="contract",
        preferred_employment_type="full_time",
    ) == 0


def test_unknown_employment_type():
    assert score_employment_type(
        job_employment_type=None,
        preferred_employment_type="full_time",
    ) == 2.5


def test_no_employment_preference():
    assert score_employment_type(
        job_employment_type="contract",
        preferred_employment_type=None,
    ) == 5