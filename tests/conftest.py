"""Test fixtures.

Every test runs against a fresh in-memory-ish SQLite file so the suite needs no
PostgreSQL and leaves nothing behind. The env vars are set before app.config is
imported, because Settings() is evaluated at import time.
"""

import os
import tempfile
from pathlib import Path

import pytest

_TMP_DB = Path(tempfile.gettempdir()) / "vendora_test.sqlite3"

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP_DB}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DEBUG", "false")

import httpx  # noqa: E402
from sqlalchemy import update  # noqa: E402

from app.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Category, User  # noqa: E402
from app.models.enums import Role  # noqa: E402


@pytest.fixture(autouse=True)
async def fresh_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as async_client:
        yield async_client


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def user_payload(**overrides):
    payload = {
        "full_name": "Ada Lovelace",
        "username": "ada",
        "email": "ada@example.com",
        "phone_number": "+254700000001",
        "password": "supersecret123",
    }
    payload.update(overrides)
    return payload


async def register(client, **overrides):
    payload = user_payload(**overrides)
    response = await client.post("/auth/register", json=payload)
    return response, payload


async def login(client, username, password):
    response = await client.post(
        "/auth/login", data={"username": username, "password": password}
    )
    return response


async def auth_headers(client, username="ada", password="supersecret123"):
    response = await login(client, username, password)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_admin(username):
    """Seed an admin directly, mirroring what the FIRST_ADMIN_* settings do on startup."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(User).where(User.username == username).values(role=Role.ADMIN.value)
        )
        await db.commit()


async def seed_category(name="Electronics", is_active=True):
    async with AsyncSessionLocal() as db:
        category = Category(name=name, description="seeded", is_active=is_active)
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category.id


@pytest.fixture
async def approved_seller(client):
    """A registered, approved seller plus their auth headers and a live category.

    Built entirely through the public API -- registering, applying, and being
    approved by an admin -- so it also proves the role flow actually works.
    """
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    admin_headers = await auth_headers(client, "root")
    seller_headers = await auth_headers(client, "ada")

    await client.post(
        "/sellers/register",
        headers=seller_headers,
        json={"business_name": "Ada Engines", "business_description": "Fine engines"},
    )
    await client.patch("/sellers/1/approve", headers=admin_headers)

    category = await client.post(
        "/categories", headers=admin_headers, json={"name": "Electronics"}
    )

    # role changed on approval, so re-issue the token to pick it up
    seller_headers = await auth_headers(client, "ada")

    return {
        "seller_headers": seller_headers,
        "admin_headers": admin_headers,
        "category_id": category.json()["id"],
    }


async def create_product(client, headers, category_id, **overrides):
    payload = {
        "name": "Difference Engine",
        "description": "Brass and steam",
        "price": "1999.99",
        "inventory": 5,
        "category_id": category_id,
    }
    payload.update(overrides)
    return await client.post("/products", headers=headers, json=payload)
