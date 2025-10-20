from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class ProductPopularity(Base):
    """
    Aggregated popularity metrics for products.

    Updated periodically by background tasks based on user interactions.
    Used for trending/popular product endpoints and ranking boosts.
    """

    __tablename__ = "product_popularity"
    __table_args__ = (
        Index("idx_product_popularity_product_id", "product_id", unique=True),
        Index("idx_product_popularity_score", "popularity_score"),
        Index("idx_product_popularity_trending", "trending_score"),
        Index("idx_product_popularity_orders", "order_count"),
        Index("idx_product_popularity_cart", "cart_add_count"),
        Index("idx_product_popularity_searches", "search_count"),
        Index("idx_product_popularity_updated", "last_updated"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Product ID (unique constraint)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Count of times product appeared in search results
    search_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Count of times clicked from search results
    search_click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Count of product views
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Count of times added to cart
    cart_add_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Count of times ordered
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Weighted aggregate popularity score
    popularity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Time-decayed trending score (higher for recent activity)
    trending_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Last update timestamp
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
    )
