from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer

from app.models.enums import Availability


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)

    description: str | None = Field(default=None, max_length=5000)

    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    inventory: int = Field(ge=0)

    category_id: int = Field(gt=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)

    description: str | None = Field(default=None, max_length=5000)

    price: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )

    inventory: int | None = Field(default=None, ge=0)

    category_id: int | None = Field(default=None, gt=0)


class ProductResponse(BaseModel):
    id: int
    seller_id: int
    category_id: int
    name: str
    description: str | None
    price: Decimal
    inventory: int
    availability: Availability
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductImageCreate(BaseModel):
    image_url: HttpUrl

    is_primary: bool = False

    sort_order: int = Field(default=0, ge=0)

    @field_serializer("image_url")
    def _url_to_str(self, value: HttpUrl) -> str:
        return str(value)


class ProductImageResponse(BaseModel):
    id: int
    product_id: int
    image_url: str
    is_primary: bool
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
