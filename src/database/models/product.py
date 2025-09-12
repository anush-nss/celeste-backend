from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import ARRAY, String, DECIMAL, Text, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database.base import Base
from src.database.models.associations import product_categories

if TYPE_CHECKING:
    from src.database.models.category import Category

class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    brand: Mapped[str] = mapped_column(String(255), nullable=False)
    base_price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    unit_measure: Mapped[str] = mapped_column(String(20), nullable=False)
    image_urls: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'))
    
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


class Tag(Base):
    __tablename__ = "tags"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tag_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))


class ProductTag(Base):
    __tablename__ = "product_tags"
    
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="product_tags")
    tag: Mapped["Tag"] = relationship("Tag")