"""Category listing -- the endpoint the storefront could not previously call."""

from tests.conftest import auth_headers, register, seed_category


async def test_list_categories_is_public(client):
    """Regression: GET /categories did not exist and returned 405."""
    await seed_category("Electronics")

    response = await client.get("/categories")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Electronics"


async def test_list_categories_hides_inactive_by_default(client):
    await seed_category("Electronics", is_active=True)
    await seed_category("Retired", is_active=False)

    default = await client.get("/categories")
    everything = await client.get("/categories?include_inactive=true")

    assert default.json()["total"] == 1
    assert everything.json()["total"] == 2


async def test_list_categories_paginates(client):
    for name in ("Alpha", "Beta", "Gamma"):
        await seed_category(name)

    response = await client.get("/categories?limit=2&offset=1")
    body = response.json()

    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["items"][0]["name"] == "Beta"  # sorted by name


async def test_get_single_category(client):
    category_id = await seed_category("Electronics")

    response = await client.get(f"/categories/{category_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Electronics"


async def test_get_missing_category_is_404(client):
    assert (await client.get("/categories/999")).status_code == 404


async def test_only_admins_create_categories(client):
    await register(client)
    headers = await auth_headers(client)

    response = await client.post("/categories", headers=headers, json={"name": "Nope"})

    assert response.status_code == 403


async def test_duplicate_category_is_rejected(client, approved_seller):
    response = await client.post(
        "/categories",
        headers=approved_seller["admin_headers"],
        json={"name": "Electronics"},
    )

    assert response.status_code == 409
