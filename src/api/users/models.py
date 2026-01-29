from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.config.constants import CartStatus, CartUserRole, UserRole
from src.api.products.models import EnhancedProductSchema


class AddressResponseSchema(BaseModel):
    id: Optional[int] = Field(None, examples=[1])
    address: Annotated[
        str,
        Field(
            min_length=5,
            max_length=500,
            description="Complete address",
            examples=["123 Main St, Colombo 05"],
        ),
    ]
    latitude: Annotated[
        float, Field(ge=-90, le=90, description="Latitude", examples=[6.8775])
    ]
    longitude: Annotated[
        float, Field(ge=-180, le=180, description="Longitude", examples=[79.8681])
    ]
    is_default: bool = Field(
        default=False, description="Whether this is the default address"
    )
    active: bool = Field(default=True, description="Whether this address is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AddressCreationSchema(BaseModel):
    address: Annotated[
        str,
        Field(
            min_length=5,
            max_length=500,
            description="Complete address",
            examples=["456 Galle Road, Colombo 03"],
        ),
    ]
    latitude: Annotated[
        float, Field(ge=-90, le=90, description="Latitude", examples=[6.9036])
    ]
    longitude: Annotated[
        float, Field(ge=-180, le=180, description="Longitude", examples=[79.8521])
    ]
    is_default: bool = Field(
        default=False, description="Whether this is the default address"
    )


class AddressWithDeliverySchema(AddressResponseSchema):
    """Address schema with delivery capability information"""

    ondemand_delivery_available: Optional[bool] = Field(
        None,
        description="Whether on-demand delivery is available from nearby stores",
        examples=[True],
    )
    nearby_stores_count: Optional[int] = Field(
        None,
        description="Number of nearby stores found within delivery radius",
        examples=[3],
    )


class CartItemSchema(BaseModel):
    user_id: Annotated[
        str,
        Field(min_length=1, description="User Firebase UID", examples=["abc123def456"]),
    ]
    product_id: Annotated[int, Field(gt=0, description="Product ID", examples=[1])]
    quantity: Annotated[
        int, Field(gt=0, le=1000, description="Quantity of items", examples=[2])
    ]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserSchema(BaseModel):
    firebase_uid: Annotated[
        str, Field(min_length=1, examples=["TZKU3C493fY2JH9Ftnsdpz5occN2"])
    ]
    name: Annotated[str, Field(min_length=1, examples=["John Doe"])]
    email: Optional[EmailStr] = Field(None, examples=["john.doe@example.com"])
    phone: Optional[str] = Field(None, examples=["+94771234567"])
    is_delivery: Optional[bool] = Field(None)
    role: UserRole = Field(..., examples=[UserRole.CUSTOMER.value])
    tier_id: Optional[int] = Field(
        default=None, description="Customer tier ID", examples=[2]
    )
    odoo_customer_id: Optional[int] = Field(
        default=None, description="Odoo Partner ID", examples=[1234]
    )
    total_orders: int = Field(
        default=0, ge=0, description="Total number of orders placed", examples=[15]
    )
    lifetime_value: float = Field(
        default=0.0,
        ge=0,
        description="Total amount spent by customer",
        examples=[75000.0],
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_order_at: Optional[datetime] = None
    addresses: Optional[List[AddressResponseSchema]] = None
    favorites: Optional[List[EnhancedProductSchema]] = None
    cart: Optional[List[CartItemSchema]] = None

    model_config = ConfigDict(from_attributes=True)


class CreateUserSchema(BaseModel):
    name: Annotated[
        str,
        Field(
            min_length=2,
            max_length=100,
            description="Full name of the user",
            examples=["Jane Doe"],
        ),
    ]
    email: Optional[EmailStr] = Field(
        default=None, description="Email address", examples=["jane.doe@example.com"]
    )
    phone: Optional[str] = Field(None, examples=["+94712345678"])
    role: UserRole = Field(default=UserRole.CUSTOMER, description="Role of the user")
    tier_id: Optional[int] = Field(
        default=None, ge=1, description="Customer tier ID", examples=[1]
    )


class UpdateUserSchema(BaseModel):
    name: Optional[
        Annotated[
            str,
            Field(
                min_length=2,
                max_length=100,
                description="Full name of the user",
                examples=["Jane Smith"],
            ),
        ]
    ] = None
    is_delivery: Optional[bool] = Field(
        default=None, description="Whether user is a delivery person"
    )


class AddToCartSchema(BaseModel):
    product_id: Annotated[
        int, Field(gt=0, description="Product ID to add to cart", examples=[1])
    ]
    quantity: Annotated[
        int, Field(gt=0, le=1000, description="Quantity to add", examples=[3])
    ]


class UpdateCartItemSchema(BaseModel):
    quantity: Annotated[
        int,
        Field(
            gt=0, le=1000, description="New quantity for the cart item", examples=[5]
        ),
    ]


# Multi-Cart System Schemas


class CreateCartSchema(BaseModel):
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            description="Cart name",
            examples=["Groceries"],
        ),
    ] = "Cart"
    description: Optional[
        Annotated[
            str,
            Field(
                max_length=1000,
                description="Cart description",
                examples=["Weekly grocery shopping"],
            ),
        ]
    ] = None


class UpdateCartSchema(BaseModel):
    name: Optional[
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=255,
                description="Cart name",
                examples=["Updated Cart Name"],
            ),
        ]
    ] = None
    description: Optional[
        Annotated[
            str,
            Field(
                max_length=1000,
                description="Cart description",
                examples=["Updated description"],
            ),
        ]
    ] = None


class CartItemDetailSchema(BaseModel):
    id: int
    product_id: int
    quantity: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CartUserSchema(BaseModel):
    user_id: str
    role: CartUserRole
    shared_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CartSchema(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: CartStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    ordered_at: Optional[datetime] = None
    items: Optional[List[CartItemDetailSchema]] = None
    users: Optional[List[CartUserSchema]] = None
    role: Optional[CartUserRole] = None  # Current user's role
    items_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class CartListSchema(BaseModel):
    owned_carts: List[CartSchema]
    shared_carts: List[CartSchema]


class AddCartItemSchema(BaseModel):
    product_id: Annotated[
        int, Field(gt=0, description="Product ID to add to cart", examples=[101])
    ]
    quantity: Annotated[
        int, Field(gt=0, le=1000, description="Quantity to add", examples=[2])
    ]


class UpdateCartItemQuantitySchema(BaseModel):
    quantity: Annotated[
        int,
        Field(
            gt=0, le=1000, description="New quantity for the cart item", examples=[5]
        ),
    ]


class AddFavoriteSchema(BaseModel):
    product_id: Annotated[
        int, Field(gt=0, description="Product ID to add to favorites", examples=[1])
    ]


class ShareCartSchema(BaseModel):
    user_id: Annotated[
        str,
        Field(
            min_length=1,
            description="User ID to share cart with",
            examples=["friend123"],
        ),
    ]


class CartShareSchema(BaseModel):
    cart_id: int
    user_id: str
    role: CartUserRole
    shared_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CartSharingDetailsSchema(BaseModel):
    cart_id: int
    shared_with: List[CartShareSchema]


class CheckoutLocationSchema(BaseModel):
    mode: Annotated[
        str,
        Field(
            description="Checkout mode: 'delivery' or 'pickup'",
            examples=["delivery", "pickup"],
        ),
    ]
    store_id: Optional[
        Annotated[
            int,
            Field(
                gt=0,
                description="Store ID for pickup mode",
                examples=[1],
            ),
        ]
    ] = None
    address_id: Optional[
        Annotated[
            int,
            Field(
                gt=0,
                description="Address ID for delivery mode",
                examples=[123],
            ),
        ]
    ] = None


class MultiCartCheckoutSchema(BaseModel):
    cart_ids: Annotated[
        List[int],
        Field(
            min_length=1,
            description="List of cart IDs to checkout",
            examples=[[1, 2, 3]],
        ),
    ]
    location: CheckoutLocationSchema


class InventoryStatusSchema(BaseModel):
    """Inventory availability status for a cart item"""

    can_fulfill: bool  # Can fulfill full requested quantity
    quantity_requested: int
    quantity_available: int  # How many can be bought
    store_id: Optional[int] = None  # Closest store with stock
    store_name: Optional[str] = None


class CartItemPricingSchema(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    base_price: float
    final_price: float
    total_price: float
    savings_per_item: float
    total_savings: float
    discount_percentage: float
    applied_discounts: List[dict] = Field(default_factory=list)
    inventory_status: Optional[InventoryStatusSchema] = None


class CartGroupSchema(BaseModel):
    cart_id: int
    cart_name: str
    items: List[CartItemPricingSchema]
    cart_subtotal: float
    cart_total_savings: float
    cart_total: float

    model_config = ConfigDict(from_attributes=True)


class InventoryValidationSummary(BaseModel):
    """Summary of inventory validation results"""

    can_fulfill_all: bool  # All items have sufficient stock
    items_checked: int
    items_available: int
    items_out_of_stock: int


class OrderPreviewSchema(BaseModel):
    cart_groups: List[CartGroupSchema]
    subtotal: float
    total_savings: float
    delivery_charge: Optional[float] = None
    total_amount: float
    pricing_summary: dict = Field(default_factory=dict)
    inventory_validation: Optional[InventoryValidationSummary] = (
        None  # Inventory check results
    )
    estimated_delivery: Optional[datetime] = None
    is_nearby_store: bool = Field(
        True,
        description="True if order fulfilled from nearby stores, False if from distant default stores",
    )


class CheckoutResponseSchema(BaseModel):
    order_id: int
    total_amount: float
    status: str
    cart_groups: List[CartGroupSchema]
    created_at: datetime
    payment_url: Optional[str] = None
    payment_reference: Optional[str] = None
    payment_expires_at: Optional[datetime] = None
    is_nearby_store: bool = Field(
        True,
        description="True if order fulfilled from nearby stores, False if from distant default stores",
    )

    model_config = ConfigDict(from_attributes=True)
