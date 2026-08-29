"""Product CRUD, pagination, filtering, and ownership isolation."""

import asyncio

from tests.conftest import auth_headers, create_product, register


async def test_create_product_sets_availability_from_inventory(client, approved_seller):
    headers, category_id = (
        approved_seller["seller_headers"],
        approved_seller["category_id"],
    )

    in_stock = await create_product(client, headers, category_id, inventory=5)
    sold_out = await create_product(
        client, headers, category_id, name="Sold Out", inventory=0
    )

    assert in_stock.json()["availability"] == "IN_STOCK"
    assert sold_out.json()["availability"] == "OUT_OF_STOCK"


async def test_create_product_rejects_inactive_category(client, approved_seller):
    from tests.conftest import seed_category

    inactive_id = await seed_category("Retired", is_active=False)

    response = await create_product(
        client, approved_seller["seller_headers"], inactive_id
    )

    assert response.status_code == 404


async def test_create_product_rejects_bad_prices(client, approved_seller):
    headers, category_id = (
        approved_seller["seller_headers"],
        approved_seller["category_id"],
    )

    negative = await create_product(client, headers, category_id, price="-5.00")
    too_precise = await create_product(client, headers, category_id, price="10.12345")

    assert negative.status_code == 422
    assert too_precise.status_code == 422


async def test_price_serialises_as_a_decimal_string(client, approved_seller):
    """The frontend must convert this before doing arithmetic -- documented behaviour."""
    response = await create_product(
        client, approved_seller["seller_headers"], approved_seller["category_id"],
        price="1999.99",
    )

    assert response.json()["price"] == "1999.99"


async def test_list_products_is_paginated(client, approved_seller):
    """Regression: GET /products returned the whole catalogue and ignored limit."""
    headers, category_id = (
        approved_seller["seller_headers"],
        approved_seller["category_id"],
    )
    for index in range(7):
        await create_product(client, headers, category_id, name=f"Widget {index}")

    response = await client.get("/products?limit=2")
    body = response.json()

    assert body["total"] == 7
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


async def test_pagination_offset_walks_the_catalogue(client, approved_seller):
    headers, category_id = (
        approved_seller["seller_headers"],
        approved_seller["category_id"],
    )
    for index in range(5):
        await create_product(client, headers, category_id, name=f"Widget {index}")

    first = (await client.get("/products?limit=2&offset=0")).json()
    second = (await client.get("/products?limit=2&offset=2")).json()

    first_ids = {item["id"] for item in first["items"]}
    second_ids = {item["id"] for item in second["items"]}

    assert not first_ids & second_ids, "pages overlap"


async def test_search_filters_by_name(client, approved_seller):
    headers, category_id = (
        approved_seller["seller_headers"],
        approved_seller["category_id"],
    )
    await create_product(client, headers, category_id, name="Difference Engine")
    await create_product(client, headers, category_id, name="Brass Telescope")

    response = await client.get("/products?search=engine")
    body = response.json()

    assert body["total"] == 1
    assert body["items"][0]["name"] == "Difference Engine"


async def test_search_is_case_insensitive(client, approved_seller):
    await create_product(
        client, approved_seller["seller_headers"], approved_seller["category_id"],
        name="Difference Engine",
    )

    assert (await client.get("/products?search=ENGINE")).json()["total"] == 1


async def test_filters_combine(client, approved_seller):
    headers, category_id = (
        approved_seller["seller_headers"],
        approved_seller["category_id"],
    )
    await create_product(client, headers, category_id, name="Cheap", price="5.00",
                         inventory=3)
    await create_product(client, headers, category_id, name="Pricey", price="500.00",
                         inventory=0)

    in_budget = await client.get("/products?max_price=100&in_stock_only=true")

    assert in_budget.json()["total"] == 1
    assert in_budget.json()["items"][0]["name"] == "Cheap"


async def test_sorting_by_price(client, approved_seller):
    headers, category_id = (
        approved_seller["seller_headers"],
        approved_seller["category_id"],
    )
    expensive = await create_product(
        client, headers, category_id, name="Expensive Widget", price="50.00"
    )
    cheap = await create_product(
        client, headers, category_id, name="Cheap Widget", price="10.00"
    )
    assert expensive.status_code == 201 and cheap.status_code == 201

    ascending = await client.get("/products?sort_by=price&sort_dir=asc")
    descending = await client.get("/products?sort_by=price&sort_dir=desc")

    assert [item["price"] for item in ascending.json()["items"]] == ["10.00", "50.00"]
    assert [item["price"] for item in descending.json()["items"]] == ["50.00", "10.00"]


async def test_invalid_limit_is_rejected(client):
    assert (await client.get("/products?limit=1000")).status_code == 422
    assert (await client.get("/products?offset=-1")).status_code == 422


async def test_products_in_inactive_categories_are_hidden(client, approved_seller):
    from sqlalchemy import update

    from app.database import AsyncSessionLocal
    from app.models import Category

    await create_product(
        client, approved_seller["seller_headers"], approved_seller["category_id"]
    )

    async with AsyncSessionLocal() as db:
        await db.execute(update(Category).values(is_active=False))
        await db.commit()

    assert (await client.get("/products")).json()["total"] == 0
    assert (await client.get("/products/1")).status_code == 404


async def test_update_recalculates_availability(client, approved_seller):
    headers = approved_seller["seller_headers"]
    await create_product(client, headers, approved_seller["category_id"], inventory=5)

    response = await client.patch("/products/1", headers=headers, json={"inventory": 0})

    assert response.json()["availability"] == "OUT_OF_STOCK"


async def test_update_ignores_unknown_fields(client, approved_seller):
    """Mass assignment: seller_id and id must not be settable from the request body."""
    headers = approved_seller["seller_headers"]
    await create_product(client, headers, approved_seller["category_id"])

    response = await client.patch(
        "/products/1",
        headers=headers,
        json={"seller_id": 99, "id": 999, "availability": "HACKED"},
    )

    body = response.json()
    assert body["id"] == 1
    assert body["seller_id"] == 1
    assert body["availability"] in ("IN_STOCK", "OUT_OF_STOCK")


async def test_delete_product(client, approved_seller):
    headers = approved_seller["seller_headers"]
    await create_product(client, headers, approved_seller["category_id"])

    response = await client.delete("/products/1", headers=headers)

    assert response.status_code == 204
    assert (await client.get("/products/1")).status_code == 404


async def test_delete_product_that_has_images(client, approved_seller):
    """Regression: deleting a product with images returned 500.

    SQLAlchemy de-associates children by setting their foreign key to NULL unless
    told otherwise, and product_images.product_id is NOT NULL. The earlier test
    passed only because its product had no images.
    """
    headers = approved_seller["seller_headers"]
    await create_product(client, headers, approved_seller["category_id"])

    for index in range(3):
        await client.post(
            "/products/1/images",
            headers=headers,
            json={
                "image_url": f"https://cdn.example.com/{index}.jpg",
                "is_primary": index == 0,
                "sort_order": index,
            },
        )

    response = await client.delete("/products/1", headers=headers)

    assert response.status_code == 204
    assert (await client.get("/products/1")).status_code == 404
    assert (await client.get("/products/1/images")).status_code == 404


async def test_deleting_a_product_removes_its_images_from_the_database(
    client, approved_seller
):
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models import ProductImage

    headers = approved_seller["seller_headers"]
    await create_product(client, headers, approved_seller["category_id"])
    await client.post("/products/1/images", headers=headers,
                      json={"image_url": "https://cdn.example.com/a.jpg"})

    await client.delete("/products/1", headers=headers)

    async with AsyncSessionLocal() as db:
        orphans = (await db.execute(select(ProductImage))).scalars().all()

    assert orphans == [], "images outlived the product they belonged to"


async def _second_seller(client):
    await register(client, username="mal", email="mal@example.com",
                   phone_number="+254700000777")
    headers = await auth_headers(client, "mal")
    await client.post(
        "/sellers/register", headers=headers, json={"business_name": "Mallory Inc"}
    )
    return headers


async def test_sellers_cannot_touch_each_others_products(client, approved_seller):
    await create_product(
        client, approved_seller["seller_headers"], approved_seller["category_id"]
    )

    mallory = await _second_seller(client)
    await client.patch("/sellers/2/approve", headers=approved_seller["admin_headers"])
    mallory = await auth_headers(client, "mal")

    update = await client.patch(
        "/products/1", headers=mallory, json={"name": "HIJACKED"}
    )
    delete = await client.delete("/products/1", headers=mallory)
    image = await client.post(
        "/products/1/images",
        headers=mallory,
        json={"image_url": "https://evil.example.com/x.jpg"},
    )

    assert update.status_code == 403
    assert delete.status_code == 403
    assert image.status_code == 403

    unchanged = await client.get("/products/1")
    assert unchanged.json()["name"] == "Difference Engine"


async def test_concurrent_creates_all_succeed(client, approved_seller):
    headers, category_id = (
        approved_seller["seller_headers"],
        approved_seller["category_id"],
    )

    results = await asyncio.gather(
        *[
            create_product(client, headers, category_id, name=f"Widget {index}")
            for index in range(5)
        ]
    )

    assert all(response.status_code == 201 for response in results)
    assert (await client.get("/products")).json()["total"] == 5
