from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SellerCreate(BaseModel):
    business_name: str = Field(
        min_length=2,
        max_length=150,
    )

    business_description: str | None = Field(
        default=None,
        max_length=1000,
    )


class SellerResponse(BaseModel):
    id: int
    user_id: int
    business_name: str
    business_description: str | None
    is_approved: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )