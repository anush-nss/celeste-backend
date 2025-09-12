from typing import Optional, List
from sqlalchemy import String, Integer, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from src.database.base import Base
from src.database.models.address import Address
from src.database.models.tier import Tier

class User(Base):
    __tablename__ = "users"

    firebase_uid: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    tier_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tiers.id"), nullable=True, default=1)  # Default to Bronze tier (id=1)
    
    # Customer statistics for tier evaluation
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_value: Mapped[float] = mapped_column(Float, default=0.0)
    is_delivery: Mapped[Optional[bool]] = mapped_column(String, nullable=True)
    last_order_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'))

    # Relationships
    addresses: Mapped[List["Address"]] = relationship("Address", back_populates="user")
    tier: Mapped[Optional["Tier"]] = relationship("Tier", foreign_keys=[tier_id])
