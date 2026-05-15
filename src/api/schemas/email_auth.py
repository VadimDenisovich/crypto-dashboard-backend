from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class EmailRequestIn(BaseModel):
    email: EmailStr
    captcha_token: str = Field(min_length=1, max_length=2048)


class EmailRequestOut(BaseModel):
    status: str = "sent"


class EmailVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
