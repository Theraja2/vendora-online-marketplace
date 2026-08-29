from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import require_roles
from app.models.category import Category
from app.models.enums import Role
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
)
from app.schemas.common import Page

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)

@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    category_data: CategoryCreate,
    admin_user: User = Depends(require_roles(Role.ADMIN.value)),
    db: AsyncSession = Depends(get_session),
) -> Category:

    existing_category = await db.scalar(
        select(Category).where(Category.name == category_data.name)
    )

    if existing_category is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category already exists",
        )

    category = Category(
        name=category_data.name,
        description=category_data.description,
        is_active=True,
    )

    db.add(category)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category already exists",
        ) from exc

    await db.refresh(category)

    return category

@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_session),
) -> Category:

    category = await db.scalar(
        select(Category).where(Category.id == category_id)
    )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    return category


@router.get(
    "",
    response_model=Page[CategoryResponse],
)
async def list_categories(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_inactive: bool = Query(
        default=False,
        description="Include deactivated categories. Products cannot be listed "
                    "under these, so storefronts should leave this false.",
    ),
    db: AsyncSession = Depends(get_session),
) -> Page[CategoryResponse]:
    """Public category list -- the storefront needs this to build its navigation."""

    filters = [] if include_inactive else [Category.is_active.is_(True)]

    total = await db.scalar(
        select(func.count()).select_from(Category).where(*filters)
    )

    result = await db.execute(
        select(Category)
        .where(*filters)
        .order_by(Category.name.asc())
        .limit(limit)
        .offset(offset)
    )

    return Page[CategoryResponse](
        items=[CategoryResponse.model_validate(c) for c in result.scalars().all()],
        total=total or 0,
        limit=limit,
        offset=offset,
    )
