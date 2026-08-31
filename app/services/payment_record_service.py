from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.core.payment_status import PAYMENT_SUCCESS


async def create_payment_record(
    session: AsyncSession,
    order_id: int,
    amount: Decimal,
    reference: str,
) -> Payment:
    payment = Payment(
        order_id=order_id,
        amount=amount,
        status=PAYMENT_SUCCESS,
        reference=reference,
    )

    session.add(payment)

    await session.flush()

    return payment