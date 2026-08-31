from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.dependencies.auth import get_current_user
from app.models.order import Order
from app.models.user import User
from app.schemas.order import (
    OrderDetailResponse,
    OrderResponse,
)


router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)


@router.get(
    "",
    response_model=list[OrderResponse]
)
async def get_my_orders(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    )

    orders = result.scalars().all()

    return orders


@router.get(
    "/{order_id}",
    response_model=OrderDetailResponse
)
async def get_order_details(
    order_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order)
        .options(
            selectinload(Order.order_items)
        )
        .where(
            Order.id == order_id,
            Order.user_id == current_user.id,
        )
    )

    order = result.scalar_one_or_none()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order


@router.patch(
    "/{order_id}/cancel",
    response_model=OrderDetailResponse
)
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Order)
        .options(
            selectinload(Order.order_items)
        )
        .where(
            Order.id == order_id,
            Order.user_id == current_user.id,
        )
    )

    order = result.scalar_one_or_none()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if order.status not in {"pending", "paid"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order cannot be cancelled at this stage",
        )

    order.status = "cancelled"

    await session.commit()

    await session.refresh(order)

    return order