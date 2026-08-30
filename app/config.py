import json
from typing import Annotated

from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    SECRET_KEY: str

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # Echoes every SQL statement to stdout. Never enable outside local debugging:
    # the log stream would include user data.
    DEBUG: bool = False

    # Origins allowed to call this API from a browser. Comma-separated in .env.
    # These are the *frontend's* origins, not this API's URL.
    # NoDecode stops pydantic-settings from JSON-parsing this before the validator
    # runs, which is what lets a plain comma-separated string work in .env.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # The first admin account, created on startup if it does not already exist.
    # Every registration through the API is a customer and only an admin can
    # promote anyone, so without this there would be no way to get the first one.
    # Leave FIRST_ADMIN_USERNAME empty to skip seeding entirely.
    FIRST_ADMIN_USERNAME: str | None = None
    FIRST_ADMIN_PASSWORD: str | None = None
    FIRST_ADMIN_EMAIL: EmailStr = "admin@example.com"
    FIRST_ADMIN_FULL_NAME: str = "Site Admin"
    FIRST_ADMIN_PHONE: str = "+254700000000"

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_weak_secret(cls, value: str) -> str:
        # HS256 signs with the raw key, so anything shorter than the 256-bit hash
        # output weakens the signature. PyJWT warns about this at runtime; failing
        # at startup is clearer than a warning nobody reads.
        if len(value) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. Generate one with:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        """Accept either a JSON array or a plain comma-separated list in .env."""
        if not isinstance(value, str):
            return value

        candidate = value.strip()

        if candidate.startswith("["):
            return json.loads(candidate)

        return [origin.strip() for origin in candidate.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
