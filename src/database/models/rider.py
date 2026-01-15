from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.database.models.associations import store_riders

if TYPE_CHECKING:
    from src.database.models.store import Store
    from src.database.models.order import Order


class RiderProfile(Base):
    __tablename__ = "rider_profiles"
    __table_args__ = (
        # Search indexes
        Index("idx_riders_phone", "phone", unique=True),
        Index("idx_riders_user_id", "user_id", unique=True, postgresql_where="user_id IS NOT NULL"),
        Index("idx_riders_active", "is_active"),
        Index(
            "idx_riders_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(128), ForeignKey("users.firebase_uid", ondelete="SET NULL"), nullable=True, unique=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False, default="motorcycle")
    vehicle_registration_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
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
    stores: Mapped[List["Store"]] = relationship(
        "Store", secondary=store_riders, back_populates="riders"
    )
    assigned_orders: Mapped[List["Order"]] = relationship("Order", back_populates="rider")
