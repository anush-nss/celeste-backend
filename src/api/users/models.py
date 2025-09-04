from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr
from src.config.constants import UserRole, DEFAULT_FALLBACK_TIER


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
    customer_tier: str = Field(
        default=DEFAULT_FALLBACK_TIER, description="Customer loyalty tier"
    )
    total_orders: int = Field(
        default=0, ge=0, description="Total number of orders placed"
    )
    lifetime_value: float = Field(
        default=0.0, ge=0, description="Total amount spent by customer"
    )
    createdAt: Optional[datetime] = None
    last_order_at: Optional[datetime] = None
    wishlist: Optional[List[str]] = None
    cart: Optional[List[CartItemSchema]] = None


class CreateUserSchema(BaseModel):
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role: UserRole = Field(default=UserRole.CUSTOMER, description="Role of the user")
    customer_tier: str = Field(
        default=DEFAULT_FALLBACK_TIER, description="Customer loyalty tier"
    )


class UpdateUserSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    role: Optional[UserRole] = None
    customer_tier: Optional[str] = Field(None, description="Customer loyalty tier")


class AddToWishlistSchema(BaseModel):
    productId: str = Field(..., min_length=1)


class AddToCartSchema(BaseModel):
    productId: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)


class UpdateCartItemSchema(BaseModel):
    quantity: int = Field(..., gt=0)
