from sqlalchemy import String, ForeignKey, Integer, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from src.database.base import Base

class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_cart_quantity_positive'),
        CheckConstraint('quantity <= 1000', name='check_cart_quantity_reasonable'),
        Index('idx_cart_user_updated', 'user_id', 'updated_at'),
    )

    user_id: Mapped[str] = mapped_column(String(128), ForeignKey("users.firebase_uid", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'), nullable=False)