from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import (
    get_current_user,
    require_roles,
)
from app.models.enums import Role
from app.models.seller import Seller
from app.models.user import User
from app.schemas.common import Page
from app.schemas.seller import (
    SellerCreate,
    SellerResponse,
)

router = APIRouter(
    prefix="/sellers",
    tags=["Sellers"],
)


@router.post(
    "/register",
    response_model=SellerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_seller(
    seller_data: SellerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> SellerResponse:

    existing_seller = await db.scalar(
        select(Seller).where(Seller.user_id == current_user.id)
    )

    if existing_seller is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already registered as a seller",
        )

    seller = Seller(
        user_id=current_user.id,
        business_name=seller_data.business_name,
        business_description=seller_data.business_description,
        is_approved=False,
    )

    db.add(seller)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already registered as a seller",
        ) from exc

    await db.refresh(seller)

    return seller


@router.get(
    "/me",
    response_model=SellerResponse,
)
async def get_my_seller_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> SellerResponse:

    seller = await db.scalar(
        select(Seller).where(Seller.user_id == current_user.id)
    )

    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not registered as a seller",
        )

    return seller


@router.get(
    "",
    response_model=Page[SellerResponse],
)
async def list_sellers(
    limit: int = 20,
    offset: int = 0,
    pending_only: bool = False,
    admin_user: User = Depends(require_roles(Role.ADMIN.value)),
    db: AsyncSession = Depends(get_session),
) -> Page[SellerResponse]:
    """Admin view of seller applications, so pending ones can actually be found."""

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    filters = []

    if pending_only:
        filters.append(Seller.is_approved.is_(False))

    total = await db.scalar(
        select(func.count()).select_from(Seller).where(*filters)
    )

    result = await db.execute(
        select(Seller)
        .where(*filters)
        .order_by(Seller.created_at.desc(), Seller.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return Page[SellerResponse](
        items=list(result.scalars().all()),
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{seller_id}/approve",
    response_model=SellerResponse,
)
async def approve_seller(
    seller_id: int,
    admin_user: User = Depends(require_roles(Role.ADMIN.value)),
    db: AsyncSession = Depends(get_session),
) -> SellerResponse:

    seller = await db.scalar(
        select(Seller).where(Seller.id == seller_id)
    )

    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller not found",
        )

    if seller.is_approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seller is already approved",
        )

    owner = await db.scalar(
        select(User).where(User.id == seller.user_id)
    )

    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller account owner not found",
        )

    seller.is_approved = True

    # Approval is what actually grants the seller role. Without this the account
    # keeps role="customer" forever and every seller-only endpoint returns 403,
    # which made the whole catalogue impossible to populate through the API.
    if owner.role == Role.CUSTOMER.value:
        owner.role = Role.SELLER.value

    await db.commit()

    await db.refresh(seller)

    return seller
