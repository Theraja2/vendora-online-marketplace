"""Registration, login, and token handling."""

import asyncio
import statistics
import time

import pytest

from tests.conftest import auth_headers, login, register, user_payload


async def test_register_returns_created_user(client):
    response, _ = await register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "ada"
    assert body["role"] == "customer"
    assert body["is_active"] is True
    assert "created_at" in body
    assert "password" not in body


async def test_register_rejects_duplicate_username(client):
    await register(client)
    response, _ = await register(client, email="other@example.com",
                                 phone_number="+254700000002")

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already exists."


async def test_register_rejects_duplicate_email(client):
    await register(client)
    response, _ = await register(client, username="other",
                                 phone_number="+254700000002")

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already exists."


async def test_register_reports_duplicate_phone_accurately(client):
    """Regression: a duplicate phone used to be reported as a username/email clash."""
    await register(client)
    response, _ = await register(client, username="other", email="other@example.com")

    assert response.status_code == 409
    assert response.json()["detail"] == "Phone number already exists."


async def test_register_rejects_short_password(client):
    response, _ = await register(client, password="short")

    assert response.status_code == 422


async def test_login_requires_form_encoding(client):
    await register(client)
    response = await client.post(
        "/auth/login", json={"username": "ada", "password": "supersecret123"}
    )

    assert response.status_code == 422


async def test_login_returns_token_pair(client):
    await register(client)
    response = await login(client, "ada", "supersecret123")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


@pytest.mark.parametrize(
    ("username", "password"),
    [("ada", "wrong-password"), ("nobody", "supersecret123")],
)
async def test_login_rejects_bad_credentials(client, username, password):
    await register(client)
    response = await login(client, username, password)

    assert response.status_code == 401
    # Identical message either way, so the response body reveals nothing.
    assert response.json()["detail"] == "Invalid username or password."


async def test_login_timing_does_not_reveal_valid_usernames(client):
    """Regression: the miss path used to skip Argon2 entirely, a 36x timing gap."""
    await register(client)

    async def median_ms(username):
        samples = []
        for _ in range(6):
            start = time.perf_counter()
            await login(client, username, "wrong-password")
            samples.append((time.perf_counter() - start) * 1000)
        return statistics.median(samples)

    existing = await median_ms("ada")
    missing = await median_ms("does-not-exist")

    ratio = max(existing, missing) / max(min(existing, missing), 0.001)
    assert ratio < 3, f"timing gap of {ratio:.1f}x still leaks username validity"


async def test_inactive_user_cannot_log_in(client):
    from sqlalchemy import update

    from app.database import AsyncSessionLocal
    from app.models import User

    await register(client)

    async with AsyncSessionLocal() as db:
        await db.execute(update(User).values(is_active=False))
        await db.commit()

    response = await login(client, "ada", "supersecret123")
    assert response.status_code == 403


async def test_refresh_issues_new_tokens(client):
    await register(client)
    tokens = (await login(client, "ada", "supersecret123")).json()

    await asyncio.sleep(1.05)  # exp has 1-second resolution

    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    assert response.json()["access_token"] != tokens["access_token"]


async def test_access_token_rejected_as_refresh_token(client):
    await register(client)
    tokens = (await login(client, "ada", "supersecret123")).json()

    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert response.status_code == 401


async def test_refresh_token_rejected_as_bearer_credential(client):
    await register(client)
    tokens = (await login(client, "ada", "supersecret123")).json()

    response = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )

    assert response.status_code == 401


async def test_garbage_token_is_rejected(client):
    response = await client.get(
        "/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


async def test_me_requires_authentication(client):
    assert (await client.get("/users/me")).status_code == 401


async def test_me_matches_register_shape(client):
    """Both endpoints describe the same entity, so the payloads should agree."""
    registered, _ = await register(client)
    headers = await auth_headers(client)

    me = await client.get("/users/me", headers=headers)

    assert me.status_code == 200
    assert me.json() == registered.json()


async def test_deactivated_user_loses_access_immediately(client):
    from sqlalchemy import update

    from app.database import AsyncSessionLocal
    from app.models import User

    await register(client)
    headers = await auth_headers(client)

    async with AsyncSessionLocal() as db:
        await db.execute(update(User).values(is_active=False))
        await db.commit()

    response = await client.get("/users/me", headers=headers)
    assert response.status_code == 403


async def test_password_is_hashed_with_argon2(client):
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models import User

    await register(client)

    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User))

    assert user.password != user_payload()["password"]
    assert user.password.startswith("$argon2")
