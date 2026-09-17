from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.models import Preference, User
from apps.api.security import create_access_token
from apps.api.dependencies import get_db


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    user = User(
        id=uuid4(),
        email=f"preferences-test-{uuid4()}@example.com",
        password_hash="test-password-hash",
    )
    db.add(user)
    db.flush()

    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


def test_update_preferences_sets_hard_eligibility_fields(
    client, auth_headers,
):
    response = client.put(
        "/preferences/me",
        headers=auth_headers,
        json={
            "employment_types": ["contract"],
            "excluded_locations": ["California"],
            "requires_sponsorship": True,
            "is_us_citizen": False,
            "has_security_clearance": None,
            "enforce_minimum_experience": True,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["excluded_locations"] == ["California"]
    assert data["requires_sponsorship"] is True
    assert data["is_us_citizen"] is False
    assert data["has_security_clearance"] is None
    assert data["enforce_minimum_experience"] is True


def test_update_preferences_null_enforce_minimum_experience_keeps_default(
    client, auth_headers,
):
    response = client.put(
        "/preferences/me",
        headers=auth_headers,
        json={"enforce_minimum_experience": None},
    )

    assert response.status_code == 200
    assert response.json()["enforce_minimum_experience"] is False


def test_get_preferences_defaults_when_unset(client, db, test_user, auth_headers):
    db.add(Preference(id=uuid4(), user_id=test_user.id))
    db.flush()

    response = client.get("/preferences/me", headers=auth_headers)

    assert response.status_code == 200

    data = response.json()

    assert data["excluded_locations"] is None
    assert data["requires_sponsorship"] is None
    assert data["is_us_citizen"] is None
    assert data["has_security_clearance"] is None
    assert data["enforce_minimum_experience"] is False


def test_user_a_cannot_read_user_b_preferences(client, db):
    user_a = User(
        id=uuid4(), email=f"a-{uuid4()}@example.com", password_hash="hash"
    )
    user_b = User(
        id=uuid4(), email=f"b-{uuid4()}@example.com", password_hash="hash"
    )
    db.add_all([user_a, user_b])
    db.flush()

    db.add(
        Preference(
            id=uuid4(),
            user_id=user_b.id,
            excluded_locations=["Texas"],
        )
    )
    db.flush()

    response = client.get(
        "/preferences/me",
        headers={"Authorization": f"Bearer {create_access_token(str(user_a.id))}"},
    )

    assert response.status_code == 200
    assert response.json() is None
