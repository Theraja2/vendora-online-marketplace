from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user
from app.schemas.cart import (
    CartItemCreate,
    CartItemResponse,
    CartItemUpdate,
    CartResponse,
)
from app.services.cart_service import (
    add_product_to_cart,
    calculate_cart_total,
    remove_cart_item,
    update_cart_item,
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


@router.patch(
    "/items/{cart_item_id}",
    response_model=CartItemResponse,
    status_code=status.HTTP_200_OK,
)
async def update_cart_item_quantity(
    cart_item_id: int,
    cart_item_data: CartItemUpdate,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    try:
        cart_item = await update_cart_item(
            session=session,
            user_id=current_user.id,
            cart_item_id=cart_item_id,
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


@router.delete(
    "/items/{cart_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_cart_item(
    cart_item_id: int,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    try:
        await remove_cart_item(
            session=session,
            user_id=current_user.id,
            cart_item_id=cart_item_id,
        )

        await session.commit()

    except ValueError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )