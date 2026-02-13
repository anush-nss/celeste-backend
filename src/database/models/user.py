from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.address import Address
    from src.database.models.favorite import Favorite
    from src.database.models.order import Order
    from src.database.models.tier import Tier


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("total_orders >= 0", name="check_total_orders_non_negative"),
        CheckConstraint(
            "lifetime_value >= 0", name="check_lifetime_value_non_negative"
        ),
        # Core authentication and lookup indexes
        Index("idx_users_firebase_uid", "firebase_uid"),
        Index(
            "idx_users_email_unique",
            "email",
            unique=True,
            postgresql_where="email IS NOT NULL",
        ),
        # Role-based filtering
        Index("idx_users_role", "role"),
        Index("idx_users_role_tier", "role", "tier_id"),
        # Customer tier and analytics indexes
        Index("idx_users_tier_id", "tier_id", postgresql_where="tier_id IS NOT NULL"),
        Index("idx_users_lifetime_value", "lifetime_value"),
        Index("idx_users_total_orders", "total_orders"),
        # Customer segmentation indexes
        Index(
            "idx_users_tier_lifetime_value",
            "tier_id",
            "lifetime_value",
            postgresql_where="tier_id IS NOT NULL",
        ),
        Index(
            "idx_users_tier_total_orders",
            "tier_id",
            "total_orders",
            postgresql_where="tier_id IS NOT NULL",
        ),
        # Delivery and logistics indexes
        Index(
            "idx_users_is_delivery",
            "is_delivery",
            postgresql_where="is_delivery IS NOT NULL",
        ),
        Index(
            "idx_users_delivery_active",
            "is_delivery",
            "role",
            postgresql_where="is_delivery = true",
        ),
        # Activity and engagement indexes
        Index(
            "idx_users_last_order_at",
            "last_order_at",
            postgresql_where="last_order_at IS NOT NULL",
        ),
        Index("idx_users_recent_customers", "last_order_at", "total_orders"),
        # Contact information indexes
        Index("idx_users_phone", "phone", postgresql_where="phone IS NOT NULL"),
        Index(
            "idx_users_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        # Administrative and audit indexes
        Index("idx_users_created_at", "created_at"),
        Index("idx_users_updated_at", "updated_at"),
        # Composite indexes for complex analytics
        Index(
            "idx_users_role_lifetime_orders", "role", "lifetime_value", "total_orders"
        ),
        Index(
            "idx_users_active_high_value",
            "tier_id",
            "lifetime_value",
            "last_order_at",
            postgresql_where="tier_id IS NOT NULL AND lifetime_value > 100",
        ),
    )

    firebase_uid: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    tier_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("tiers.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )

    # Customer statistics for tier evaluation
    total_orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lifetime_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_delivery: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=None
    )
    last_order_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    odoo_customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
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
    addresses: Mapped[List["Address"]] = relationship(
        "Address", back_populates="user", cascade="all, delete-orphan"
    )
    favorites: Mapped[Optional["Favorite"]] = relationship(
        "Favorite",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tier: Mapped[Optional["Tier"]] = relationship("Tier", foreign_keys=[tier_id])
    orders: Mapped[List["Order"]] = relationship(
        "Order", back_populates="user", cascade="all, delete-orphan"
    )
