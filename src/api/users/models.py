from datetime import datetime
from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from src.config.constants import UserRole


class AddressSchema(BaseModel):
    id: Optional[int] = None
    address: Annotated[str, Field(
        min_length=5,
        max_length=500,
        description="Complete address",
        examples=["123 Main St, New York, NY 10001"]
    )]
    latitude: Annotated[float, Field(
        ge=-90,
        le=90,
        description="Latitude coordinate",
        examples=[40.7128]
    )]
    longitude: Annotated[float, Field(
        ge=-180,
        le=180,
        description="Longitude coordinate",
        examples=[-74.0060]
    )]
    is_default: bool = Field(default=False, description="Whether this is the default address")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateAddressSchema(BaseModel):
    address: Optional[Annotated[str, Field(
        min_length=5,
        max_length=500,
        description="Complete address",
        examples=["456 Oak Ave, Los Angeles, CA 90210"]
    )]] = None
    latitude: Optional[Annotated[float, Field(
        ge=-90,
        le=90,
        description="Latitude coordinate",
        examples=[34.0522]
    )]] = None
    longitude: Optional[Annotated[float, Field(
        ge=-180,
        le=180,
        description="Longitude coordinate",
        examples=[-118.2437]
    )]] = None
    is_default: Optional[bool] = Field(
        None,
        description="Whether this should be the default address"
    )


class CartItemSchema(BaseModel):
    user_id: Annotated[str, Field(
        min_length=1,
        description="User Firebase UID",
        examples=["abc123def456"]
    )]
    product_id: Annotated[str, Field(
        min_length=1,
        description="Product ID",
        examples=["1"]
    )]
    quantity: Annotated[int, Field(
        gt=0,
        le=1000,
        description="Quantity of items",
        examples=[2]
    )]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserSchema(BaseModel):
    firebase_uid: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_delivery: Optional[bool] = None
    role: UserRole = UserRole.CUSTOMER
    tier_id: Optional[int] = Field(
        default=None, description="Customer tier ID"
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
    name: Annotated[str, Field(
        min_length=2,
        max_length=100,
        description="Full name of the user",
        examples=["John Doe"]
    )]
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email address",
        examples=["john.doe@example.com"]
    )
    phone: Optional[Annotated[str, Field(
        min_length=10,
        max_length=20,
        description="Phone number with country code",
        pattern=r'^\+\d{10,19}$',
        examples=["+1234567890"]
    )]] = None
    role: UserRole = Field(
        default=UserRole.CUSTOMER,
        description="Role of the user"
    )
    tier_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Customer tier ID",
        examples=[1]
    )


class UpdateUserSchema(BaseModel):
    name: Optional[Annotated[str, Field(
        min_length=2,
        max_length=100,
        description="Full name of the user",
        examples=["Jane Smith"]
    )]] = None
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email address",
        examples=["jane.smith@example.com"]
    )
    phone: Optional[Annotated[str, Field(
        min_length=10,
        max_length=20,
        description="Phone number with country code",
        pattern=r'^\+\d{10,19}$',
        examples=["+1987654321"]
    )]] = None
    is_delivery: Optional[bool] = Field(
        default=None,
        description="Whether user is a delivery person"
    )
    role: Optional[UserRole] = Field(
        default=None,
        description="Role of the user"
    )
    tier_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Customer tier ID",
        examples=[2]
    )


class AddToCartSchema(BaseModel):
    product_id: Annotated[str, Field(
        min_length=1,
        description="Product ID to add to cart",
        examples=["1"]
    )]
    quantity: Annotated[int, Field(
        gt=0,
        le=1000,
        description="Quantity to add",
        examples=[3]
    )]


class UpdateCartItemSchema(BaseModel):
    quantity: Annotated[int, Field(
        gt=0,
        le=1000,
        description="New quantity for the cart item",
        examples=[5]
    )]