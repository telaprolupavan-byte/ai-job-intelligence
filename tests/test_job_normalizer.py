from services.job_discovery.normalizer import (
    normalize_employment_type,
    normalize_remote_type,
    normalize_text,
    normalize_url,
)


def test_normalize_text():
    assert normalize_text("  Machine   Learning   Engineer  ") == (
        "Machine Learning Engineer"
    )


def test_normalize_empty_text():
    assert normalize_text("   ") is None


def test_normalize_employment_type():
    assert normalize_employment_type("FULL-TIME") == "full_time"
    assert normalize_employment_type("Contract") == "contract"
    assert normalize_employment_type("Intern") == "internship"


def test_unknown_employment_type():
    assert normalize_employment_type("Something Unknown") is None


def test_normalize_remote_type():
    assert normalize_remote_type("Fully Remote") == "remote"
    assert normalize_remote_type("Hybrid") == "hybrid"
    assert normalize_remote_type("On-Site") == "onsite"


def test_unknown_remote_type():
    assert normalize_remote_type("Something Unknown") is None


def test_normalize_url():
    assert normalize_url("  https://example.com/job/123  ") == (
        "https://example.com/job/123"
    )