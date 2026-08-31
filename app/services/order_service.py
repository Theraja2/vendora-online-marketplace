from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import Cart
from app.models.order import Order
from app.models.order_item import OrderItem
from app.services.payment_service import create_payment_record


async def create_order_after_payment(
    session: AsyncSession,
    user_id: int,
    cart: Cart,
    total_amount: Decimal,
) -> Order:

    try:
        order = Order(
            user_id=user_id,
            total_amount=total_amount,
            status="paid",
        )

        session.add(order)

        await session.flush()

        for cart_item in cart.items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
                unit_price=cart_item.product.price,
            )

            session.add(order_item)

        payment_reference = str(uuid4())

        await create_payment_record(
            session=session,
            order_id=order.id,
            amount=total_amount,
            reference=payment_reference,
        )

        for cart_item in cart.items:
            await session.delete(cart_item)

        await session.commit()

        await session.refresh(order)

        return order

    except Exception:
        await session.rollback()
        raise