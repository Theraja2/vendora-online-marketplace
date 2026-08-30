from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.enums import Role
from app.models.user import User
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.user import UserCreate, UserResponse
from app.security.jwt import (
    REFRESH_TOKEN_TYPE,
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.security.password import (
    hash_password,
    verify_password,
    waste_time_like_a_real_verify,
)

from app.schemas.auth import ForgotPasswordRequest

from app.security import (
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
)



router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_session),
) -> UserResponse:

    # phone_number is unique in the database too, so it has to be checked here --
    # otherwise a duplicate phone falls through to the IntegrityError handler and
    # reports "username or email already exists", which is simply wrong.
    existing_user = await db.scalar(
        select(User).where(
            or_(
                User.username == user_data.username,
                User.email == user_data.email,
                User.phone_number == user_data.phone_number,
            )
        )
    )

    if existing_user:
        if existing_user.username == user_data.username:
            detail = "Username already exists."
        elif existing_user.email == user_data.email:
            detail = "Email already exists."
        else:
            detail = "Phone number already exists."

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

    new_user = User(
        full_name=user_data.full_name,
        username=user_data.username,
        email=user_data.email,
        password=hash_password(user_data.password),
        phone_number=user_data.phone_number,
        role=Role.CUSTOMER.value,
        is_active=True,
    )

    db.add(new_user)

    try:
        await db.commit()
    except IntegrityError as exc:
        # Still possible if two registrations race between the check and the commit.
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username, email, or phone number already exists.",
        ) from exc

    await db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_session),
) -> TokenResponse:

    user = await db.scalar(
        select(User).where(
            User.username == form_data.username
        )
    )

    if user is None:
        # Spend the same Argon2 cost as a real verify so response time does not
        # reveal whether the username exists.
        waste_time_like_a_real_verify()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
async def refresh_access_token(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_session),
) -> TokenResponse:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    try:
        payload = decode_token(data.refresh_token)

        user_id = payload.get("sub")
        token_type = payload.get("type")

        if user_id is None:
            raise credentials_exception

        if token_type != REFRESH_TOKEN_TYPE:
            raise credentials_exception

        user_id = int(user_id)

    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise credentials_exception from exc

    user = await db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
    )


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(User).where(User.email == data.email)
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # STEP 1: Generate reset token
    if data.reset_token is None:
        reset_token = create_password_reset_token(user.id)

        return {
            "message": "Password reset token generated successfully",
            "reset_token": reset_token,
        }

    # STEP 2: Verify reset token
    try:
        token_user_id = decode_password_reset_token(data.reset_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    if token_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token",
        )

    if data.new_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password is required",
        )

    # Hash and update the password
    user.password = hash_password(data.new_password)

    await db.commit()

    return {
        "message": "Password reset successfully",
    }
