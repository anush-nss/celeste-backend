from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    ARRAY,
    DECIMAL,
    Boolean,
    CheckConstraint,
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
from src.database.models.associations import product_categories

if TYPE_CHECKING:
    from src.database.models.category import Category
    from src.database.models.inventory import Inventory


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("base_price >= 0", name="check_base_price_non_negative"),
        # Core performance indexes
        Index("idx_products_base_price", "base_price"),
        Index("idx_products_created_at", "created_at"),
        Index("idx_products_ref", "ref", postgresql_where="ref IS NOT NULL"),
        Index(
            "idx_products_ecommerce_category",
            "ecommerce_category_id",
            postgresql_where="ecommerce_category_id IS NOT NULL",
        ),
        # Composite indexes for complex queries
        Index("idx_products_price_range_pagination", "base_price", "id"),
        Index(
            "idx_products_category_price_id",
            "ecommerce_category_id",
            "base_price",
            "id",
            postgresql_where="ecommerce_category_id IS NOT NULL",
        ),
        Index("idx_products_id_pagination", "id", postgresql_where="id > 0"),
        # Brand and category combinations
        Index(
            "idx_products_brand_price",
            "brand",
            "base_price",
            postgresql_where="brand IS NOT NULL",
        ),
        Index(
            "idx_products_brand_category",
            "brand",
            "ecommerce_category_id",
            postgresql_where="brand IS NOT NULL AND ecommerce_category_id IS NOT NULL",
        ),
        # Search and filtering indexes
        Index(
            "idx_products_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "idx_products_brand_trgm",
            "brand",
            postgresql_using="gin",
            postgresql_ops={"brand": "gin_trgm_ops"},
            postgresql_where="brand IS NOT NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ref: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    base_price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), nullable=False, index=True
    )
    unit_measure: Mapped[str] = mapped_column(String(20), nullable=False)
    image_urls: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    ecommerce_category_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    ecommerce_subcategory_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
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
    categories: Mapped[List["Category"]] = relationship(
        "Category", secondary=product_categories, back_populates="products"
    )
    product_tags: Mapped[List["ProductTag"]] = relationship(
        "ProductTag", back_populates="product"
    )
    inventory_levels: Mapped[List["Inventory"]] = relationship(
        "Inventory", back_populates="product", cascade="all, delete-orphan"
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        # Core tag indexes
        Index("idx_tags_type_name", "tag_type", "name"),
        Index(
            "idx_tags_slug", "slug", unique=True, postgresql_where="slug IS NOT NULL"
        ),
        Index(
            "idx_tags_active",
            "is_active",
            "tag_type",
            postgresql_where="is_active = true",
        ),
        Index(
            "idx_tags_type_active_name",
            "tag_type",
            "is_active",
            "name",
            postgresql_where="is_active = true",
        ),
        # Search indexes
        Index(
            "idx_tags_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tag_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False
    )


class ProductTag(Base):
    __tablename__ = "product_tags"
    __table_args__ = (
        # Relationship indexes for optimal JOINs
        Index("idx_product_tags_product_id", "product_id"),
        Index("idx_product_tags_tag_id", "tag_id"),
        Index("idx_product_tags_composite", "tag_id", "product_id"),
        Index("idx_product_tags_product_tag", "product_id", "tag_id", unique=True),
        # Value-based filtering
        Index("idx_product_tags_value", "value", postgresql_where="value IS NOT NULL"),
        Index(
            "idx_product_tags_tag_value",
            "tag_id",
            "value",
            postgresql_where="value IS NOT NULL",
        ),
    )

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="product_tags")
    tag: Mapped["Tag"] = relationship("Tag")
