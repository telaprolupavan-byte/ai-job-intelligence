"""Unit tests for AJI-022's deterministic pasted-content normalizer."""

from apps.api.services.job_intelligence.deterministic import (
    RawJobDescription,
    extract_deterministic,
)
from apps.api.services.job_submission.normalizer import (
    UNTITLED_JOB_TITLE,
    classify_heading,
    normalize_job_content,
    resolve_title,
)


STRUCTURED_POSTING = """Senior Backend Engineer
Acme builds payments infrastructure for small businesses.

What you'll do:
- Design and operate high-throughput payment APIs
- Mentor engineers on the platform team

Requirements
- 5+ years of Python experience
- Experience with PostgreSQL

Preferred Qualifications:
- Kubernetes experience

Benefits
- Health insurance and 401k
"""


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

def test_recognizes_common_heading_variants():
    assert classify_heading("Requirements") == "requirements"
    assert classify_heading("Requirements:") == "requirements"
    assert classify_heading("## Minimum Qualifications") == "requirements"
    assert classify_heading("**Nice to have**") == "requirements"
    assert classify_heading("What you’ll do:") == "responsibilities"
    assert classify_heading("Key Responsibilities") == "responsibilities"
    assert classify_heading("Benefits") == "description"
    assert classify_heading("About the role") == "description"


def test_content_lines_are_never_headings():
    # Heading word followed by content on the same line stays content.
    assert classify_heading("Requirements: 5+ years of Python") is None
    assert classify_heading("- Requirements") is None
    assert (
        classify_heading(
            "Our requirements for this role are demanding but fair and clear"
        )
        is None
    )
    assert classify_heading("") is None


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

def test_splits_structured_posting_into_existing_job_inputs():
    result = normalize_job_content(STRUCTURED_POSTING)

    assert result.description == (
        "Senior Backend Engineer\n"
        "Acme builds payments infrastructure for small businesses.\n"
        "\n"
        "Benefits\n"
        "- Health insurance and 401k"
    )
    # The responsibilities heading itself is dropped from this column -
    # see the next tests.
    assert result.responsibilities == (
        "- Design and operate high-throughput payment APIs\n"
        "- Mentor engineers on the platform team"
    )
    assert result.requirements == (
        "Requirements\n"
        "- 5+ years of Python experience\n"
        "- Experience with PostgreSQL\n"
        "\n"
        "Preferred Qualifications:\n"
        "- Kubernetes experience"
    )


def test_every_line_is_kept_verbatim_in_exactly_one_section():
    """Every line lands verbatim in exactly one column, except a
    responsibilities heading, which is dropped so it can never be
    extracted as a responsibility item."""
    result = normalize_job_content(STRUCTURED_POSTING)
    combined = "\n".join(
        part
        for part in [
            result.description,
            result.requirements,
            result.responsibilities,
        ]
        if part
    )

    original_lines = sorted(
        line
        for line in STRUCTURED_POSTING.split("\n")
        if line.strip() and classify_heading(line) != "responsibilities"
    )
    split_lines = sorted(
        line for line in combined.split("\n") if line.strip()
    )
    assert split_lines == original_lines


def test_unstructured_blob_stays_whole_as_description():
    blob = (
        "We are hiring a data analyst. You should know SQL and Excel. "
        "You will build dashboards for the finance team."
    )

    result = normalize_job_content(blob)

    assert result.description == blob
    # Never invented: no heading means no requirements/responsibilities.
    assert result.requirements is None
    assert result.responsibilities is None


def test_missing_sections_are_never_invented():
    result = normalize_job_content(
        "Intro paragraph.\n\nResponsibilities\n- Build reliable pipelines"
    )

    assert result.responsibilities == "- Build reliable pipelines"
    assert result.requirements is None
    assert result.description == "Intro paragraph."


def test_windows_line_endings_are_normalized():
    result = normalize_job_content(
        "Intro\r\nRequirements\r\n- Python experience\r\n"
    )

    assert result.description == "Intro"
    assert result.requirements == "Requirements\n- Python experience"


def test_empty_or_whitespace_content_yields_nothing():
    result = normalize_job_content("   \n\n  ")

    assert result.description is None
    assert result.requirements is None
    assert result.responsibilities is None


def test_normalized_output_keeps_existing_job_intelligence_semantics():
    """The split must feed AJI-012 so that responsibilities stay out of
    requirements and a "Preferred Qualifications" heading still makes
    what follows preferred."""
    result = normalize_job_content(STRUCTURED_POSTING)

    extraction = extract_deterministic(
        RawJobDescription(
            title="Senior Backend Engineer",
            description=result.description,
            requirements=result.requirements,
            responsibilities=result.responsibilities,
        )
    )

    required = {item.canonical_skill for item in extraction.required_skills}
    preferred = {item.canonical_skill for item in extraction.preferred_skills}

    assert "python" in {skill.lower() for skill in required}
    assert "kubernetes" in {skill.lower() for skill in preferred}
    assert "kubernetes" not in {skill.lower() for skill in required}
    assert [item.description for item in extraction.responsibilities] == [
        "Design and operate high-throughput payment APIs",
        "Mentor engineers on the platform team",
    ]


# ---------------------------------------------------------------------------
# Title resolution
# ---------------------------------------------------------------------------

def test_user_title_wins():
    assert resolve_title("  Staff Engineer ", STRUCTURED_POSTING) == (
        "Staff Engineer"
    )


def test_title_falls_back_to_first_line_verbatim():
    assert resolve_title(None, STRUCTURED_POSTING) == "Senior Backend Engineer"
    assert resolve_title("   ", "\n\n## Data Engineer\nBody") == "Data Engineer"


def test_title_never_taken_from_a_heading_or_a_paragraph():
    assert resolve_title(None, "About the job\nWe build things.") == (
        UNTITLED_JOB_TITLE
    )
    assert resolve_title(None, "x" * 400) == UNTITLED_JOB_TITLE
