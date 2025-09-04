from pydantic import BaseModel, Field
from typing import Optional
from src.config.constants import UserRole


class LoginSchema(BaseModel):
    token: str = Field(..., min_length=1)


class RegisterSchema(BaseModel):
    phoneNumber: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class UserRegistration(BaseModel):
    idToken: str
    name: str


class DecodedToken(BaseModel):
    iss: str
    aud: str
    auth_time: int
    user_id: str
    sub: str
    iat: int
    exp: int
    email: Optional[str] = None
    email_verified: Optional[bool] = None
    phone_number: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    firebase: dict
    uid: str
    role: Optional[UserRole] = None
