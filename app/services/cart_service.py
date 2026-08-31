from decimal import Decimal

from sqlalchemy import delete, select
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
            selectinload(Cart.items)
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

    if quantity <= 0:
        raise ValueError(
            "Quantity must be greater than zero."
        )

    if quantity > product.stock_quantity:
        raise ValueError(
            "Requested quantity exceeds available stock."
        )

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
        new_quantity = cart_item.quantity + quantity

        if new_quantity > product.stock_quantity:
            raise ValueError(
                "Requested quantity exceeds available stock."
            )

        cart_item.quantity = new_quantity

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

    for item in cart.items:
        total += item.product.price * item.quantity

    return total


async def update_cart_item(
    session: AsyncSession,
    user_id: int,
    cart_item_id: int,
    quantity: int,
) -> CartItem:
    result = await session.execute(
        select(CartItem)
        .join(
            Cart,
            CartItem.cart_id == Cart.id,
        )
        .where(
            CartItem.id == cart_item_id,
            Cart.user_id == user_id,
        )
        .options(
            selectinload(CartItem.product)
        )
    )

    cart_item = result.scalar_one_or_none()

    if cart_item is None:
        raise ValueError(
            "Cart item not found."
        )

    if not cart_item.product.is_available:
        raise ValueError(
            "Product is no longer available."
        )

    if quantity <= 0:
        raise ValueError(
            "Quantity must be greater than zero."
        )

    if quantity > cart_item.product.stock_quantity:
        raise ValueError(
            "Requested quantity exceeds available stock."
        )

    cart_item.quantity = quantity

    await session.flush()

    return cart_item


async def remove_cart_item(
    session: AsyncSession,
    user_id: int,
    cart_item_id: int,
) -> None:
    result = await session.execute(
        select(CartItem.id)
        .join(
            Cart,
            CartItem.cart_id == Cart.id,
        )
        .where(
            CartItem.id == cart_item_id,
            Cart.user_id == user_id,
        )
    )

    item_id = result.scalar_one_or_none()

    if item_id is None:
        raise ValueError(
            "Cart item not found."
        )

    await session.execute(
        delete(CartItem)
        .where(CartItem.id == item_id)
    )

    await session.flush()


async def validate_cart(
    session: AsyncSession,
    user_id: int,
) -> Cart:
    cart = await get_user_cart(
        session=session,
        user_id=user_id,
    )

    if cart is None:
        raise ValueError(
            "Cart not found."
        )

    if not cart.items:
        raise ValueError(
            "Cart is empty."
        )

    for item in cart.items:
        product = item.product

        if product is None:
            raise ValueError(
                "A product in the cart no longer exists."
            )

        if not product.is_available:
            raise ValueError(
                f"Product '{product.name}' is no longer available."
            )

        if item.quantity <= 0:
            raise ValueError(
                f"Invalid quantity for product '{product.name}'."
            )

        if item.quantity > product.stock_quantity:
            raise ValueError(
                f"Requested quantity for '{product.name}' "
                "exceeds available stock."
            )

    return cart