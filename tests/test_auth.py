import uuid
from datetime import timedelta

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import cfg
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    create_token,
)

URL = "/api/v1/auth"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def register_payload() -> dict:
    return {
        "email": "new.user@example.com",
        "password": "super-secret-1",
        "full_name": "New User",
    }


# ---------- POST /auth/register ----------


async def test_register(anon_client: AsyncClient, register_payload):
    response = await anon_client.post(f"{URL}/register", json=register_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"
    assert body["full_name"] == "New User"
    assert body["role"] == "customer"
    assert "password" not in body
    assert "hashed_password" not in body
    assert "salt" not in body


async def test_register_lowercases_email(anon_client: AsyncClient, register_payload):
    register_payload["email"] = "New.User@Example.COM"

    response = await anon_client.post(f"{URL}/register", json=register_payload)

    assert response.status_code == 201
    assert response.json()["email"] == "new.user@example.com"


async def test_register_cannot_set_role(anon_client: AsyncClient, register_payload):
    register_payload["role"] = "admin"

    response = await anon_client.post(f"{URL}/register", json=register_payload)

    assert response.status_code == 201
    assert response.json()["role"] == "customer"


@pytest.mark.parametrize("email", ["new.user@example.com", "NEW.USER@example.com"])
async def test_register_duplicate_email(
    anon_client: AsyncClient, register_payload, email
):
    await anon_client.post(f"{URL}/register", json=register_payload)
    register_payload["email"] = email

    response = await anon_client.post(f"{URL}/register", json=register_payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "User with this email already exists"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("email", ""),
        ("password", "short"),
        ("password", "x" * 129),
        ("full_name", ""),
        ("full_name", "x" * 151),
    ],
)
async def test_register_invalid(
    anon_client: AsyncClient, register_payload, field, value
):
    register_payload[field] = value

    response = await anon_client.post(f"{URL}/register", json=register_payload)

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["email", "password", "full_name"])
async def test_register_missing_field(
    anon_client: AsyncClient, register_payload, field
):
    del register_payload[field]

    response = await anon_client.post(f"{URL}/register", json=register_payload)

    assert response.status_code == 422


# ---------- POST /auth/login ----------


async def test_login(anon_client: AsyncClient, user_password, customer_user):
    response = await anon_client.post(
        f"{URL}/login",
        json={"email": customer_user.email, "password": user_password},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    me = await anon_client.get(f"{URL}/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == customer_user.id


async def test_register_then_login(anon_client: AsyncClient, register_payload):
    await anon_client.post(f"{URL}/register", json=register_payload)

    response = await anon_client.post(
        f"{URL}/login",
        json={
            "email": "NEW.USER@example.com",
            "password": register_payload["password"],
        },
    )

    assert response.status_code == 200


async def test_login_wrong_password(anon_client: AsyncClient, customer_user):
    response = await anon_client.post(
        f"{URL}/login",
        json={"email": customer_user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_login_unknown_email(anon_client: AsyncClient, user_password):
    response = await anon_client.post(
        f"{URL}/login",
        json={"email": "nobody@example.com", "password": user_password},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_login_inactive_user(
    anon_client: AsyncClient, user_password, inactive_user
):
    response = await anon_client.post(
        f"{URL}/login",
        json={"email": inactive_user.email, "password": user_password},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User is inactive"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "admin@example.com"},
        {"password": "some-password"},
        {"email": "not-an-email", "password": "some-password"},
    ],
    ids=["empty", "no_password", "no_email", "bad_email"],
)
async def test_login_invalid_body(anon_client: AsyncClient, payload):
    response = await anon_client.post(f"{URL}/login", json=payload)

    assert response.status_code == 422


# ---------- GET /auth/me ----------


async def test_me(customer_client: AsyncClient, customer_user):
    response = await customer_client.get(f"{URL}/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == customer_user.id
    assert body["email"] == customer_user.email
    assert body["role"] == "customer"


async def test_me_without_token(anon_client: AsyncClient):
    response = await anon_client.get(f"{URL}/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer garbage"},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "garbage"},
    ],
    ids=["garbage_token", "empty_token", "basic_scheme", "no_scheme"],
)
async def test_me_malformed_auth_header(anon_client: AsyncClient, headers):
    response = await anon_client.get(f"{URL}/me", headers=headers)

    assert response.status_code == 401


async def test_me_expired_token(anon_client: AsyncClient, customer_user):
    token = create_token(customer_user.id, TokenType.access, timedelta(seconds=-1))

    response = await anon_client.get(f"{URL}/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


async def test_me_refresh_token_rejected(anon_client: AsyncClient, customer_user):
    token = create_refresh_token(customer_user.id, uuid.uuid4())

    response = await anon_client.get(f"{URL}/me", headers=bearer(token))

    assert response.status_code == 401


async def test_me_token_signed_with_other_secret(
    anon_client: AsyncClient, customer_user
):
    token = jwt.encode(
        {"sub": str(customer_user.id), "type": "access", "exp": 9_999_999_999},
        "another-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )

    response = await anon_client.get(f"{URL}/me", headers=bearer(token))

    assert response.status_code == 401


async def test_me_tampered_token(anon_client: AsyncClient, customer_user, admin_user):
    header, _, signature = create_access_token(customer_user.id).split(".")
    _, payload, _ = create_access_token(admin_user.id).split(".")

    response = await anon_client.get(
        f"{URL}/me", headers=bearer(f"{header}.{payload}.{signature}")
    )

    assert response.status_code == 401


async def test_me_alg_none_rejected(anon_client: AsyncClient, admin_user):
    token = jwt.encode(
        {"sub": str(admin_user.id), "type": "access", "exp": 9_999_999_999},
        key=None,
        algorithm="none",
    )

    response = await anon_client.get(f"{URL}/me", headers=bearer(token))

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "access", "exp": 9_999_999_999},  # нет sub
        {"sub": "1", "exp": 9_999_999_999},  # нет type
        {"sub": "1", "type": "access"},  # нет exp
        {"sub": "abc", "type": "access", "exp": 9_999_999_999},
    ],
    ids=["no_sub", "no_type", "no_exp", "non_numeric_sub"],
)
async def test_me_token_with_bad_claims(anon_client: AsyncClient, payload):
    token = jwt.encode(payload, cfg.SECRET, algorithm=cfg.JWT_ALGORITHM)

    response = await anon_client.get(f"{URL}/me", headers=bearer(token))

    assert response.status_code == 401


async def test_me_deleted_user(anon_client: AsyncClient, db, customer_user):
    token = create_access_token(customer_user.id)
    await db.delete(customer_user)
    await db.commit()

    response = await anon_client.get(f"{URL}/me", headers=bearer(token))

    assert response.status_code == 401


async def test_me_inactive_user(anon_client: AsyncClient, inactive_user):
    token = create_access_token(inactive_user.id)

    response = await anon_client.get(f"{URL}/me", headers=bearer(token))

    assert response.status_code == 401
