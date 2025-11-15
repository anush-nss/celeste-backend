from datetime import datetime

from sqlalchemy import Boolean, Float, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class SearchSuggestion(Base):
    """
    Stores popular and suggested search queries for autocomplete/dropdown.

    Built from aggregated search_interactions data.
    Shows trending and frequently searched queries.
    """

    __tablename__ = "search_suggestions"
    __table_args__ = (
        Index("idx_search_suggestions_query", "query", unique=True),
        Index("idx_search_suggestions_count", "search_count"),
        Index("idx_search_suggestions_trending", "is_trending"),
        Index("idx_search_suggestions_success", "success_rate"),
        Index("idx_search_suggestions_last_searched", "last_searched"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Search query text
    query: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Number of times this query was searched
    search_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Success rate: percentage of searches with clicks (0.0 to 1.0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Last time this query was searched
    last_searched: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    # Flag for trending queries (updated by background task)
    is_trending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
