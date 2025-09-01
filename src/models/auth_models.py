from pydantic import BaseModel, Field

class LoginSchema(BaseModel):
    token: str = Field(..., min_length=1)

class RegisterSchema(BaseModel):
    phoneNumber: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)

class UserRegistration(BaseModel):
    idToken: str
    name: str
