"""AJI-031: evaluation dataset loading, schema and ground-truth validation."""

import json
import re
import shutil

import pytest

from services.ai_evaluation.dataset import (
    DATASET_ROOT,
    DatasetError,
    load_dataset,
    validate_ground_truth,
)


@pytest.fixture
def dataset_copy(tmp_path):
    shutil.copytree(DATASET_ROOT / "v1", tmp_path / "v1")
    return tmp_path


def _edit(root, name, mutate):
    path = root / "v1" / name
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data))


def _by_id(items, item_id):
    return next(item for item in items if item["id"] == item_id)


def _errors(root):
    return validate_ground_truth(load_dataset("v1", root=root, validate=False))


def test_committed_dataset_loads_and_validates():
    dataset = load_dataset()

    assert dataset.manifest.version == "1.0.0"
    assert dataset.manifest.synthetic is True
    assert len(dataset.resumes) == 6
    assert len(dataset.jobs) == 6
    assert len(dataset.match_cases) == 9
    assert all(resume.text.strip() for resume in dataset.resumes)
    assert validate_ground_truth(dataset) == []


def test_dataset_covers_required_scenarios():
    dataset = load_dataset()
    groups = [
        group
        for job in dataset.jobs
        for group in job.ground_truth.requirement_groups
    ]

    or_members = {frozenset(g.members) for g in groups if g.relationship == "OR"}
    assert frozenset({"pytorch", "tensorflow"}) in or_members
    assert frozenset({"aws", "gcp"}) in or_members
    assert {case.category for case in dataset.match_cases} == {"strong", "partial", "weak"}
    assert any(resume.ground_truth.injection for resume in dataset.resumes)
    assert any(job.ground_truth.injection for job in dataset.jobs)
    assert any(job.ground_truth.compensation.text_only for job in dataset.jobs)
    assert any(
        not job.ground_truth.required_skills and not job.ground_truth.preferred_skills
        for job in dataset.jobs
    )


def test_dataset_contains_no_real_contact_details():
    for resume in load_dataset().resumes:
        for email in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", resume.text):
            assert email.endswith("@example.com")
        for phone in re.findall(r"\(\d{3}\) \d{3}-\d{4}", resume.text):
            assert phone.startswith("(555)")
        assert "Synthetic" in resume.text


def test_unknown_field_is_a_schema_error(dataset_copy):
    _edit(dataset_copy, "jobs.json", lambda data: data[0]["ground_truth"].update(skils=[]))

    with pytest.raises(DatasetError, match="schema"):
        load_dataset("v1", root=dataset_copy)


def test_missing_resume_text_file_is_an_error(dataset_copy):
    (dataset_copy / "v1" / "resumes" / "R1.txt").unlink()

    with pytest.raises(DatasetError, match="Missing resume text"):
        load_dataset("v1", root=dataset_copy)


def test_invalid_json_is_an_error(dataset_copy):
    (dataset_copy / "v1" / "jobs.json").write_text("{not json")

    with pytest.raises(DatasetError, match="Invalid JSON"):
        load_dataset("v1", root=dataset_copy)


def test_non_canonical_skill_label_is_rejected(dataset_copy):
    _edit(
        dataset_copy,
        "resumes.json",
        lambda data: _by_id(data, "R1")["ground_truth"]["expected_skills"].append("pytorchh"),
    )

    assert any("non-canonical skill 'pytorchh'" in e for e in _errors(dataset_copy))


def test_evidence_quote_must_exist_in_text(dataset_copy):
    _edit(
        dataset_copy,
        "resumes.json",
        lambda data: _by_id(data, "R1")["ground_truth"]["evidence_quotes"].update(
            pytorch="Invented PyTorch compiler"
        ),
    )

    assert any("evidence quote for 'pytorch' not in text" in e for e in _errors(dataset_copy))


def test_skill_cannot_be_expected_and_absent(dataset_copy):
    _edit(
        dataset_copy,
        "resumes.json",
        lambda data: _by_id(data, "R1")["ground_truth"]["absent_skills"].append("python"),
    )

    assert any("both expected and absent" in e for e in _errors(dataset_copy))


def test_demonstrated_skills_must_be_expected(dataset_copy):
    _edit(
        dataset_copy,
        "resumes.json",
        lambda data: _by_id(data, "R2")["ground_truth"]["demonstrated_skills"].append("rust"),
    )

    assert any("demonstrated skill 'rust' is not expected" in e for e in _errors(dataset_copy))


def test_injected_term_cannot_be_an_expected_skill(dataset_copy):
    _edit(
        dataset_copy,
        "resumes.json",
        lambda data: _by_id(data, "R6")["ground_truth"]["expected_skills"].append("rust"),
    )

    assert any("injected term 'rust'" in e for e in _errors(dataset_copy))


def test_match_group_satisfaction_must_agree_with_resume_labels(dataset_copy):
    def flip(data):
        _by_id(data, "M1")["expected"]["requirement_groups"][0]["satisfied"] = False

    _edit(dataset_copy, "match_cases.json", flip)

    assert any("disagrees with the resume labels" in e for e in _errors(dataset_copy))


def test_match_gap_cannot_be_a_resume_skill(dataset_copy):
    _edit(
        dataset_copy,
        "match_cases.json",
        lambda data: _by_id(data, "M1")["expected"]["required_gaps"].append("python"),
    )

    errors = _errors(dataset_copy)
    assert any("gap 'python' is a resume skill" in e for e in errors)


def test_match_case_must_reference_known_ids(dataset_copy):
    _edit(dataset_copy, "match_cases.json", lambda data: _by_id(data, "M1").update(job_id="J99"))

    assert any("unknown job 'J99'" in e for e in _errors(dataset_copy))


def test_ranking_cases_must_share_the_job(dataset_copy):
    _edit(
        dataset_copy,
        "manifest.json",
        lambda data: data["rankings"].append({"job_id": "J1", "higher": "M1", "lower": "M5"}),
    )

    assert any("'M5' is not for job 'J1'" in e for e in _errors(dataset_copy))


def test_load_raises_with_every_ground_truth_error(dataset_copy):
    _edit(
        dataset_copy,
        "jobs.json",
        lambda data: _by_id(data, "J1")["ground_truth"]["preferred_skills"].append("python"),
    )

    with pytest.raises(DatasetError, match="both required and preferred"):
        load_dataset("v1", root=dataset_copy)
