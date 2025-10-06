from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

if TYPE_CHECKING:
    pass


class EcommerceCategory(Base):
    __tablename__ = "ecommerce_categories"
    __table_args__ = (
        Index("idx_ecommerce_categories_name", "name"),
        Index("idx_ecommerce_categories_parent", "parent_category_id"),
        Index("idx_ecommerce_categories_parent_name", "parent_category_id", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    parent_category_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("ecommerce_categories.id", ondelete="CASCADE"),
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
    parent_category: Mapped[Optional["EcommerceCategory"]] = relationship(
        "EcommerceCategory", remote_side=[id], back_populates="subcategories"
    )
    subcategories: Mapped[List["EcommerceCategory"]] = relationship(
        "EcommerceCategory",
        back_populates="parent_category",
        cascade="all, delete-orphan",
    )
