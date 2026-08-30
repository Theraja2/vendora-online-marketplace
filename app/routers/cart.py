from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import get_current_user
from app.schemas.cart import (
    CartItemCreate,
    CartItemResponse,
    CartResponse,
)
from app.services.cart_service import (
    add_product_to_cart,
    calculate_cart_total,
    view_user_cart,
)


router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
)


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_cart(
    cart_item_data: CartItemCreate,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    try:
        cart_item = await add_product_to_cart(
            session=session,
            user_id=current_user.id,
            product_id=cart_item_data.product_id,
            quantity=cart_item_data.quantity,
        )

        await session.commit()
        await session.refresh(cart_item)

        return cart_item

    except ValueError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=CartResponse,
    status_code=status.HTTP_200_OK,
)
async def view_cart(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    cart = await view_user_cart(
        session=session,
        user_id=current_user.id,
    )

    if cart is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found.",
        )

    total = calculate_cart_total(cart)

    items = []

    for item in cart.cart_items:
        subtotal = item.product.price * item.quantity

        items.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "product": item.product,
                "subtotal": subtotal,
            }
        )

    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "items": items,
        "total": total,
    }