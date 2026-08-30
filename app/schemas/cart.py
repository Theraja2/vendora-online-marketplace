from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.product import ProductResponse


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    product: ProductResponse
    subtotal: Decimal


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    items: list[CartItemResponse]
    total: Decimal