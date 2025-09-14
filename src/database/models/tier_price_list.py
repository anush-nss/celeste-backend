from sqlalchemy import Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from src.database.base import Base
from src.database.models.price_list import PriceList
from src.database.models.tier import Tier

class TierPriceList(Base):
    __tablename__ = "tier_price_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tier_id: Mapped[int] = mapped_column(Integer, ForeignKey("tiers.id", ondelete="CASCADE"), nullable=False)
    price_list_id: Mapped[int] = mapped_column(Integer, ForeignKey("price_lists.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))

    # Relationships
    tier: Mapped["Tier"] = relationship("Tier", back_populates="price_lists")
    price_list: Mapped["PriceList"] = relationship("PriceList", back_populates="tier_associations")

    # Table constraints
    __table_args__ = (
        UniqueConstraint('tier_id', 'price_list_id', name='unique_tier_price_list'),
        Index('idx_tier_price_lists_tier_id', 'tier_id'),
    )