from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, Float, Boolean, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.address import Address
    from src.database.models.tier import Tier
    from src.database.models.order import Order

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint('total_orders >= 0', name='check_total_orders_non_negative'),
        CheckConstraint('lifetime_value >= 0', name='check_lifetime_value_non_negative'),
        Index('idx_user_tier_id', 'tier_id'),
        Index('idx_user_role', 'role'),
        Index('idx_user_email', 'email'),
    )

    firebase_uid: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    tier_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tiers.id", ondelete="SET NULL"), nullable=True, default=None, index=True)

    # Customer statistics for tier evaluation
    total_orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lifetime_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_delivery: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
    last_order_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'), nullable=False)

    # Relationships
    addresses: Mapped[List["Address"]] = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    tier: Mapped[Optional["Tier"]] = relationship("Tier", foreign_keys=[tier_id])
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user", cascade="all, delete-orphan")
