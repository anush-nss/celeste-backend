from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import ARRAY, String, DECIMAL, Text, Integer, Boolean, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database.base import Base
from src.database.models.associations import product_categories

if TYPE_CHECKING:
    from src.database.models.category import Category
    from src.database.models.inventory import Inventory


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint('base_price >= 0', name='check_base_price_non_negative'),
        Index('idx_product_name', 'name'),
        Index('idx_product_brand', 'brand'),
        Index('idx_product_price', 'base_price'),
        Index('idx_product_ref', 'ref'),
        Index('idx_products_brand_price', 'brand', 'base_price'),
        Index('idx_products_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    base_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False, index=True)
    unit_measure: Mapped[str] = mapped_column(String(20), nullable=False)
    image_urls: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'), nullable=False)
    
    # Relationships
    categories: Mapped[List["Category"]] = relationship(
        "Category", 
        secondary=product_categories, 
        back_populates="products"
    )
    product_tags: Mapped[List["ProductTag"]] = relationship(
        "ProductTag", 
        back_populates="product"
    )
    inventory_levels: Mapped[List["Inventory"]] = relationship(
        "Inventory",
        back_populates="product",
        cascade="all, delete-orphan"
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        Index('idx_tag_type_active', 'tag_type', 'is_active'),
        Index('idx_tag_slug_unique', 'slug', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tag_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)


class ProductTag(Base):
    __tablename__ = "product_tags"
    __table_args__ = (
        Index('idx_product_tag_product', 'product_id'),
        Index('idx_product_tag_tag', 'tag_id'),
    )

    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="product_tags")
    tag: Mapped["Tag"] = relationship("Tag")