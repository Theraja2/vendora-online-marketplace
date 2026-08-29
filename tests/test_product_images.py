"""Product images -- the primary-image invariant that used to wedge at HTTP 500."""

import asyncio

from tests.conftest import create_product


async def _product(client, approved_seller):
    await create_product(
        client, approved_seller["seller_headers"], approved_seller["category_id"]
    )
    return approved_seller["seller_headers"]


async def test_add_image(client, approved_seller):
    headers = await _product(client, approved_seller)

    response = await client.post(
        "/products/1/images",
        headers=headers,
        json={"image_url": "https://cdn.example.com/a.jpg", "is_primary": True},
    )

    assert response.status_code == 201
    assert response.json()["is_primary"] is True


async def test_image_url_must_be_a_url(client, approved_seller):
    """Regression: any string was accepted, including 'not-a-url-at-all'."""
    headers = await _product(client, approved_seller)

    response = await client.post(
        "/products/1/images", headers=headers, json={"image_url": "not-a-url-at-all"}
    )

    assert response.status_code == 422


async def test_setting_a_new_primary_demotes_the_old_one(client, approved_seller):
    headers = await _product(client, approved_seller)

    await client.post(
        "/products/1/images",
        headers=headers,
        json={"image_url": "https://cdn.example.com/a.jpg", "is_primary": True},
    )
    await client.post(
        "/products/1/images",
        headers=headers,
        json={"image_url": "https://cdn.example.com/b.jpg", "is_primary": True,
              "sort_order": 1},
    )

    images = (await client.get("/products/1/images")).json()
    primaries = [image for image in images if image["is_primary"]]

    assert len(primaries) == 1
    assert primaries[0]["image_url"] == "https://cdn.example.com/b.jpg"


async def test_concurrent_primary_uploads_keep_the_invariant(client, approved_seller):
    """Regression: 4 parallel is_primary=true uploads produced 4 primaries, after
    which every later primary upload raised MultipleResultsFound -- a permanent 500."""
    headers = await _product(client, approved_seller)

    responses = await asyncio.gather(
        *[
            client.post(
                "/products/1/images",
                headers=headers,
                json={
                    "image_url": f"https://cdn.example.com/{index}.jpg",
                    "is_primary": True,
                    "sort_order": index,
                },
            )
            for index in range(4)
        ]
    )

    assert all(response.status_code in (201, 409) for response in responses), [
        response.status_code for response in responses
    ]
    assert any(response.status_code == 201 for response in responses)

    images = (await client.get("/products/1/images")).json()
    primaries = [image for image in images if image["is_primary"]]
    assert len(primaries) <= 1, f"invariant broken: {len(primaries)} primaries"

    # And the endpoint still works afterwards -- it is not wedged.
    followup = await client.post(
        "/products/1/images",
        headers=headers,
        json={"image_url": "https://cdn.example.com/final.jpg", "is_primary": True,
              "sort_order": 9},
    )
    assert followup.status_code == 201


async def test_database_rejects_a_second_primary_directly(client, approved_seller):
    """The partial unique index is the real guarantee, not the application check."""
    from sqlalchemy.exc import IntegrityError

    from app.database import AsyncSessionLocal
    from app.models import ProductImage

    await _product(client, approved_seller)

    async with AsyncSessionLocal() as db:
        db.add_all(
            [
                ProductImage(product_id=1, image_url="https://a", is_primary=True),
                ProductImage(product_id=1, image_url="https://b", is_primary=True),
            ]
        )

        try:
            await db.commit()
        except IntegrityError:
            pass
        else:
            raise AssertionError("database allowed two primary images")


async def test_non_primary_images_are_unconstrained(client, approved_seller):
    headers = await _product(client, approved_seller)

    responses = [
        await client.post(
            "/products/1/images",
            headers=headers,
            json={"image_url": f"https://cdn.example.com/{index}.jpg",
                  "sort_order": index},
        )
        for index in range(3)
    ]

    assert all(response.status_code == 201 for response in responses)


async def test_images_are_sorted(client, approved_seller):
    headers = await _product(client, approved_seller)

    for order in (2, 0, 1):
        await client.post(
            "/products/1/images",
            headers=headers,
            json={"image_url": f"https://cdn.example.com/{order}.jpg",
                  "sort_order": order},
        )

    images = (await client.get("/products/1/images")).json()
    assert [image["sort_order"] for image in images] == [0, 1, 2]


async def test_images_for_missing_product_is_404(client):
    assert (await client.get("/products/999/images")).status_code == 404


async def test_delete_image(client, approved_seller):
    headers = await _product(client, approved_seller)
    await client.post(
        "/products/1/images", headers=headers,
        json={"image_url": "https://cdn.example.com/a.jpg"},
    )

    response = await client.delete("/products/1/images/1", headers=headers)

    assert response.status_code == 204
    assert (await client.get("/products/1/images")).json() == []
