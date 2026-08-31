from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError

from app.config import settings


ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
PASSWORD_RESET_TOKEN_TYPE = "password_reset"


__all__ = [
    "ACCESS_TOKEN_TYPE",
    "REFRESH_TOKEN_TYPE",
    "PASSWORD_RESET_TOKEN_TYPE",
    "InvalidTokenError",
    "create_access_token",
    "create_refresh_token",
    "create_password_reset_token",
    "decode_token",
    "decode_password_reset_token",
]


def _create_token(
    user_id: int,
    token_type: str,
    expires_in: timedelta,
) -> str:
    now = datetime.now(UTC)

    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_in,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_access_token(user_id: int) -> str:
    return _create_token(
        user_id,
        ACCESS_TOKEN_TYPE,
        timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        user_id,
        REFRESH_TOKEN_TYPE,
        timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        ),
    )


def create_password_reset_token(user_id: int) -> str:
    return _create_token(
        user_id,
        PASSWORD_RESET_TOKEN_TYPE,
        timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        ),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )


def decode_password_reset_token(token: str) -> int:
    """
    Decode and verify a password-reset token.

    Returns:
        The user ID stored in the token.

    Raises:
        ValueError: If the token is invalid, expired,
        or is not a password-reset token.
    """

    try:
        payload = decode_token(token)

        if payload.get("type") != PASSWORD_RESET_TOKEN_TYPE:
            raise ValueError("Invalid token type")

        user_id = payload.get("sub")

        if user_id is None:
            raise ValueError("Missing user ID")

        return int(user_id)

    except (InvalidTokenError, ValueError, TypeError):
        raise ValueError("Invalid or expired password reset token")