from datetime import datetime
from typing import Optional

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class SearchInteraction(Base):
    """
    Tracks all authenticated user search interactions for analytics and personalization.
    Only logged-in users are tracked.
    """

    __tablename__ = "search_interactions"
    __table_args__ = (
        Index("idx_search_interactions_user_id", "user_id"),
        Index("idx_search_interactions_timestamp", "timestamp"),
        Index("idx_search_interactions_user_time", "user_id", "timestamp"),
        Index("idx_search_interactions_query", "query"),
        Index("idx_search_interactions_mode", "mode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Firebase UID (required - only authenticated users)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Search query
    query: Mapped[str] = mapped_column(Text, nullable=False)

    # Search mode: 'dropdown' or 'full'
    mode: Mapped[str] = mapped_column(String(50), nullable=False)

    # Number of results returned
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Product IDs that were clicked/selected from results
    clicked_product_ids: Mapped[list] = mapped_column(
        ARRAY(Integer), nullable=True, default=[]
    )

    # Timestamp of search
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, index=True
    )

    # Additional context (filters applied, search time, etc.)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
