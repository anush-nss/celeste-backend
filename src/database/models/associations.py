"""
Association tables for many-to-many relationships
"""

from sqlalchemy import Column, ForeignKey, Index, Integer, Table, text
from sqlalchemy.dialects.postgresql import TIMESTAMP

from src.database.base import Base

# Association table for many-to-many relationship between products and categories
product_categories = Table(
    "product_categories",
    Base.metadata,
    Column(
        "product_id",
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", TIMESTAMP(timezone=True), server_default=text("NOW()")),
    # Relationship indexes for optimal JOINs
    Index("idx_product_categories_product_id", "product_id"),
    Index("idx_product_categories_category_id", "category_id"),
    Index("idx_product_categories_composite", "category_id", "product_id"),
    Index("idx_product_categories_product_category", "product_id", "category_id"),
    # Timestamp index for audit queries
    Index("idx_product_categories_created_at", "created_at"),
)


# Association table for many-to-many relationship between stores and riders
store_riders = Table(
    "store_riders",
    Base.metadata,
    Column(
        "store_id",
        Integer,
        ForeignKey("stores.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "rider_profile_id",
        Integer,
        ForeignKey("rider_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("assigned_at", TIMESTAMP(timezone=True), server_default=text("NOW()")),
    # Relationship indexes
    Index("idx_store_riders_store", "store_id"),
    Index("idx_store_riders_rider", "rider_profile_id"),
    Index("idx_store_riders_composite", "store_id", "rider_profile_id"),
)
