from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product import Product


async def get_user_cart(
    session: AsyncSession,
    user_id: int,
) -> Cart | None:
    result = await session.execute(
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(
            selectinload(Cart.cart_items)
            .selectinload(CartItem.product)
        )
    )

    return result.scalar_one_or_none()


async def get_or_create_user_cart(
    session: AsyncSession,
    user_id: int,
) -> Cart:
    cart = await get_user_cart(
        session=session,
        user_id=user_id,
    )

    if cart is not None:
        return cart

    cart = Cart(
        user_id=user_id,
    )

    session.add(cart)

    await session.flush()

    return cart


async def get_cart_item(
    session: AsyncSession,
    cart_id: int,
    product_id: int,
) -> CartItem | None:
    result = await session.execute(
        select(CartItem)
        .where(
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        )
    )

    return result.scalar_one_or_none()


async def add_product_to_cart(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: int,
) -> CartItem:
    result = await session.execute(
        select(Product)
        .where(Product.id == product_id)
    )

    product = result.scalar_one_or_none()

    if product is None:
        raise ValueError("Product not found.")

    if not product.is_available:
        raise ValueError("Product is not available.")

    cart = await get_or_create_user_cart(
        session=session,
        user_id=user_id,
    )

    cart_item = await get_cart_item(
        session=session,
        cart_id=cart.id,
        product_id=product_id,
    )

    if cart_item is not None:
        cart_item.quantity += quantity

    else:
        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity,
        )

        session.add(cart_item)

    await session.flush()

    return cart_item


async def view_user_cart(
    session: AsyncSession,
    user_id: int,
) -> Cart | None:
    return await get_user_cart(
        session=session,
        user_id=user_id,
    )


def calculate_cart_total(cart: Cart) -> Decimal:
    total = Decimal("0")

    for item in cart.cart_items:
        total += item.product.price * item.quantity

    return total