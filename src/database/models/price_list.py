from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    valid_from: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )  # NULL = no expiry
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()")
    )

    # Relationships
    lines: Mapped[List["PriceListLine"]] = relationship(
        "PriceListLine", back_populates="price_list", cascade="all, delete-orphan"
    )
    tier_associations: Mapped[List["TierPriceList"]] = relationship(
        "TierPriceList", back_populates="price_list", cascade="all, delete-orphan"
    )

    # Table constraints and indexes
    __table_args__ = (
        # Active price list queries
        Index(
            "idx_price_lists_active_priority",
            "is_active",
            "priority",
            postgresql_where="is_active = true",
        ),
        Index(
            "idx_price_lists_validity_active",
            "is_active",
            "valid_from",
            "valid_until",
            postgresql_where="is_active = true",
        ),
        # Date-based filtering for current validity
        Index(
            "idx_price_lists_current",
            "valid_from",
            "valid_until",
            "is_active",
            postgresql_where="is_active = true",
        ),
        # Priority-based sorting
        Index("idx_price_lists_priority", "priority"),
        # Search and admin queries
        Index(
            "idx_price_lists_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("idx_price_lists_created_at", "created_at"),
        Index("idx_price_lists_updated_at", "updated_at"),
        # Composite queries
        Index(
            "idx_price_lists_active_valid_priority",
            "is_active",
            "valid_from",
            "priority",
            postgresql_where="is_active = true",
        ),
        # JOIN optimization with tier_price_lists (covering index for pricing queries)
        Index(
            "idx_price_lists_id_active_validity",
            "id",
            "is_active",
            "valid_from",
            "valid_until",
            "priority",
            postgresql_where="is_active = true",
        ),
    )
