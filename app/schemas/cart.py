from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartItemResponse(BaseModel):
    id: int
    cart_id: int
    product_id: int
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class CartProductResponse(BaseModel):
    id: int
    name: str
    price: Decimal
    is_available: bool

    model_config = ConfigDict(from_attributes=True)


class CartItemDetailResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: CartProductResponse
    subtotal: Decimal


class CartResponse(BaseModel):
    id: int
    user_id: int
    items: list[CartItemDetailResponse]
    total: Decimal