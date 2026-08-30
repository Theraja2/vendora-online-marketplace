from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings


def create_password_reset_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "type": "password_reset",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_password_reset_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        if payload.get("type") != "password_reset":
            raise ValueError("Invalid password reset token")

        user_id = payload.get("sub")

        if user_id is None:
            raise ValueError("Invalid password reset token")

        return int(user_id)

    except (JWTError, ValueError, TypeError):
        raise ValueError("Invalid or expired password reset token")