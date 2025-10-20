from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class ProductInteraction(Base):
    """
    Tracks detailed user interactions with products for personalization
    and collaborative filtering.

    Tracks: search clicks, views, cart adds, orders, wishlist adds.
    Only for authenticated users.
    """

    __tablename__ = "product_interactions"
    __table_args__ = (
        Index("idx_product_interactions_user_id", "user_id"),
        Index("idx_product_interactions_product_id", "product_id"),
        Index("idx_product_interactions_timestamp", "timestamp"),
        Index("idx_product_interactions_type", "interaction_type"),
        Index("idx_product_interactions_user_time", "user_id", "timestamp"),
        Index("idx_product_interactions_user_product", "user_id", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Firebase UID
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Product ID
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )

    # Interaction type: search_click, view, cart_add, order, wishlist_add
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Weighted score for this interaction (from INTERACTION_SCORES constant)
    interaction_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Timestamp of interaction
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    # Additional context (search query, cart_id, order_id, etc.)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
