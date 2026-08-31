from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MockPaymentResult(BaseModel):
    success: bool
    reference: str
    amount: Decimal
    message: str


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    amount: Decimal
    status: str
    payment_method: str
    transaction_reference: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )