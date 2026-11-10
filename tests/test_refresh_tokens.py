"""Хранимые refresh-токены: выдача, ротация, повторное использование, logout."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import cfg
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    create_token,
)
from app.models.refresh_token import RefreshToken

URL = "/api/v1/auth"


def jti_of(token: str) -> uuid.UUID:
    payload = jwt.decode(token, options={"verify_signature": False})
    return uuid.UUID(payload["jti"])


async def get_record(db, token: str) -> RefreshToken | None:
    return await db.get(RefreshToken, jti_of(token), populate_existing=True)


async def count_tokens(db, user_id: int) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(RefreshToken)
        .where(RefreshToken.user_id == user_id)
    )


@pytest.fixture
def login(anon_client: AsyncClient, user_password):
    async def _login(user) -> dict:
        response = await anon_client.post(
            f"{URL}/login", json={"email": user.email, "password": user_password}
        )
        assert response.status_code == 200
        return response.json()

    return _login


async def do_refresh(client: AsyncClient, token: str):
    return await client.post(f"{URL}/refresh", json={"refresh_token": token})


# ---------- выдача при login ----------


async def test_login_stores_refresh_token(db, login, customer_user):
    tokens = await login(customer_user)

    record = await get_record(db, tokens["refresh_token"])
    assert record is not None
    assert record.user_id == customer_user.id
    assert record.revoked_at is None
    assert record.replaced_by is None
    assert record.created_at is not None
    expected = datetime.now(UTC) + timedelta(days=cfg.REFRESH_TOKEN_EXPIRE_DAYS)
    assert abs(record.expires_at - expected) < timedelta(minutes=1)


async def test_each_login_creates_separate_token(db, login, customer_user):
    first = await login(customer_user)
    second = await login(customer_user)

    assert jti_of(first["refresh_token"]) != jti_of(second["refresh_token"])
    assert await count_tokens(db, customer_user.id) == 2


# ---------- POST /auth/refresh: ротация ----------


async def test_refresh_rotates_token(
    anon_client: AsyncClient, db, login, customer_user
):
    old = await login(customer_user)

    response = await do_refresh(anon_client, old["refresh_token"])

    assert response.status_code == 200
    new = response.json()
    assert new["refresh_token"] != old["refresh_token"]

    old_record = await get_record(db, old["refresh_token"])
    new_record = await get_record(db, new["refresh_token"])
    assert old_record.revoked_at is not None
    assert old_record.replaced_by == new_record.id
    assert new_record.revoked_at is None
    assert new_record.user_id == customer_user.id

    me = await anon_client.get(
        f"{URL}/me", headers={"Authorization": f"Bearer {new['access_token']}"}
    )
    assert me.json()["id"] == customer_user.id


async def test_refresh_chain(anon_client: AsyncClient, login, customer_user):
    token = (await login(customer_user))["refresh_token"]

    for _ in range(3):
        response = await do_refresh(anon_client, token)
        assert response.status_code == 200
        token = response.json()["refresh_token"]


async def test_reused_token_revokes_whole_family(
    anon_client: AsyncClient, db, login, customer_user
):
    stolen = (await login(customer_user))["refresh_token"]
    legit = (await do_refresh(anon_client, stolen)).json()["refresh_token"]

    # злоумышленник повторно предъявляет уже использованный токен
    reuse = await do_refresh(anon_client, stolen)

    assert reuse.status_code == 401
    # и легитимный (новый) токен тоже отозван
    assert (await get_record(db, legit)).revoked_at is not None
    assert (await do_refresh(anon_client, legit)).status_code == 401


async def test_reuse_does_not_affect_other_users(
    anon_client: AsyncClient, login, customer_user, admin_user
):
    admin_token = (await login(admin_user))["refresh_token"]
    stolen = (await login(customer_user))["refresh_token"]
    await do_refresh(anon_client, stolen)
    await do_refresh(anon_client, stolen)

    assert (await do_refresh(anon_client, admin_token)).status_code == 200


async def test_refresh_unknown_jti(anon_client: AsyncClient, customer_user):
    token = create_refresh_token(customer_user.id, uuid.uuid4())

    response = await do_refresh(anon_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


async def test_refresh_jti_of_other_user(
    anon_client: AsyncClient, login, customer_user, admin_user
):
    customer_jti = jti_of((await login(customer_user))["refresh_token"])
    forged = create_refresh_token(admin_user.id, customer_jti)

    response = await do_refresh(anon_client, forged)

    assert response.status_code == 401


async def test_refresh_expired_in_db(
    anon_client: AsyncClient, db, login, customer_user
):
    token = (await login(customer_user))["refresh_token"]
    record = await get_record(db, token)
    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()

    response = await do_refresh(anon_client, token)

    assert response.status_code == 401


async def test_refresh_expired_jwt(anon_client: AsyncClient, customer_user):
    token = create_token(
        customer_user.id,
        TokenType.refresh,
        timedelta(seconds=-1),
        jti=uuid.uuid4(),
    )

    response = await do_refresh(anon_client, token)

    assert response.status_code == 401


async def test_refresh_without_jti(anon_client: AsyncClient, customer_user):
    token = create_token(customer_user.id, TokenType.refresh, timedelta(minutes=5))

    response = await do_refresh(anon_client, token)

    assert response.status_code == 401


async def test_refresh_with_access_token(anon_client: AsyncClient, customer_user):
    response = await do_refresh(anon_client, create_access_token(customer_user.id))

    assert response.status_code == 401


async def test_refresh_garbage(anon_client: AsyncClient):
    response = await do_refresh(anon_client, "garbage")

    assert response.status_code == 401


async def test_refresh_user_deactivated_after_login(
    anon_client: AsyncClient, db, login, customer_user
):
    token = (await login(customer_user))["refresh_token"]
    customer_user.is_active = False
    await db.commit()

    response = await do_refresh(anon_client, token)

    assert response.status_code == 401


async def test_refresh_missing_body(anon_client: AsyncClient):
    response = await anon_client.post(f"{URL}/refresh", json={})

    assert response.status_code == 422


# ---------- POST /auth/logout ----------


async def test_logout(anon_client: AsyncClient, db, login, customer_user):
    token = (await login(customer_user))["refresh_token"]

    response = await anon_client.post(f"{URL}/logout", json={"refresh_token": token})

    assert response.status_code == 204
    assert (await get_record(db, token)).revoked_at is not None
    assert (await do_refresh(anon_client, token)).status_code == 401


async def test_logout_twice(anon_client: AsyncClient, login, customer_user):
    token = (await login(customer_user))["refresh_token"]
    await anon_client.post(f"{URL}/logout", json={"refresh_token": token})

    response = await anon_client.post(f"{URL}/logout", json={"refresh_token": token})

    assert response.status_code == 204


async def test_logout_keeps_other_sessions(
    anon_client: AsyncClient, login, customer_user
):
    phone = (await login(customer_user))["refresh_token"]
    laptop = (await login(customer_user))["refresh_token"]

    await anon_client.post(f"{URL}/logout", json={"refresh_token": phone})

    assert (await do_refresh(anon_client, laptop)).status_code == 200


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda user: "garbage",
        lambda user: create_access_token(user.id),
        lambda user: create_refresh_token(user.id, uuid.uuid4()),
    ],
    ids=["garbage", "access_token", "unknown_jti"],
)
async def test_logout_invalid_token(
    anon_client: AsyncClient, customer_user, token_factory
):
    response = await anon_client.post(
        f"{URL}/logout", json={"refresh_token": token_factory(customer_user)}
    )

    assert response.status_code == 401


async def test_logout_missing_body(anon_client: AsyncClient):
    response = await anon_client.post(f"{URL}/logout", json={})

    assert response.status_code == 422


# ---------- POST /auth/logout-all ----------


async def test_logout_all(anon_client: AsyncClient, login, customer_user, admin_user):
    phone = (await login(customer_user))["refresh_token"]
    laptop = (await login(customer_user))["refresh_token"]
    admin_token = (await login(admin_user))["refresh_token"]

    response = await anon_client.post(
        f"{URL}/logout-all",
        headers={"Authorization": f"Bearer {create_access_token(customer_user.id)}"},
    )

    assert response.status_code == 204
    assert (await do_refresh(anon_client, phone)).status_code == 401
    assert (await do_refresh(anon_client, laptop)).status_code == 401
    # токены других пользователей не тронуты
    assert (await do_refresh(anon_client, admin_token)).status_code == 200


async def test_logout_all_requires_auth(anon_client: AsyncClient):
    response = await anon_client.post(f"{URL}/logout-all")

    assert response.status_code == 401


# ---------- каскад ----------


async def test_tokens_deleted_with_user(db, login, customer_user):
    await login(customer_user)
    user_id = customer_user.id

    await db.delete(customer_user)
    await db.commit()

    assert await count_tokens(db, user_id) == 0
