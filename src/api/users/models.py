from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from src.config.constants import DEFAULT_FALLBACK_TIER, UserRole


class AddressSchema(BaseModel):
    id: Optional[int] = None
    address: str
    latitude: float
    longitude: float
    is_default: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateAddressSchema(BaseModel):
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_default: Optional[bool] = None


class CartItemSchema(BaseModel):
    user_id: str
    product_id: str
    quantity: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserSchema(BaseModel):
    firebase_uid: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_delivery: Optional[bool] = None
    role: UserRole = UserRole.CUSTOMER
    tier_id: str = Field(
        default=DEFAULT_FALLBACK_TIER, description="Customer loyalty tier"
    )
    total_orders: int = Field(
        default=0, ge=0, description="Total number of orders placed"
    )
    lifetime_value: float = Field(
        default=0.0, ge=0, description="Total amount spent by customer"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_order_at: Optional[datetime] = None
    addresses: Optional[List[AddressSchema]] = None
    cart: Optional[List[CartItemSchema]] = None # Added cart

    model_config = ConfigDict(from_attributes=True)


class CreateUserSchema(BaseModel):
    name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: UserRole = Field(default=UserRole.CUSTOMER, description="Role of the user")
    tier_id: Optional[str] = None


class UpdateUserSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_delivery: Optional[bool] = None
    role: Optional[UserRole] = None
    tier_id: Optional[str] = Field(None, description="Customer loyalty tier")


class AddToCartSchema(BaseModel):
    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)


class UpdateCartItemSchema(BaseModel):
    quantity: int = Field(..., gt=0)