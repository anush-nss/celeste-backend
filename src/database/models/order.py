from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    DECIMAL,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.constants import (
    DeliveryServiceLevel,
    FulfillmentMode,
    OdooSyncStatus,
    OrderStatus,
    Platform,
)
from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.product import Product
    from src.database.models.store import Store
    from src.database.models.user import User
    from src.database.models.payment import PaymentTransaction
    from src.database.models.rider import RiderProfile


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "total_amount >= 0", name="check_order_total_amount_non_negative"
        ),
        # Core order lookup indexes
        Index("idx_orders_user_id", "user_id"),
        Index("idx_orders_store_id", "store_id"),
        # Status and workflow indexes
        Index("idx_orders_status", "status"),
        Index("idx_orders_status_user", "status", "user_id"),
        Index("idx_orders_status_store", "status", "store_id"),
        # Date-based queries and reporting
        Index("idx_orders_created_at", "created_at"),
        Index("idx_orders_updated_at", "updated_at"),
        # Revenue and analytics indexes
        Index("idx_orders_total_amount", "total_amount"),
        Index("idx_orders_user_total", "user_id", "total_amount"),
        Index("idx_orders_store_total", "store_id", "total_amount"),
        # Time-based analytics
        Index("idx_orders_daily_revenue", "created_at", "total_amount", "status"),
        Index("idx_orders_monthly_stats", "created_at", "total_amount", "status"),
        # Customer order history
        Index("idx_orders_user_chronological", "user_id", "created_at"),
        Index("idx_orders_user_status_date", "user_id", "status", "created_at"),
        # Store operations
        Index("idx_orders_store_status_date", "store_id", "status", "created_at"),
        Index("idx_orders_store_pending", "store_id", "created_at"),
        # Performance optimization for order listing
        Index(
            "idx_orders_composite_listing",
            "user_id",
            "status",
            "created_at",
            "total_amount",
        ),
        Index(
            "idx_orders_store_composite",
            "store_id",
            "status",
            "created_at",
            "total_amount",
        ),
        # Recent orders optimization
        Index("idx_orders_recent", "created_at", "status"),
        # Odoo sync status tracking
        Index("idx_orders_odoo_sync_status", "odoo_sync_status"),
        Index("idx_orders_odoo_failed_syncs", "odoo_sync_status", "created_at"),
        Index("idx_orders_platform", "platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("users.firebase_uid"), nullable=False
    )
    store_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stores.id"), nullable=False
    )
    address_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("addresses.id"), nullable=True
    )
    payment_transaction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("payment_transactions.id"), nullable=True
    )
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    delivery_charge: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), nullable=False, server_default=text("'0.00'")
    )
    fulfillment_mode: Mapped[str] = mapped_column(
        Enum(
            FulfillmentMode,
            values_callable=lambda obj: [e.value for e in obj],
            name="fulfillmentmode",
        ),
        default=FulfillmentMode.PICKUP.value,
        nullable=False,
    )
    delivery_service_level: Mapped[str] = mapped_column(
        Enum(
            DeliveryServiceLevel,
            values_callable=lambda obj: [e.value for e in obj],
            name="deliveryservicelevel",
        ),
        server_default=DeliveryServiceLevel.STANDARD.value,
        nullable=False,
    )
    platform: Mapped[str | None] = mapped_column(
        Enum(
            Platform,
            values_callable=lambda obj: [e.value for e in obj],
            name="platform",
        ),
        nullable=True,
    )
    delivery_option: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(
        Enum(
            OrderStatus,
            values_callable=lambda obj: [e.value for e in obj],
            name="orderstatus",
        ),
        default=OrderStatus.PENDING.value,
        nullable=False,
    )

    # Odoo ERP sync fields
    odoo_sync_status: Mapped[str] = mapped_column(
        Enum(
            OdooSyncStatus,
            values_callable=lambda obj: [e.value for e in obj],
            name="odoosyncstatus",
        ),
        default=OdooSyncStatus.PENDING.value,
        nullable=False,
    )
    odoo_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    odoo_customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    odoo_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    odoo_synced_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    odoo_last_retry_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
        nullable=False,
    )

    # Relationships
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship("User", back_populates="orders")
    store: Mapped["Store"] = relationship("Store")
    payment_transaction: Mapped["PaymentTransaction"] = relationship(
        "PaymentTransaction"
    )
    rider: Mapped["RiderProfile"] = relationship(
        "RiderProfile", back_populates="assigned_orders"
    )

    rider_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("rider_profiles.id"), nullable=True
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_order_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="check_order_item_unit_price_positive"),
        CheckConstraint(
            "total_price >= 0", name="check_order_item_total_price_positive"
        ),
        # Core relationship indexes for optimal JOINs
        Index("idx_order_items_order_id", "order_id"),
        Index("idx_order_items_product_id", "product_id"),
        Index("idx_order_items_source_cart_id", "source_cart_id"),
        Index("idx_order_items_store_id", "store_id"),
        # Composite indexes for order analysis
        Index("idx_order_items_order_product", "order_id", "product_id"),
        Index("idx_order_items_product_order", "product_id", "order_id"),
        Index("idx_order_items_order_store", "order_id", "store_id"),
        # Pricing and quantity analysis
        Index("idx_order_items_unit_price", "unit_price"),
        Index("idx_order_items_total_price", "total_price"),
        Index("idx_order_items_quantity", "quantity"),
        # Product sales analytics
        Index("idx_order_items_product_sales", "product_id", "quantity", "total_price"),
        Index("idx_order_items_product_revenue", "product_id", "total_price"),
        # Cart traceability
        Index("idx_order_items_cart_order", "source_cart_id", "order_id"),
        # Order completion and fulfillment
        Index("idx_order_items_order_totals", "order_id", "total_price", "quantity"),
        # Administrative and audit indexes
        Index("idx_order_items_created_at", "created_at"),
        # Comprehensive order item analysis
        Index(
            "idx_order_items_full_analysis",
            "order_id",
            "product_id",
            "quantity",
            "unit_price",
            "total_price",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    source_cart_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carts.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False
    )
    store_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stores.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product")


# The back-population for User.orders is now defined in the User model in user.py
