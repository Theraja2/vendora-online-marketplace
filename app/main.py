from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  -- registers every model on Base.metadata
from app.bootstrap import ensure_first_admin
from app.config import settings
from app.database import engine
from app.routers.auth import router as auth_router
from app.routers.categories import router as categories_router
from app.routers.products import router as products_router
from app.routers.sellers import router as sellers_router
from app.routers.users import router as users_router
from app.routers.cart import router as cart_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic ("alembic upgrade head"), not create_all --
    # create_all only ever creates missing tables and silently ignores changes to
    # existing ones, which hides migrations that never actually ran.
    await ensure_first_admin()

    yield

    await engine.dispose()


app = FastAPI(
    title="VENDORA ONLINE MARKETPLACE API",
    version="1.1.0",
    lifespan=lifespan,
)


# Browsers block cross-origin requests unless the API says otherwise, so a
# frontend on any other host cannot call this API without these headers.
# CORS_ORIGINS holds the *frontend's* origins, not this API's URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(sellers_router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(cart_router)


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    return {
        "message": "Welcome to Vendora Online Marketplace API"
    }


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
