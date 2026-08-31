from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.payment import Payment
from app.schemas.payment import MockPaymentResult
from app.services.cart_service import (
    calculate_cart_total,
    validate_cart,
)
from app.services.payment_service import (
    process_mock_payment,
)


async def prepare_checkout(
    session: AsyncSession,
    user_id: int,
) -> tuple[int, Decimal, int]:

    cart = await validate_cart(
        session=session,
        user_id=user_id,
    )

    total_amount = calculate_cart_total(cart)

    item_count = sum(
        item.quantity
        for item in cart.items
    )

    return (
        cart.id,
        total_amount,
        item_count,
    )


async def process_checkout_payment(
    session: AsyncSession,
    user_id: int,
) -> MockPaymentResult:

    cart = await validate_cart(
        session=session,
        user_id=user_id,
    )

    total_amount = calculate_cart_total(cart)

    order = Order(
        user_id=user_id,
        total_amount=total_amount,
        status="pending",
    )

    session.add(order)

    await session.flush()

    payment_result = await process_mock_payment(
        amount=total_amount,
    )

    if not payment_result.success:
        await session.rollback()

        raise ValueError(
            payment_result.message
        )

    payment = Payment(
        order_id=order.id,
        amount=payment_result.amount,
        status="successful",
        payment_method="mock",
        transaction_reference=payment_result.reference,
    )

    session.add(payment)

    order.status = "paid"

    await session.commit()

    return payment_result