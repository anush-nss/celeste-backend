from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DECIMAL, Boolean, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.tier_benefit import Benefit
    from src.database.models.tier_price_list import TierPriceList


class Tier(Base):
    __tablename__ = "tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Simple requirements
    min_total_spent: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0.0)
    min_orders_count: Mapped[int] = mapped_column(Integer, default=0)
    min_monthly_spent: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0.0)
    min_monthly_orders: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()")
    )

    # Relationships
    benefits: Mapped[List["Benefit"]] = relationship(
        "Benefit", secondary="tier_benefits", back_populates="tiers"
    )
    price_lists: Mapped[List["TierPriceList"]] = relationship(
        "TierPriceList", back_populates="tier", cascade="all, delete-orphan"
    )
