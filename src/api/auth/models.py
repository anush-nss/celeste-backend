from typing import Annotated, Optional

from pydantic import BaseModel, Field

from src.config.constants import UserRole


class LoginSchema(BaseModel):
    token: Annotated[
        str,
        Field(
            min_length=10,
            max_length=5000,
            description="Firebase ID token",
            examples=["eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2NzAy..."],
        ),
    ]


class RegisterSchema(BaseModel):
    phoneNumber: Annotated[
        str,
        Field(
            min_length=10,
            max_length=20,
            description="Phone number with country code",
            pattern=r"^\+\d{10,19}$",
            examples=["+1234567890"],
        ),
    ]
    name: Annotated[
        str,
        Field(
            min_length=2,
            max_length=100,
            description="Full name of the user",
            examples=["John Doe"],
        ),
    ]


class UserRegistration(BaseModel):
    idToken: Annotated[
        str,
        Field(
            min_length=10,
            max_length=5000,
            description="Firebase ID token obtained from client authentication",
            examples=["eyJhbGciOiJSUzI1NiIsImtpZCI6IjE2NzAy..."],
        ),
    ]
    name: Annotated[
        str,
        Field(
            min_length=2,
            max_length=100,
            description="Full name of the user",
            examples=["John Doe"],
        ),
    ]


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
