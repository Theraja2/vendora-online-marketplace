"""The role lifecycle -- the deadlock that made the catalogue unreachable."""

from tests.conftest import auth_headers, make_admin, register


async def test_new_users_are_customers(client):
    response, _ = await register(client)
    assert response.json()["role"] == "customer"


async def test_customer_cannot_create_products_or_categories(client):
    await register(client)
    headers = await auth_headers(client)

    products = await client.post(
        "/products",
        headers=headers,
        json={"name": "Nope", "price": "1.00", "inventory": 1, "category_id": 1},
    )
    categories = await client.post(
        "/categories", headers=headers, json={"name": "Nope"}
    )

    assert products.status_code == 403
    assert categories.status_code == 403


async def test_approval_grants_the_seller_role(client):
    """Regression: approval used to flip is_approved but leave role='customer',
    so every seller endpoint returned 403 forever."""
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    seller_headers = await auth_headers(client, "ada")
    admin_headers = await auth_headers(client, "root")

    await client.post(
        "/sellers/register", headers=seller_headers,
        json={"business_name": "Ada Engines"},
    )

    before = await client.get("/users/me", headers=seller_headers)
    assert before.json()["role"] == "customer"

    approve = await client.patch("/sellers/1/approve", headers=admin_headers)
    assert approve.status_code == 200
    assert approve.json()["is_approved"] is True

    after = await client.get("/users/me", headers=seller_headers)
    assert after.json()["role"] == "seller"


async def test_full_path_from_signup_to_a_listed_product(client, approved_seller):
    """The end-to-end journey that was previously impossible through the API."""
    response = await client.post(
        "/products",
        headers=approved_seller["seller_headers"],
        json={
            "name": "Difference Engine",
            "price": "1999.99",
            "inventory": 5,
            "category_id": approved_seller["category_id"],
        },
    )

    assert response.status_code == 201

    listing = await client.get("/products")
    assert listing.json()["total"] == 1


async def test_unapproved_seller_cannot_create_products(client):
    await register(client, username="ada", email="ada@example.com",
                   phone_number="+254700000001")
    await register(client, username="root", email="root@example.com",
                   phone_number="+254700000099")
    await make_admin("root")

    seller_headers = await auth_headers(client, "ada")
    await client.post(
        "/sellers/register", headers=seller_headers,
        json={"business_name": "Ada Engines"},
    )

    # role is still customer, so require_roles rejects before the approval check
    response = await client.post(
        "/products", headers=seller_headers,
        json={"name": "Too Early", "price": "1.00", "inventory": 1, "category_id": 1},
    )
    assert response.status_code == 403


async def test_seller_registration_is_idempotent_per_user(client):
    await register(client)
    headers = await auth_headers(client)

    first = await client.post(
        "/sellers/register", headers=headers, json={"business_name": "Ada Engines"}
    )
    second = await client.post(
        "/sellers/register", headers=headers, json={"business_name": "Ada Engines 2"}
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_double_approval_is_rejected(client, approved_seller):
    response = await client.patch(
        "/sellers/1/approve", headers=approved_seller["admin_headers"]
    )
    assert response.status_code == 409


async def test_admin_can_list_pending_sellers(client, approved_seller):
    response = await client.get(
        "/sellers?pending_only=true", headers=approved_seller["admin_headers"]
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0  # the only seller is already approved


async def test_seller_can_read_own_profile(client, approved_seller):
    response = await client.get(
        "/sellers/me", headers=approved_seller["seller_headers"]
    )

    assert response.status_code == 200
    assert response.json()["is_approved"] is True


async def test_non_seller_gets_404_on_seller_profile(client):
    await register(client)
    headers = await auth_headers(client)

    assert (await client.get("/sellers/me", headers=headers)).status_code == 404
