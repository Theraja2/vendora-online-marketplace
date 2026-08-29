from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class UserBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    phone_number: str = Field(min_length=5, max_length=20)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    full_name: str
    username: str
    email: EmailStr
    phone_number: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    username: str
    password: str


class UserRoleUpdate(BaseModel):
    """Change a user's role. Admin only."""

    role: Role
