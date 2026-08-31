from decimal import Decimal

from pydantic import BaseModel


class CheckoutResponse(BaseModel):
    message: str
    cart_id: int
    total_amount: Decimal
    item_count: int


class PaymentCheckoutResponse(BaseModel):
    success: bool
    payment_reference: str
    amount: Decimal
    message: str