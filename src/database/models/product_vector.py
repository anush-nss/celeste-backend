from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.product import Product


class ProductVector(Base):
    """
    Stores vector embeddings for products for semantic search.
    (Note: Vector functionality is currently disabled for Vercel)
    """

    __tablename__ = "product_vectors"
    __table_args__ = (
        Index("idx_product_vectors_product_id", "product_id", unique=True),
        Index("idx_product_vectors_updated", "last_updated"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )

    # Vector embedding stored as JSONB for portability
    vector_embedding: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # TF-IDF sparse vector stored as JSONB
    tfidf_vector: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Combined text content used for vectorization
    text_content: Mapped[str] = mapped_column(Text, nullable=False)

    # Track when vectorization was done
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
    )

    # Track embedding model version for future updates
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="vector")
