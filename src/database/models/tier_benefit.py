from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DECIMAL,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.tier import Tier

# Association table for many-to-many relationship between tiers and benefits
tier_benefits = Table(
    "tier_benefits",
    Base.metadata,
    Column(
        "tier_id", Integer, ForeignKey("tiers.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "benefit_id",
        Integer,
        ForeignKey("benefits.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", TIMESTAMP(timezone=True), server_default=text("NOW()")),
)


class Benefit(Base):
    __tablename__ = "benefits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    benefit_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # order_discount or delivery_discount
    discount_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # flat or percentage

    # Discount configuration
    discount_value: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    max_discount_amount: Mapped[Optional[float]] = mapped_column(
        DECIMAL(10, 2), nullable=True
    )  # Cap for percentage discounts

    # Minimum requirements
    min_order_value: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0.0)
    min_items: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )

    # Many-to-many relationship with tiers
    tiers: Mapped[List["Tier"]] = relationship(
        "Tier", secondary=tier_benefits, back_populates="benefits"
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "benefit_type IN ('order_discount', 'delivery_discount')",
            name="check_benefit_type",
        ),
        CheckConstraint(
            "discount_type IN ('flat', 'percentage')", name="check_discount_type"
        ),
    )
