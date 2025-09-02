from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr
from src.shared.constants import UserRole

class CartItemSchema(BaseModel):
    productId: str
    quantity: int = Field(..., gt=0)

class UserSchema(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role: UserRole = UserRole.CUSTOMER
    createdAt: Optional[datetime] = None
    wishlist: Optional[List[str]] = None
    cart: Optional[List[CartItemSchema]] = None

class CreateUserSchema(BaseModel):
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role: UserRole = UserRole.CUSTOMER

class UpdateUserSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role: Optional[UserRole] = None

class AddToWishlistSchema(BaseModel):
    productId: str = Field(..., min_length=1)

class AddToCartSchema(BaseModel):
    productId: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)

class UpdateCartItemSchema(BaseModel):
    quantity: int = Field(..., gt=0)
