from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.config.constants import SEARCH_VECTOR_DIM
from src.database.base import Base


class UserPreference(Base):
    """
    Stores aggregated user interests and preferences based on their interactions.

    Used for personalized product ranking and recommendations.
    Built from searches, cart additions, and orders.
    """

    __tablename__ = "user_preferences"
    __table_args__ = (
        Index("idx_user_preferences_user_id", "user_id", unique=True),
        Index("idx_user_preferences_updated", "last_updated"),
        Index("idx_user_preferences_interactions", "total_interactions"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Firebase UID
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Aggregated interest vector (weighted average of interacted products)
    interest_vector: Mapped[Vector] = mapped_column(
        Vector(SEARCH_VECTOR_DIM), nullable=True
    )

    # Category affinity scores: {category_id: score}
    category_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Brand affinity scores: {brand: score}
    brand_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Search keyword frequency: {keyword: count}
    search_keywords: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Last update timestamp
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
    )

    # Total number of interactions (for cold start detection)
    total_interactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
