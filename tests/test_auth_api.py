import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import apps.api.routers.auth as auth_router
from apps.api.dependencies import get_db
from apps.api.main import app
from apps.api.models import PasswordResetToken, User
from apps.api.security import hash_password, hash_reset_token


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def captured_emails(monkeypatch):
    sent = []

    def fake_send(to_email, reset_url):
        sent.append({"to_email": to_email, "reset_url": reset_url})

    monkeypatch.setattr(auth_router, "send_password_reset_email", fake_send)

    return sent


def _extract_token(reset_url: str) -> str:
    match = re.search(r"token=([^&]+)", reset_url)
    assert match is not None
    return match.group(1)


def _fresh_password() -> str:
    # Random per call (never a fixed, plausible-looking literal) so
    # secret-scanning tools like GitGuardian don't flag test fixtures as
    # hardcoded credentials.
    return f"pw-{uuid4().hex}"


def test_register_and_login_still_work(client):
    email = f"regress-{uuid4()}@example.com"
    password = _fresh_password()

    register_response = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == email


def test_register_duplicate_email_still_rejected(client):
    email = f"dup-{uuid4()}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": _fresh_password()},
    )

    response = client.post(
        "/auth/register",
        json={"email": email, "password": _fresh_password()},
    )

    assert response.status_code == 400


def test_forgot_password_existing_email_sends_reset_link(
    client, db, captured_emails,
):
    email = f"forgot-{uuid4()}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": _fresh_password()},
    )

    response = client.post("/auth/forgot-password", json={"email": email})

    assert response.status_code == 200
    assert "message" in response.json()
    assert len(captured_emails) == 1
    assert captured_emails[0]["to_email"] == email

    token_count = (
        db.query(PasswordResetToken)
        .join(User, PasswordResetToken.user_id == User.id)
        .filter(User.email == email)
        .count()
    )
    assert token_count == 1


def test_forgot_password_does_not_reveal_whether_email_exists(
    client, captured_emails,
):
    existing_email = f"exists-{uuid4()}@example.com"
    client.post(
        "/auth/register",
        json={"email": existing_email, "password": _fresh_password()},
    )

    existing_response = client.post(
        "/auth/forgot-password", json={"email": existing_email}
    )
    missing_response = client.post(
        "/auth/forgot-password",
        json={"email": f"missing-{uuid4()}@example.com"},
    )

    assert existing_response.status_code == 200
    assert missing_response.status_code == 200
    assert existing_response.json() == missing_response.json()

    # Only the existing user actually gets an email sent.
    assert len(captured_emails) == 1


def test_reset_password_with_valid_token_allows_login_with_new_password(
    client, captured_emails,
):
    email = f"reset-{uuid4()}@example.com"
    original_password = _fresh_password()
    new_password = _fresh_password()

    client.post(
        "/auth/register",
        json={"email": email, "password": original_password},
    )
    client.post("/auth/forgot-password", json={"email": email})

    raw_token = _extract_token(captured_emails[0]["reset_url"])

    reset_response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": new_password},
    )
    assert reset_response.status_code == 200

    old_login = client.post(
        "/auth/login",
        json={"email": email, "password": original_password},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new_login.status_code == 200


def test_reset_password_token_is_single_use(client, captured_emails):
    email = f"singleuse-{uuid4()}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": _fresh_password()},
    )
    client.post("/auth/forgot-password", json={"email": email})

    raw_token = _extract_token(captured_emails[0]["reset_url"])

    first = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": _fresh_password()},
    )
    assert first.status_code == 200

    second = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": _fresh_password()},
    )
    assert second.status_code == 400


def test_reset_password_rejects_invalid_token(client):
    response = client.post(
        "/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": _fresh_password()},
    )
    assert response.status_code == 400


def test_reset_password_rejects_expired_token(client, db):
    email = f"expired-{uuid4()}@example.com"
    original_password = _fresh_password()
    user = User(
        id=uuid4(),
        email=email,
        password_hash=hash_password(original_password),
    )
    db.add(user)
    db.flush()

    raw_token = f"expired-{uuid4().hex}"
    db.add(
        PasswordResetToken(
            id=uuid4(),
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db.flush()

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": _fresh_password()},
    )

    assert response.status_code == 400

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": original_password},
    )
    assert login_response.status_code == 200


def test_reset_password_rejects_short_new_password(client, captured_emails):
    email = f"weak-{uuid4()}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": _fresh_password()},
    )
    client.post("/auth/forgot-password", json={"email": email})

    raw_token = _extract_token(captured_emails[0]["reset_url"])

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "short"},
    )

    assert response.status_code == 422
