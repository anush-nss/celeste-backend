from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'ordered')", name="check_cart_status"
        ),
        # Core cart lookup indexes
        Index("idx_carts_created_by", "created_by"),
        Index("idx_carts_status", "status"),
        # User cart management
        Index("idx_carts_user_status", "created_by", "status"),
        Index(
            "idx_carts_user_active",
            "created_by",
            "status",
            postgresql_where="status = 'active'",
        ),
        # Cart lifecycle tracking
        Index("idx_carts_created_at", "created_at"),
        Index("idx_carts_updated_at", "updated_at"),
        Index(
            "idx_carts_ordered_at",
            "ordered_at",
            postgresql_where="ordered_at IS NOT NULL",
        ),
        # Status-based filtering
        Index(
            "idx_carts_active",
            "status",
            "created_by",
            postgresql_where="status = 'active'",
        ),
        Index(
            "idx_carts_ordered",
            "status",
            "ordered_at",
            postgresql_where="status = 'ordered'",
        ),
        # Cart analytics and cleanup
        Index(
            "idx_carts_stale",
            "updated_at",
            "status",
            postgresql_where="status = 'active'",
        ),
        # Search and management
        Index(
            "idx_carts_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        # Composite indexes for cart management
        Index("idx_carts_user_lifecycle", "created_by", "status", "created_at"),
        Index(
            "idx_carts_conversion_tracking", "created_by", "created_at", "ordered_at"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Cart")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.firebase_uid", ondelete="CASCADE"),
        nullable=False,
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
    ordered_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    items: Mapped[List["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )
    users: Mapped[List["CartUser"]] = relationship(
        "CartUser", back_populates="cart", cascade="all, delete-orphan"
    )


class CartUser(Base):
    __tablename__ = "cart_users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'viewer')", name="check_cart_user_role"),
        # Core relationship indexes for optimal JOINs
        Index("idx_cart_users_cart_id", "cart_id"),
        Index("idx_cart_users_user_id", "user_id"),
        # Role-based access control
        Index("idx_cart_users_role", "role"),
        Index("idx_cart_users_user_role", "user_id", "role"),
        # Cart sharing and permissions
        Index("idx_cart_users_cart_role", "cart_id", "role"),
        Index(
            "idx_cart_users_owners",
            "cart_id",
            "user_id",
            postgresql_where="role = 'owner'",
        ),
        Index(
            "idx_cart_users_viewers",
            "cart_id",
            "user_id",
            postgresql_where="role = 'viewer'",
        ),
        # Sharing analytics
        Index("idx_cart_users_shared_at", "shared_at"),
        Index("idx_cart_users_user_sharing_history", "user_id", "shared_at"),
        # Composite indexes for permission checks
        Index("idx_cart_users_access_control", "cart_id", "user_id", "role"),
        Index("idx_cart_users_user_carts", "user_id", "cart_id", "role"),
    )

    cart_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.firebase_uid", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")
    shared_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False
    )

    # Relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="users")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="unique_cart_product"),
        CheckConstraint("quantity > 0", name="check_cart_item_quantity_positive"),
        CheckConstraint("quantity <= 1000", name="check_cart_item_quantity_reasonable"),
        # Core relationship indexes for optimal JOINs
        Index("idx_cart_items_cart_id", "cart_id"),
        Index("idx_cart_items_product_id", "product_id"),
        # Composite indexes for cart operations
        Index("idx_cart_items_cart_product", "cart_id", "product_id"),
        Index("idx_cart_items_product_cart", "product_id", "cart_id"),
        # Quantity-based analysis
        Index("idx_cart_items_quantity", "quantity"),
        Index("idx_cart_items_cart_quantity", "cart_id", "quantity"),
        # Product popularity analysis
        Index("idx_cart_items_product_quantity", "product_id", "quantity"),
        Index("idx_cart_items_product_frequency", "product_id", "created_at"),
        # Cart item lifecycle
        Index("idx_cart_items_created_at", "created_at"),
        Index("idx_cart_items_updated_at", "updated_at"),
        Index("idx_cart_items_cart_timeline", "cart_id", "created_at"),
        # Cart completion and analytics
        Index("idx_cart_items_cart_summary", "cart_id", "quantity", "created_at"),
        Index(
            "idx_cart_items_product_analytics", "product_id", "quantity", "created_at"
        ),
        # Recent activity tracking
        Index("idx_cart_items_recent", "updated_at", "cart_id"),
        # Comprehensive cart item analysis
        Index(
            "idx_cart_items_full_analysis",
            "cart_id",
            "product_id",
            "quantity",
            "created_at",
            "updated_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
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
    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
