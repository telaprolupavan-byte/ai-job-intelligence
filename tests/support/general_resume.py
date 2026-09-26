"""Shared resume texts and builders for the AJI-027 General Resume
Intelligence tests."""

from uuid import uuid4

from apps.api.models import Resume, ResumeVersion, User
from apps.api.services.resume_fingerprint import compute_content_fingerprint

STRONG_RESUME = """Jane Doe
jane@example.com | 555-123-4567

SUMMARY
Machine learning engineer building production systems.

PROFESSIONAL EXPERIENCE
Senior ML Engineer, Acme Corp, 2020 - 2024
- Built a real-time fraud detection pipeline in Python processing 2M events per day.
- Led migration of the model serving stack to Kubernetes, reducing latency by 35%.

EDUCATION
B.S. Computer Science, State University, 2018

SKILLS
Python, Kubernetes
"""

WEAK_RESUME = """Jane Doe
jane@example.com | 555-123-4567

SUMMARY
Machine learning engineer with experience building production systems.

PROFESSIONAL EXPERIENCE
Senior ML Engineer, Acme Corp, 2020 - 2024
- Built a real-time fraud detection pipeline in Python processing 2M events per day.
- Led migration of the model serving stack to Kubernetes, reducing latency by 35%.
- Responsible for the data quality checks for the feature store.
- Worked on various dashboards for the analytics team.

EDUCATION
B.S. Computer Science, State University, 2018

SKILLS
Python, Kubernetes, Docker
"""

WEAK_BULLET_1 = "- Responsible for the data quality checks for the feature store."
WEAK_BULLET_2 = "- Worked on various dashboards for the analytics team."


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self):
        self.calls = 0

    def generate_improvement_explanations(self, *, items):
        self.calls += 1
        return {"items": []}


def make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"general-resume-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def make_version(db, user, text=WEAK_RESUME) -> ResumeVersion:
    resume = Resume(id=uuid4(), user_id=user.id, filename="resume.pdf", original_text=text)
    db.add(resume)
    db.flush()
    version = ResumeVersion(
        id=uuid4(),
        resume_id=resume.id,
        name="Original",
        content_text=text,
        content_fingerprint=compute_content_fingerprint(text),
        original_filename="resume.pdf",
        storage_path=f"/tmp/{uuid4()}.pdf",
        is_master=True,
    )
    db.add(version)
    db.flush()
    return version
