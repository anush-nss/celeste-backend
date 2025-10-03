from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.product import Tag
    from src.database.models.store import Store


class StoreTag(Base):
    __tablename__ = "store_tags"
    __table_args__ = (
        Index("idx_store_tag_store", "store_id"),
        Index("idx_store_tag_tag", "tag_id"),
    )

    store_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True
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
    store: Mapped["Store"] = relationship("Store", back_populates="store_tags")
    tag: Mapped["Tag"] = relationship("Tag")
