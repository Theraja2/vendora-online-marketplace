"""Database-level guarantees that the application layer must not be trusted for."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import AsyncSessionLocal
from app.models import Cart, CartItem, Category, Product, Review, Seller, User
from app.models.enums import Availability, Role


async def _base_rows(db):
    user = User(
        full_name="Ada", username="ada", email="ada@example.com",
        phone_number="+2547", password="x", role=Role.CUSTOMER.value,
    )
    db.add(user)
    await db.flush()

    seller = Seller(user_id=user.id, business_name="Ada Inc", is_approved=True)
    category = Category(name="Electronics", is_active=True)
    db.add_all([seller, category])
    await db.flush()

    product = Product(
        seller_id=seller.id, category_id=category.id, name="Engine",
        price=10, inventory=1, availability=Availability.IN_STOCK.value,
    )
    db.add(product)
    await db.flush()

    return user, product


@pytest.mark.parametrize("rating", [0, 6, -1, 999])
async def test_review_rating_must_be_1_to_5(client, rating):
    async with AsyncSessionLocal() as db:
        user, product = await _base_rows(db)
        db.add(Review(user_id=user.id, product_id=product.id, rating=rating))

        with pytest.raises(IntegrityError):
            await db.commit()


async def test_valid_review_rating_is_accepted(client):
    async with AsyncSessionLocal() as db:
        user, product = await _base_rows(db)
        db.add(Review(user_id=user.id, product_id=product.id, rating=5))
        await db.commit()


async def test_one_review_per_user_per_product(client):
    async with AsyncSessionLocal() as db:
        user, product = await _base_rows(db)
        db.add_all(
            [
                Review(user_id=user.id, product_id=product.id, rating=5),
                Review(user_id=user.id, product_id=product.id, rating=1),
            ]
        )

        with pytest.raises(IntegrityError):
            await db.commit()


async def test_a_product_appears_once_per_cart(client):
    async with AsyncSessionLocal() as db:
        user, product = await _base_rows(db)
        cart = Cart(user_id=user.id)
        db.add(cart)
        await db.flush()

        db.add_all(
            [
                CartItem(cart_id=cart.id, product_id=product.id, quantity=1),
                CartItem(cart_id=cart.id, product_id=product.id, quantity=2),
            ]
        )

        with pytest.raises(IntegrityError):
            await db.commit()


async def test_cart_quantity_must_be_positive(client):
    async with AsyncSessionLocal() as db:
        user, product = await _base_rows(db)
        cart = Cart(user_id=user.id)
        db.add(cart)
        await db.flush()

        db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=0))

        with pytest.raises(IntegrityError):
            await db.commit()


async def test_product_price_must_be_positive(client):
    async with AsyncSessionLocal() as db:
        _, product = await _base_rows(db)
        db.add(
            Product(
                seller_id=product.seller_id, category_id=product.category_id,
                name="Free", price=0, inventory=1,
                availability=Availability.IN_STOCK.value,
            )
        )

        with pytest.raises(IntegrityError):
            await db.commit()


async def test_role_must_be_a_known_value(client):
    async with AsyncSessionLocal() as db:
        db.add(
            User(
                full_name="Eve", username="eve", email="eve@example.com",
                phone_number="+9999", password="x", role="superuser",
            )
        )

        with pytest.raises(IntegrityError):
            await db.commit()


async def test_sqlite_enforces_foreign_keys(client):
    """Without PRAGMA foreign_keys=ON, SQLite ignores every ON DELETE CASCADE and
    the suite reports passes for behaviour that only works on PostgreSQL."""
    from sqlalchemy import text

    from app.database import engine

    if engine.dialect.name != "sqlite":
        return

    async with engine.connect() as conn:
        enabled = (await conn.execute(text("PRAGMA foreign_keys"))).scalar_one()

    assert enabled == 1, "foreign keys are not enforced -- cascade tests are meaningless"


async def test_seller_created_at_is_timezone_aware():
    """Regression: sellers.created_at was the only naive TIMESTAMP column."""
    from sqlalchemy.dialects import postgresql

    from app.database import Base

    naive = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if column.name in ("created_at", "updated_at"):
                compiled = column.type.compile(postgresql.dialect())
                if "WITH TIME ZONE" not in compiled:
                    naive.append(f"{table.name}.{column.name}")

    assert naive == [], f"timezone-naive timestamp columns: {naive}"
