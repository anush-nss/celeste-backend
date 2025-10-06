from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.database.models.associations import product_categories

if TYPE_CHECKING:
    from src.database.models.product import Product


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("sort_order >= 0", name="check_sort_order_non_negative"),
        # Core category navigation indexes
        Index("idx_categories_parent_sort", "parent_category_id", "sort_order"),
        Index("idx_categories_sort_order", "sort_order"),
        Index("idx_categories_parent", "parent_category_id"),
        # Category hierarchy queries
        Index(
            "idx_categories_hierarchy_root",
            "parent_category_id",
            "name",
            postgresql_where="parent_category_id IS NULL",
        ),
        Index(
            "idx_categories_hierarchy_children",
            "parent_category_id",
            "sort_order",
            "name",
            postgresql_where="parent_category_id IS NOT NULL",
        ),
        # Search and filtering indexes
        Index(
            "idx_categories_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        # Administrative and timestamp indexes
        Index("idx_categories_created_at", "created_at"),
        Index("idx_categories_updated_at", "updated_at"),
        # Composite indexes for common queries
        Index("idx_categories_parent_name", "parent_category_id", "name"),
        Index("idx_categories_sort_name", "sort_order", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    parent_category_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
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

    # Self-referencing relationship for parent/child categories
    parent_category: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side=[id], back_populates="subcategories"
    )
    subcategories: Mapped[List["Category"]] = relationship(
        "Category", back_populates="parent_category", cascade="all, delete-orphan"
    )

    # Relationship with products (many-to-many)
    products: Mapped[List["Product"]] = relationship(
        "Product", secondary=product_categories, back_populates="categories"
    )
