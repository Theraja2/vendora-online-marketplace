from decimal import Decimal
from uuid import uuid4


async def process_mock_payment(
    amount: Decimal,
) -> dict:
    transaction_reference = (
        f"VENDORA-TXN-{uuid4().hex[:12].upper()}"
    )

    return {
        "amount": amount,
        "status": "successful",
        "payment_method": "mock",
        "transaction_reference": transaction_reference,
    }