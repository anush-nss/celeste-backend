from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.price_list_line import PriceListLine
    from src.database.models.tier_price_list import TierPriceList

class PriceList(Base):
    __tablename__ = "price_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    
    # Validity
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))
    valid_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)  # NULL = no expiry
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'))

    # Relationships
    lines: Mapped[List["PriceListLine"]] = relationship("PriceListLine", back_populates="price_list", cascade="all, delete-orphan")
    tier_associations: Mapped[List["TierPriceList"]] = relationship("TierPriceList", back_populates="price_list", cascade="all, delete-orphan")
    
    # Table constraints and indexes
    __table_args__ = (
        Index('idx_price_lists_validity', 'is_active', 'valid_from', 'valid_until'),
    )
