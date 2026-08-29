"""CORS, OpenAPI completeness, and the module-shadowing regression."""

import importlib


async def test_cors_preflight_succeeds(client):
    """Regression: OPTIONS returned 405 with no headers, blocking every browser."""
    response = await client.request(
        "OPTIONS",
        "/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]


async def test_cors_headers_on_a_normal_request(client):
    response = await client.get("/products", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_unknown_origin_is_not_allowed(client):
    response = await client.get("/products", headers={"Origin": "https://evil.example"})

    assert response.headers.get("access-control-allow-origin") != "https://evil.example"


async def test_token_helpers_are_not_shadowed():
    """Regression: routers/auth.py re-imported these from a second module at line
    152, silently overriding the top-of-file import so app/security/jwt.py never ran."""
    import app.routers.auth as auth_router

    assert auth_router.create_access_token.__module__ == "app.security.jwt"
    assert auth_router.create_refresh_token.__module__ == "app.security.jwt"
    assert auth_router.decode_token.__module__ == "app.security.jwt"


async def test_the_duplicated_modules_are_gone():
    for dead_module in ("app.utils.security", "app.security.dependencies"):
        try:
            importlib.import_module(dead_module)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{dead_module} still exists and can shadow the real one")


async def test_tokens_carry_issued_at():
    from app.security.jwt import create_access_token, decode_token

    payload = decode_token(create_access_token(1))

    assert payload["sub"] == "1"
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload


async def test_every_endpoint_declares_a_response_schema(client):
    """Regression: GET /users/me had no response_model, so it generated as unknown."""
    spec = (await client.get("/openapi.json")).json()

    undocumented = []
    for path, operations in spec["paths"].items():
        for verb, operation in operations.items():
            success = {
                code: body
                for code, body in operation.get("responses", {}).items()
                if code.startswith("2")
            }
            if not success:
                undocumented.append(f"{verb.upper()} {path}")
                continue

            has_schema = any(
                "schema" in content.get("application/json", {})
                for body in success.values()
                for content in [body.get("content", {})]
            )
            # 204 responses legitimately have no body.
            if not has_schema and "204" not in success:
                undocumented.append(f"{verb.upper()} {path}")

    assert undocumented == [], f"endpoints without a typed response: {undocumented}"


async def test_health_endpoint(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_openapi_documents_every_router(client):
    spec = (await client.get("/openapi.json")).json()
    paths = set(spec["paths"])

    for expected in (
        "/auth/register", "/auth/login", "/auth/refresh",
        "/users/me", "/sellers/register", "/sellers/me",
        "/categories", "/products", "/products/{product_id}",
    ):
        assert expected in paths, f"{expected} missing from the OpenAPI spec"


async def test_debug_defaults_to_off():
    """echo=True would stream user data into the log aggregator once deployed."""
    from app.config import Settings

    assert Settings.model_fields["DEBUG"].default is False
