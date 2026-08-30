from pydantic import BaseModel, EmailStr, Field


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"



class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    reset_token: str | None = None
    new_password: str | None = Field(default=None, min_length=8)
