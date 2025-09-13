from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, Boolean, DECIMAL, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.category import Category
    from src.database.models.price_list import PriceList
    from src.database.models.product import Product

class PriceListLine(Base):
    __tablename__ = "price_list_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    price_list_id: Mapped[int] = mapped_column(Integer, ForeignKey("price_lists.id", ondelete="CASCADE"), nullable=False)
    
    # Pricing Target (product-specific has highest priority)
    product_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True)  # NULL = all products
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True)  # NULL = all products
    # If both product_id and category_id are NULL, applies to all products
    
    # Pricing Rules
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    max_discount_amount: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True)  # Cap for percentage discounts
    
    # Minimum quantity for bulk pricing
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)
    
    # Conditions
    min_order_amount: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True)  # NULL = no minimum order requirement
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'))

    # Relationships
    price_list: Mapped["PriceList"] = relationship("PriceList", back_populates="lines")
    product: Mapped[Optional["Product"]] = relationship("Product", foreign_keys=[product_id])
    category: Mapped[Optional["Category"]] = relationship("Category", foreign_keys=[category_id])

    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint("discount_type IN ('percentage', 'flat', 'fixed_price')", name='check_discount_type'),
        CheckConstraint('discount_value >= 0', name='check_discount_value_non_negative'),
        CheckConstraint('min_quantity >= 1', name='check_min_quantity_positive'),
        CheckConstraint('min_order_amount >= 0', name='check_min_order_amount_non_negative'),
        Index('idx_price_list_lines_list_active', 'price_list_id', 'is_active'),
        Index('idx_price_list_lines_product', 'product_id'),
        Index('idx_price_list_lines_category', 'category_id'),
        Index('idx_price_list_lines_quantity', 'min_quantity'),
        Index('idx_price_list_lines_covering', 'price_list_id', 'is_active', 'min_quantity', 'discount_type', 'discount_value'),
    )
