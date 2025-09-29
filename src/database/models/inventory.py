from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.product import Product
    from src.database.models.store import Store

class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint('quantity_available >= 0', name='check_quantity_available_non_negative'),
        CheckConstraint('quantity_reserved >= 0', name='check_quantity_reserved_non_negative'),
        CheckConstraint('quantity_on_hold >= 0', name='check_quantity_on_hold_non_negative'),

        # Primary lookup indexes
        Index('idx_inventory_product_store', 'product_id', 'store_id', unique=True),
        Index('idx_inventory_store_product', 'store_id', 'product_id'),

        # Available inventory filtering
        Index('idx_inventory_store_available', 'store_id', 'quantity_available',
              postgresql_where="quantity_available > 0"),
        Index('idx_inventory_product_available', 'product_id', 'quantity_available',
              postgresql_where="quantity_available > 0"),

        # Bulk inventory queries optimization
        Index('idx_inventory_composite_all', 'product_id', 'store_id', 'quantity_available', 'quantity_on_hold', 'quantity_reserved'),

        # Inventory tracking and updates
        Index('idx_inventory_updated', 'updated_at'),
        Index('idx_inventory_low_stock', 'product_id', 'quantity_available',
              postgresql_where="quantity_available < 10"),

        # Reserved and hold tracking
        Index('idx_inventory_reserved', 'store_id', 'quantity_reserved',
              postgresql_where="quantity_reserved > 0"),
        Index('idx_inventory_on_hold', 'store_id', 'quantity_on_hold',
              postgresql_where="quantity_on_hold > 0"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)

    quantity_available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_on_hold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text('NOW()'),
        onupdate=text('NOW()'),
        nullable=False
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="inventory_levels")
    store: Mapped["Store"] = relationship("Store")
