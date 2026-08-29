"""Admin bootstrapping and role management -- what replaced the CLI."""

import pytest
from sqlalchemy import select

from app.bootstrap import ensure_first_admin
from app.database import AsyncSessionLocal
from app.models import User
from app.models.enums import Role
from app.security.password import verify_password
from tests.conftest import auth_headers, make_admin, register


@pytest.fixture
def admin_settings(monkeypatch):
    """Point the FIRST_ADMIN_* settings at a known account."""
    from app.bootstrap import settings

    monkeypatch.setattr(settings, "FIRST_ADMIN_USERNAME", "seededadmin")
    monkeypatch.setattr(settings, "FIRST_ADMIN_PASSWORD", "seeded-password-123")
    monkeypatch.setattr(settings, "FIRST_ADMIN_EMAIL", "seeded@example.com")
    monkeypatch.setattr(settings, "FIRST_ADMIN_FULL_NAME", "Seeded Admin")
    monkeypatch.setattr(settings, "FIRST_ADMIN_PHONE", "+254700000123")
    return settings


# --------------------------------------------------------------------------
# Seeding the first admin
# --------------------------------------------------------------------------

async def test_seeding_creates_the_first_admin(client, admin_settings):
    await ensure_first_admin()

    async with AsyncSessionLocal() as db:
        admin = await db.scalar(select(User).where(User.username == "seededadmin"))

    assert admin is not None
    assert admin.role == Role.ADMIN.value
    assert admin.is_active is True
    assert verify_password("seeded-password-123", admin.password)


async def test_seeded_admin_can_log_in(client, admin_settings):
    await ensure_first_admin()

    response = await client.post(
        "/auth/login",
        data={"username": "seededadmin", "password": "seeded-password-123"},
    )

    assert response.status_code == 200

    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = await client.get("/users/me", headers=headers)
    assert me.json()["role"] == "admin"


async def test_seeding_runs_more_than_once_safely(client, admin_settings):
    """It runs on every boot, so it must never create a duplicate."""
    await ensure_first_admin()
    await ensure_first_admin()
    await ensure_first_admin()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == "seededadmin")
        )
        admins = result.scalars().all()

    assert len(admins) == 1


async def test_seeding_is_skipped_when_unconfigured(client, monkeypatch):
    from app.bootstrap import settings

    monkeypatch.setattr(settings, "FIRST_ADMIN_USERNAME", None)
    monkeypatch.setattr(settings, "FIRST_ADMIN_PASSWORD", None)

    await ensure_first_admin()

    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(User))).scalars().all()

    assert total == []


async def test_seeding_rejects_a_short_password(client, admin_settings, monkeypatch):
    from app.bootstrap import settings

    monkeypatch.setattr(settings, "FIRST_ADMIN_PASSWORD", "short")

    await ensure_first_admin()

    async with AsyncSessionLocal() as db:
        admin = await db.scalar(select(User).where(User.username == "seededadmin"))

    assert admin is None


async def test_seeding_leaves_an_existing_non_admin_alone(client, admin_settings):
    """A name collision must not silently promote someone's ordinary account."""
    await register(client, username="seededadmin", email="someone@example.com",
                   phone_number="+254700000555")

    await ensure_first_admin()

    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == "seededadmin"))

    assert user.role == Role.CUSTOMER.value


# --------------------------------------------------------------------------
# Listing users
# --------------------------------------------------------------------------

async def test_admin_can_list_users(client):
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    headers = await auth_headers(client, "root")
    response = await client.get("/users", headers=headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


async def test_user_list_can_filter_by_role(client):
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    headers = await auth_headers(client, "root")
    admins = await client.get("/users?role=admin", headers=headers)
    customers = await client.get("/users?role=customer", headers=headers)

    assert admins.json()["total"] == 1
    assert customers.json()["total"] == 1


async def test_customers_cannot_list_users(client):
    await register(client)
    headers = await auth_headers(client)

    assert (await client.get("/users", headers=headers)).status_code == 403


async def test_user_list_never_exposes_password_hashes(client):
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    headers = await auth_headers(client, "root")
    body = (await client.get("/users", headers=headers)).json()

    assert all("password" not in item for item in body["items"])


# --------------------------------------------------------------------------
# Changing roles
# --------------------------------------------------------------------------

async def test_admin_can_promote_a_user(client):
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    headers = await auth_headers(client, "root")
    response = await client.patch("/users/1/role", headers=headers,
                                  json={"role": "admin"})

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_a_promoted_admin_gains_admin_powers(client):
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    admin_headers = await auth_headers(client, "root")

    ada_headers = await auth_headers(client, "ada")
    assert (await client.post("/categories", headers=ada_headers,
                              json={"name": "Too Early"})).status_code == 403

    await client.patch("/users/1/role", headers=admin_headers, json={"role": "admin"})

    # a fresh token picks up the new role
    ada_headers = await auth_headers(client, "ada")
    assert (await client.post("/categories", headers=ada_headers,
                              json={"name": "Electronics"})).status_code == 201


async def test_admin_cannot_change_their_own_role(client):
    """Self-demotion would lock the last admin out with no way back through the API."""
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    headers = await auth_headers(client, "root")
    response = await client.patch("/users/1/role", headers=headers,
                                  json={"role": "customer"})

    assert response.status_code == 403
    assert (await client.get("/users/me", headers=headers)).json()["role"] == "admin"


async def test_customers_cannot_change_roles(client):
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="mal", email="mal@example.com",
                   phone_number="+254700000002")

    headers = await auth_headers(client, "mal")
    response = await client.patch("/users/1/role", headers=headers,
                                  json={"role": "admin"})

    assert response.status_code == 403


async def test_changing_the_role_of_a_missing_user_is_404(client):
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    headers = await auth_headers(client, "root")
    response = await client.patch("/users/999/role", headers=headers,
                                  json={"role": "admin"})

    assert response.status_code == 404


async def test_unknown_roles_are_rejected(client):
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    headers = await auth_headers(client, "root")
    response = await client.patch("/users/1/role", headers=headers,
                                  json={"role": "superuser"})

    assert response.status_code == 422


async def test_a_bad_admin_email_is_rejected_at_startup():
    """Regression: an invalid FIRST_ADMIN_EMAIL created an account that then made
    every endpoint returning that user fail with a 500."""
    import pydantic

    from app.config import Settings

    with pytest.raises(pydantic.ValidationError):
        Settings(
            _env_file=None,          # ignore any .env the developer happens to have
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            SECRET_KEY="x" * 40,
            FIRST_ADMIN_EMAIL="admin@vendora.test",   # .test is a reserved TLD
        )


async def test_the_cli_module_is_gone():
    """Replaced by .env seeding and the /users endpoints."""
    import importlib

    for removed in ("app.cli", "app.rate_limit"):
        try:
            importlib.import_module(removed)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{removed} still exists")
