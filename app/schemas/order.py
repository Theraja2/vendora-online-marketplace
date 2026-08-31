from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrderResponse(BaseModel):
    id: int
    total_amount: Decimal
    status: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal

    model_config = ConfigDict(
        from_attributes=True
    )


class OrderDetailResponse(BaseModel):
    id: int
    total_amount: Decimal
    status: str
    created_at: datetime
    order_items: list[OrderItemResponse]

    model_config = ConfigDict(
        from_attributes=True
    )