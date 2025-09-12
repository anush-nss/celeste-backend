from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, Boolean, DECIMAL, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from src.database.base import Base
if TYPE_CHECKING:
    from src.database.models.tier import Tier

class TierBenefit(Base):
    __tablename__ = "tier_benefits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tier_id: Mapped[int] = mapped_column(Integer, ForeignKey("tiers.id", ondelete="CASCADE"), nullable=False)
    benefit_type: Mapped[str] = mapped_column(
        String(30), 
        nullable=False,
        # Add check constraint for valid benefit types
    )
    
    # Simple discount fields
    discount_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    discount_value: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 2), nullable=True)
    max_discount_amount: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 2), nullable=True)  # Cap for percentage discounts
    min_order_amount: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0.0)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))

    # Relationships
    tier: Mapped["Tier"] = relationship("Tier", back_populates="benefits")

    # Table constraints
    __table_args__ = (
        CheckConstraint("benefit_type IN ('delivery_discount', 'order_discount', 'free_shipping')", name='check_benefit_type'),
        CheckConstraint("discount_type IN ('percentage', 'flat') OR discount_type IS NULL", name='check_discount_type'),
    )