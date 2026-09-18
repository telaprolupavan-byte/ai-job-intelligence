from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import Company, Job, SavedJob, User
from apps.api.security import create_access_token


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _make_user(db) -> User:
    user = User(
        id=uuid4(),
        email=f"applicant-{uuid4()}@example.com",
        password_hash="not-a-real-hash",
    )
    db.add(user)
    db.flush()
    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _make_job(db, *, title="Backend Engineer") -> Job:
    company = Company(
        id=uuid4(),
        name=f"Applications Test Co {uuid4()}",
        normalized_name=f"applications-test-co-{uuid4()}",
    )
    db.add(company)
    db.flush()

    job = Job(
        id=uuid4(),
        company_id=company.id,
        title=title,
        employment_type="full_time",
        source="test",
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(job)
    db.flush()
    return job


def test_save_job_creates_application(client, db):
    user = _make_user(db)
    job = _make_job(db)
    db.commit()

    response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(user),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "saved"
    assert body["job"]["title"] == "Backend Engineer"
    assert body["applied_at"] is None


def test_save_job_is_idempotent_no_duplicate(client, db):
    user = _make_user(db)
    job = _make_job(db)
    db.commit()

    first = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(user),
    )
    second = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(user),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    count = (
        db.query(SavedJob)
        .filter(SavedJob.user_id == user.id, SavedJob.job_id == job.id)
        .count()
    )
    assert count == 1


def test_save_job_rejects_missing_job(client, db):
    user = _make_user(db)
    db.commit()

    response = client.post(
        "/applications",
        json={"job_id": str(uuid4())},
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


def test_save_job_requires_authentication(client, db):
    job = _make_job(db)
    db.commit()

    response = client.post("/applications", json={"job_id": str(job.id)})

    assert response.status_code in (401, 403)


def test_list_applications_only_returns_own(client, db):
    owner = _make_user(db)
    other_user = _make_user(db)
    job = _make_job(db)
    db.commit()

    client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(owner),
    )

    owner_response = client.get("/applications", headers=_auth_headers(owner))
    other_response = client.get(
        "/applications", headers=_auth_headers(other_user)
    )

    assert len(owner_response.json()) == 1
    assert other_response.json() == []


def test_get_application_detail_includes_status_history(client, db):
    user = _make_user(db)
    job = _make_job(db)
    db.commit()

    create_response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(user),
    )
    application_id = create_response.json()["id"]

    client.patch(
        f"/applications/{application_id}",
        json={"status": "applied"},
        headers=_auth_headers(user),
    )

    detail_response = client.get(
        f"/applications/{application_id}", headers=_auth_headers(user)
    )

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["status"] == "applied"
    assert body["applied_at"] is not None
    statuses = [event["status"] for event in body["status_history"]]
    assert statuses == ["saved", "applied"]


def test_get_application_detail_404_for_other_user(client, db):
    owner = _make_user(db)
    other_user = _make_user(db)
    job = _make_job(db)
    db.commit()

    create_response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(owner),
    )
    application_id = create_response.json()["id"]

    response = client.get(
        f"/applications/{application_id}", headers=_auth_headers(other_user)
    )

    assert response.status_code == 404


def test_update_status_rejects_invalid_status(client, db):
    user = _make_user(db)
    job = _make_job(db)
    db.commit()

    create_response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(user),
    )
    application_id = create_response.json()["id"]

    response = client.patch(
        f"/applications/{application_id}",
        json={"status": "ghosted"},
        headers=_auth_headers(user),
    )

    assert response.status_code == 422


def test_update_status_for_other_users_application_is_404(client, db):
    owner = _make_user(db)
    other_user = _make_user(db)
    job = _make_job(db)
    db.commit()

    create_response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(owner),
    )
    application_id = create_response.json()["id"]

    response = client.patch(
        f"/applications/{application_id}",
        json={"status": "applied"},
        headers=_auth_headers(other_user),
    )

    assert response.status_code == 404


def test_update_status_missing_application_is_404(client, db):
    user = _make_user(db)
    db.commit()

    response = client.patch(
        f"/applications/{uuid4()}",
        json={"status": "applied"},
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


def test_remove_saved_job_deletes_while_still_saved(client, db):
    user = _make_user(db)
    job = _make_job(db)
    db.commit()

    create_response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(user),
    )
    application_id = create_response.json()["id"]

    response = client.delete(
        f"/applications/{application_id}", headers=_auth_headers(user)
    )

    assert response.status_code == 204
    assert (
        db.query(SavedJob).filter(SavedJob.id == application_id).first()
        is None
    )


def test_remove_saved_job_rejects_once_applied(client, db):
    user = _make_user(db)
    job = _make_job(db)
    db.commit()

    create_response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(user),
    )
    application_id = create_response.json()["id"]

    client.patch(
        f"/applications/{application_id}",
        json={"status": "applied"},
        headers=_auth_headers(user),
    )

    response = client.delete(
        f"/applications/{application_id}", headers=_auth_headers(user)
    )

    assert response.status_code == 409
    assert (
        db.query(SavedJob).filter(SavedJob.id == application_id).first()
        is not None
    )


def test_remove_saved_job_for_other_users_application_is_404(client, db):
    owner = _make_user(db)
    other_user = _make_user(db)
    job = _make_job(db)
    db.commit()

    create_response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(owner),
    )
    application_id = create_response.json()["id"]

    response = client.delete(
        f"/applications/{application_id}", headers=_auth_headers(other_user)
    )

    assert response.status_code == 404
    assert (
        db.query(SavedJob).filter(SavedJob.id == application_id).first()
        is not None
    )


def test_remove_saved_job_missing_application_is_404(client, db):
    user = _make_user(db)
    db.commit()

    response = client.delete(
        f"/applications/{uuid4()}", headers=_auth_headers(user)
    )

    assert response.status_code == 404


def test_remove_saved_job_requires_authentication(client, db):
    user = _make_user(db)
    job = _make_job(db)
    db.commit()

    create_response = client.post(
        "/applications",
        json={"job_id": str(job.id)},
        headers=_auth_headers(user),
    )
    application_id = create_response.json()["id"]

    response = client.delete(f"/applications/{application_id}")

    assert response.status_code in (401, 403)
