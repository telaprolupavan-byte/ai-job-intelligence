from apps.api.services.resume_validation import validate_resume_text


def _valid_resume_text() -> str:
    return """
    Jane Doe
    jane@example.com

    SUMMARY
    Product-minded software engineer with experience building reliable services.

    EXPERIENCE
    Software Engineer
    Built and maintained backend services for internal users.
    Improved deployment workflows and supported production operations.

    SKILLS
    Python, SQL, FastAPI, PostgreSQL

    EDUCATION
    Bachelor of Science in Computer Science
    """ + " Additional resume detail." * 8


def test_validate_resume_text_accepts_resume_with_required_signals():
    result = validate_resume_text(_valid_resume_text())

    assert result.valid is True
    assert result.word_count >= 50
    assert result.character_count >= 300
    assert "experience" in result.section_matches
    assert result.warnings == []


def test_validate_resume_text_reports_each_missing_requirement():
    result = validate_resume_text("Python developer")

    assert result.valid is False
    assert any("300 characters" in warning for warning in result.warnings)
    assert any("50 words" in warning for warning in result.warnings)
    assert any("sections" in warning for warning in result.warnings)
