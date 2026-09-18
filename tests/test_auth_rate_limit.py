from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.main import app


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _fresh_password() -> str:
    return f"pw-{uuid4().hex}"


def test_login_is_rate_limited_after_repeated_failures(client):
    email = f"bruteforce-{uuid4()}@example.com"
    client.post(
        "/auth/register",
        json={"email": email, "password": _fresh_password()},
    )

    last_status = None
    for _ in range(11):
        response = client.post(
            "/auth/login",
            json={"email": email, "password": "wrong-password"},
        )
        last_status = response.status_code

    assert last_status == 429


def test_login_rate_limit_is_scoped_per_email_not_global(client):
    email_a = f"victim-{uuid4()}@example.com"
    client.post(
        "/auth/register",
        json={"email": email_a, "password": _fresh_password()},
    )

    for _ in range(10):
        client.post(
            "/auth/login",
            json={"email": email_a, "password": "wrong-password"},
        )

    email_b = f"unrelated-{uuid4()}@example.com"
    password_b = _fresh_password()
    client.post(
        "/auth/register",
        json={"email": email_b, "password": password_b},
    )

    response = client.post(
        "/auth/login",
        json={"email": email_b, "password": password_b},
    )
    assert response.status_code == 200


def test_register_is_rate_limited_per_ip(client):
    last_status = None
    for _ in range(31):
        response = client.post(
            "/auth/register",
            json={
                "email": f"spam-{uuid4()}@example.com",
                "password": _fresh_password(),
            },
        )
        last_status = response.status_code

    assert last_status == 429
