from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_user, require_roles
from app.models.enums import Role
from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import UserResponse, UserRoleUpdate

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return current_user


@router.get(
    "",
    response_model=Page[UserResponse],
)
async def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    role: Role | None = Query(default=None, description="Filter by role."),
    admin_user: User = Depends(require_roles(Role.ADMIN.value)),
    db: AsyncSession = Depends(get_session),
) -> Page[UserResponse]:
    """Admin view of every account, so a user's id can be found before promoting."""

    filters = []

    if role is not None:
        filters.append(User.role == role.value)

    total = await db.scalar(
        select(func.count()).select_from(User).where(*filters)
    )

    result = await db.execute(
        select(User)
        .where(*filters)
        .order_by(User.id.asc())
        .limit(limit)
        .offset(offset)
    )

    return Page[UserResponse](
        items=list(result.scalars().all()),
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
)
async def change_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    admin_user: User = Depends(require_roles(Role.ADMIN.value)),
    db: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Promote or demote an account. Admin only.

    Note that granting the seller role here does not create a seller profile --
    the user still has to apply through POST /sellers/register. The normal route
    to becoming a seller is applying and being approved, which grants the role
    automatically.
    """

    if user_id == admin_user.id:
        # An admin demoting themselves would lock the last one out of every
        # admin-only endpoint, with no way back in through the API.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own role. Ask another admin.",
        )

    user = await db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.role = role_data.role.value

    await db.commit()

    await db.refresh(user)

    return user
