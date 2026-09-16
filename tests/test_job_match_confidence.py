from services.job_matching.scorer import calculate_match_confidence


def test_high_confidence():
    assert calculate_match_confidence(
        has_job_requirements=True,
        has_resume_skills=True,
        has_experience_data=True,
        has_role_data=True,
    ) == "high"


def test_medium_confidence():
    assert calculate_match_confidence(
        has_job_requirements=True,
        has_resume_skills=True,
        has_experience_data=False,
        has_role_data=False,
    ) == "medium"


def test_low_confidence():
    assert calculate_match_confidence(
        has_job_requirements=False,
        has_resume_skills=True,
        has_experience_data=False,
        has_role_data=False,
    ) == "low"