from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewCreate(BaseModel):
    product_id: int = Field(
        gt=0
    )

    rating: int = Field(
        ge=1,
        le=5
    )

    comment: str | None = Field(
        default=None,
        max_length=1000
    )

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if value == "":
            return None

        return value


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    rating: int
    comment: str | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )