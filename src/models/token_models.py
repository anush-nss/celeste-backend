from pydantic import BaseModel
from typing import Optional
from src.shared.constants import UserRole

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
