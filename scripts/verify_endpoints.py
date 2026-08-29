"""Exercise every endpoint against the real database configured in .env.

    python scripts/verify_endpoints.py

The test suite (`pytest`) runs against SQLite so it needs no database. This
script runs the same app against whatever DATABASE_URL points at, which is what
proves the PostgreSQL-specific behaviour: the partial unique index on primary
images, timezone-aware timestamps, real ILIKE search, and NUMERIC precision.

It creates a handful of rows with a random suffix and deletes them all before
exiting, so it is safe to run against a database you care about.
"""

import asyncio
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import delete, select, text

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.main import app, lifespan
from app.models import Category, Product, ProductImage, Seller, User

TAG = secrets.token_hex(3)
GREEN, RED, YELLOW, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)

results: list[tuple[str, str, bool, str]] = []


def check(group: str, label: str, ok: bool, detail: str = "") -> bool:
    results.append((group, label, ok, detail))
    mark = f"{GREEN}PASS{OFF}" if ok else f"{RED}FAIL{OFF}"
    print(f"  {mark}  {label}" + (f"{DIM}  {detail}{OFF}" if detail else ""))
    return ok


def head(title: str) -> None:
    print(f"\n{BOLD}{title}{OFF}")


async def preflight() -> bool:
    """Fail early and clearly rather than deep inside a request."""
    head("Configuration")

    if "<YOUR_POSTGRES_PASSWORD>" in settings.DATABASE_URL:
        print(f"  {RED}FAIL{OFF}  DATABASE_URL still contains the placeholder password.")
        print("        Edit .env and replace <YOUR_POSTGRES_PASSWORD> with your")
        print("        postgres password, then run this again.")
        return False

    shown = settings.DATABASE_URL
    if "@" in shown and "://" in shown:
        scheme, rest = shown.split("://", 1)
        creds, host = rest.rsplit("@", 1)
        user = creds.split(":", 1)[0]
        shown = f"{scheme}://{user}:***@{host}"
    check("config", "DATABASE_URL is set", True, shown)
    check("config", "SECRET_KEY length", len(settings.SECRET_KEY) >= 32,
          f"{len(settings.SECRET_KEY)} chars")

    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SELECT version()"))).scalar_one()
            db = (await conn.execute(text("SELECT current_database()"))).scalar_one()
    except Exception as exc:  # noqa: BLE001
        print(f"  {RED}FAIL{OFF}  Cannot connect: {type(exc).__name__}: {exc}")
        print("        Check the password in .env, and that the database exists.")
        return False

    check("config", "database reachable", True, f"{db} · {version.split(',')[0]}")

    async with engine.connect() as conn:
        tables = (await conn.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='public'"
        ))).scalar_one()

    if not check("config", "schema is migrated", tables >= 11,
                 f"{tables} tables in public"):
        print(f"        Run: {BOLD}alembic upgrade head{OFF}")
        return False

    return True


async def cleanup() -> None:
    """Remove everything this run created."""
    async with AsyncSessionLocal() as db:
        products = (await db.execute(
            select(Product).where(Product.name.like(f"%{TAG}%"))
        )).scalars().all()

        for product in products:
            await db.execute(
                delete(ProductImage).where(ProductImage.product_id == product.id)
            )
            await db.delete(product)

        await db.flush()

        users = (await db.execute(
            select(User).where(User.username.like(f"%{TAG}%"))
        )).scalars().all()

        for user in users:
            await db.execute(delete(Seller).where(Seller.user_id == user.id))
            await db.delete(user)

        await db.execute(delete(Category).where(Category.name.like(f"%{TAG}%")))
        await db.commit()


async def main() -> int:
    print(f"{BOLD}Vendora endpoint verification{OFF}  {DIM}run tag {TAG}{OFF}")

    if not await preflight():
        return 1

    async with lifespan(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://verify.local"
        ) as c:

            # ---------------------------------------------------------------
            head("Public")
            r = await c.get("/")
            check("public", "GET /", r.status_code == 200, f"{r.status_code}")
            r = await c.get("/health")
            check("public", "GET /health",
                  r.status_code == 200 and r.json() == {"status": "ok"}, f"{r.status_code}")

            r = await c.request("OPTIONS", "/auth/login", headers={
                "Origin": settings.CORS_ORIGINS[0],
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            })
            allow = r.headers.get("access-control-allow-origin", "")
            check("public", "CORS preflight", r.status_code == 200 and allow != "",
                  f"{r.status_code} · allow-origin: {allow or 'NONE'}")

            # ---------------------------------------------------------------
            head("Admin bootstrap")
            r = await c.post("/auth/login", data={
                "username": settings.FIRST_ADMIN_USERNAME,
                "password": settings.FIRST_ADMIN_PASSWORD,
            })
            if not check("admin", "seeded admin can log in", r.status_code == 200,
                         f"{r.status_code} · user {settings.FIRST_ADMIN_USERNAME!r}"):
                print("        FIRST_ADMIN_* in .env may not match the existing account.")
                return 1

            AH = {"Authorization": f"Bearer {r.json()['access_token']}"}
            r = await c.get("/users/me", headers=AH)
            check("admin", "admin has the admin role",
                  r.json().get("role") == "admin", f"role={r.json().get('role')}")

            # ---------------------------------------------------------------
            head("Registration and login")
            user = {
                "full_name": "Verify Runner",
                "username": f"seller_{TAG}",
                "email": f"seller_{TAG}@example.com",
                "phone_number": f"+2547{TAG[:6]}",
                "password": "supersecret123",
            }
            r = await c.post("/auth/register", json=user)
            check("auth", "POST /auth/register", r.status_code == 201,
                  f"{r.status_code} · role={r.json().get('role')}")

            r = await c.post("/auth/register", json=user)
            check("auth", "duplicate username rejected", r.status_code == 409,
                  f"{r.status_code} · {r.json().get('detail')}")

            r = await c.post("/auth/register", json=dict(
                user, username=f"other_{TAG}", email=f"other_{TAG}@example.com"))
            check("auth", "duplicate phone reported accurately",
                  r.status_code == 409 and "Phone" in str(r.json().get("detail")),
                  f"{r.json().get('detail')}")

            r = await c.post("/auth/login", data={
                "username": user["username"], "password": user["password"]})
            check("auth", "POST /auth/login", r.status_code == 200, f"{r.status_code}")
            tokens = r.json()
            SH = {"Authorization": f"Bearer {tokens['access_token']}"}

            r = await c.post("/auth/login", data={
                "username": user["username"], "password": "wrong"})
            check("auth", "bad password rejected", r.status_code == 401, f"{r.status_code}")

            r = await c.post("/auth/refresh",
                             json={"refresh_token": tokens["refresh_token"]})
            check("auth", "POST /auth/refresh", r.status_code == 200, f"{r.status_code}")

            r = await c.get("/users/me", headers=SH)
            check("auth", "GET /users/me", r.status_code == 200,
                  f"{r.status_code} · {r.json().get('username')}")

            r = await c.get("/users/me")
            check("auth", "unauthenticated request rejected", r.status_code == 401,
                  f"{r.status_code}")

            # ---------------------------------------------------------------
            head("Admin: users")
            r = await c.get("/users", headers=AH)
            check("users", "GET /users", r.status_code == 200,
                  f"{r.status_code} · total={r.json().get('total')}")

            r = await c.get("/users?role=admin", headers=AH)
            check("users", "GET /users?role= filter", r.status_code == 200,
                  f"total={r.json().get('total')} admins")

            r = await c.get("/users", headers=SH)
            check("users", "non-admin blocked", r.status_code == 403, f"{r.status_code}")

            me_id = (await c.get("/users/me", headers=AH)).json()["id"]
            r = await c.patch(f"/users/{me_id}/role", headers=AH,
                              json={"role": "customer"})
            check("users", "admin cannot demote themselves", r.status_code == 403,
                  f"{r.status_code}")

            # ---------------------------------------------------------------
            head("Categories")
            r = await c.post("/categories", headers=AH,
                             json={"name": f"Electronics {TAG}",
                                   "description": "verification run"})
            check("categories", "POST /categories", r.status_code == 201,
                  f"{r.status_code}")
            category_id = r.json().get("id")

            r = await c.post("/categories", headers=SH, json={"name": f"Nope {TAG}"})
            check("categories", "non-admin blocked", r.status_code == 403,
                  f"{r.status_code}")

            r = await c.get("/categories")
            body = r.json()
            check("categories", "GET /categories", r.status_code == 200,
                  f"{r.status_code} · total={body.get('total')}")
            check("categories", "paginated envelope",
                  {"items", "total", "limit", "offset"} <= set(body),
                  f"keys={sorted(body)}")

            r = await c.get(f"/categories/{category_id}")
            check("categories", "GET /categories/{id}", r.status_code == 200,
                  f"{r.status_code}")

            # ---------------------------------------------------------------
            head("Seller onboarding")
            r = await c.post("/sellers/register", headers=SH,
                             json={"business_name": f"Verify Engines {TAG}"})
            check("sellers", "POST /sellers/register", r.status_code == 201,
                  f"{r.status_code} · approved={r.json().get('is_approved')}")
            seller_id = r.json().get("id")

            r = await c.get("/sellers/me", headers=SH)
            check("sellers", "GET /sellers/me", r.status_code == 200, f"{r.status_code}")

            r = await c.post("/products", headers=SH, json={
                "name": f"Too Early {TAG}", "price": "1.00",
                "inventory": 1, "category_id": category_id})
            check("sellers", "unapproved seller cannot list products",
                  r.status_code == 403, f"{r.status_code}")

            r = await c.get("/sellers?pending_only=true", headers=AH)
            check("sellers", "GET /sellers (admin)", r.status_code == 200,
                  f"{r.status_code} · pending={r.json().get('total')}")

            r = await c.patch(f"/sellers/{seller_id}/approve", headers=AH)
            check("sellers", "PATCH /sellers/{id}/approve", r.status_code == 200,
                  f"{r.status_code} · approved={r.json().get('is_approved')}")

            r = await c.post("/auth/login", data={
                "username": user["username"], "password": user["password"]})
            SH = {"Authorization": f"Bearer {r.json()['access_token']}"}
            role = (await c.get("/users/me", headers=SH)).json()["role"]
            check("sellers", "approval granted the seller role", role == "seller",
                  f"role={role}")

            # ---------------------------------------------------------------
            head("Products")
            r = await c.post("/products", headers=SH, json={
                "name": f"Difference Engine {TAG}",
                "description": "Brass and steam",
                "price": "1999.99", "inventory": 5, "category_id": category_id})
            check("products", "POST /products", r.status_code == 201,
                  f"{r.status_code} · availability={r.json().get('availability')}")
            product_id = r.json().get("id")
            created = r.json()

            r = await c.post("/products", headers=SH, json={
                "name": f"Bad Price {TAG}", "price": "-1.00",
                "inventory": 1, "category_id": category_id})
            check("products", "negative price rejected", r.status_code == 422,
                  f"{r.status_code}")

            r = await c.get(f"/products/{product_id}")
            check("products", "GET /products/{id}", r.status_code == 200,
                  f"{r.status_code}")

            r = await c.get("/products")
            check("products", "GET /products", r.status_code == 200,
                  f"{r.status_code} · total={r.json().get('total')}")

            r = await c.get(f"/products?limit=1&category_id={category_id}")
            check("products", "pagination + category filter",
                  r.status_code == 200 and len(r.json()["items"]) <= 1,
                  f"returned {len(r.json()['items'])} of {r.json()['total']}")

            r = await c.get("/products?search=DIFFERENCE")
            check("products", "case-insensitive search (real ILIKE on PostgreSQL)",
                  r.status_code == 200 and r.json()["total"] >= 1,
                  f"matched {r.json().get('total')}")

            r = await c.get("/products?sort_by=price&sort_dir=asc")
            check("products", "sorting", r.status_code == 200, f"{r.status_code}")

            r = await c.get("/products?limit=9999")
            check("products", "limit is bounded", r.status_code == 422, f"{r.status_code}")

            r = await c.patch(f"/products/{product_id}", headers=SH,
                              json={"inventory": 0})
            check("products", "PATCH /products/{id} recalculates availability",
                  r.json().get("availability") == "OUT_OF_STOCK",
                  f"availability={r.json().get('availability')}")

            r = await c.patch(f"/products/{product_id}", headers=SH,
                              json={"seller_id": 99999, "id": 1})
            check("products", "unknown fields ignored (no mass assignment)",
                  r.json().get("id") == product_id
                  and r.json().get("seller_id") == seller_id,
                  f"id={r.json().get('id')} seller_id={r.json().get('seller_id')}")

            # ---------------------------------------------------------------
            head("Product images")
            r = await c.post(f"/products/{product_id}/images", headers=SH,
                             json={"image_url": "not-a-url"})
            check("images", "invalid URL rejected", r.status_code == 422,
                  f"{r.status_code}")

            r = await c.post(f"/products/{product_id}/images", headers=SH, json={
                "image_url": "https://cdn.example.com/a.jpg", "is_primary": True})
            check("images", "POST /products/{id}/images", r.status_code == 201,
                  f"{r.status_code}")
            image_id = r.json().get("id")

            responses = await asyncio.gather(*[
                c.post(f"/products/{product_id}/images", headers=SH, json={
                    "image_url": f"https://cdn.example.com/race{i}.jpg",
                    "is_primary": True, "sort_order": i + 1})
                for i in range(4)
            ])
            codes = [x.status_code for x in responses]
            images = (await c.get(f"/products/{product_id}/images")).json()
            primaries = sum(1 for i in images if i["is_primary"])
            check("images", "concurrent primaries — partial unique index holds",
                  primaries <= 1 and all(x in (201, 409) for x in codes),
                  f"codes={codes} · primaries={primaries}")

            r = await c.post(f"/products/{product_id}/images", headers=SH, json={
                "image_url": "https://cdn.example.com/after.jpg", "is_primary": True})
            check("images", "endpoint still works after the race (no 500 wedge)",
                  r.status_code == 201, f"{r.status_code}")

            r = await c.get(f"/products/{product_id}/images")
            check("images", "GET /products/{id}/images", r.status_code == 200,
                  f"{r.status_code} · {len(r.json())} images")

            r = await c.delete(f"/products/{product_id}/images/{image_id}", headers=SH)
            check("images", "DELETE image", r.status_code == 204, f"{r.status_code}")

            # ---------------------------------------------------------------
            head("Ownership isolation")
            other = dict(user, username=f"mal_{TAG}", email=f"mal_{TAG}@example.com",
                         phone_number=f"+2548{TAG[:6]}")
            await c.post("/auth/register", json=other)
            r = await c.post("/auth/login", data={
                "username": other["username"], "password": other["password"]})
            MH = {"Authorization": f"Bearer {r.json()['access_token']}"}

            r = await c.patch(f"/products/{product_id}", headers=MH,
                              json={"name": "HIJACKED"})
            check("isolation", "another account cannot edit the product",
                  r.status_code == 403, f"{r.status_code}")

            r = await c.delete(f"/products/{product_id}", headers=MH)
            check("isolation", "another account cannot delete the product",
                  r.status_code == 403, f"{r.status_code}")

            # ---------------------------------------------------------------
            head("Database-level guarantees")
            check("database", "NUMERIC(12,2) precision preserved",
                  created["price"] == "1999.99", f"price={created['price']!r}")

            if engine.dialect.name == "postgresql":
                check("database", "timestamps are timezone-aware",
                      any(m in created["created_at"] for m in ("+", "Z")),
                      f"created_at={created['created_at']}")

                async with engine.connect() as conn:
                    idx = (await conn.execute(text(
                        "SELECT indexdef FROM pg_indexes "
                        "WHERE indexname='uq_product_images_one_primary'"
                    ))).scalar_one_or_none()
                check("database", "partial unique index exists in the database",
                      idx is not None and "WHERE" in (idx or ""),
                      (idx or "not found")[:74])

                async with engine.connect() as conn:
                    constraints = (await conn.execute(text(
                        "SELECT count(*) FROM pg_constraint WHERE contype='c' "
                        "AND conname LIKE 'ck_%'"
                    ))).scalar_one()
                check("database", "CHECK constraints present", constraints >= 8,
                      f"{constraints} ck_* constraints")
            else:
                print(f"  {YELLOW}SKIP{OFF}  PostgreSQL-only checks "
                      f"{DIM}(dialect is {engine.dialect.name}){OFF}")

            # ---------------------------------------------------------------
            head("Cleanup")
            r = await c.delete(f"/products/{product_id}", headers=SH)
            check("cleanup", "DELETE /products/{id}", r.status_code == 204,
                  f"{r.status_code}")

    await cleanup()
    print(f"  {DIM}removed every row tagged {TAG}{OFF}")

    # ------------------------------------------------------------------
    failed = [r for r in results if not r[2]]
    total = len(results)

    print(f"\n{BOLD}{'─' * 62}{OFF}")
    if failed:
        print(f"{RED}{BOLD}  {len(failed)} of {total} checks FAILED{OFF}")
        for group, label, _, detail in failed:
            print(f"    {RED}·{OFF} [{group}] {label}  {DIM}{detail}{OFF}")
    else:
        print(f"{GREEN}{BOLD}  All {total} checks passed — every endpoint works.{OFF}")
        print(f"{DIM}  Safe to expose through ngrok. Remember to add the ngrok URL"
              f" to CORS_ORIGINS.{OFF}")
    print(f"{BOLD}{'─' * 62}{OFF}")

    await engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
