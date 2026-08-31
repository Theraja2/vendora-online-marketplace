from decimal import Decimal
from uuid import uuid4

from app.schemas.payment import MockPaymentResult


async def process_mock_payment(
    amount: Decimal,
) -> MockPaymentResult:
    if amount <= Decimal("0"):
        return MockPaymentResult(
            success=False,
            reference="",
            amount=amount,
            message=(
                "Payment amount must be greater "
                "than zero."
            ),
        )

    payment_reference = (
        f"MOCK-{uuid4().hex[:12].upper()}"
    )

    return MockPaymentResult(
        success=True,
        reference=payment_reference,
        amount=amount,
        message="Mock payment successful.",
    )