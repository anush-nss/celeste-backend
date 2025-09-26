from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, DECIMAL, Integer, ForeignKey, Enum, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from src.database.base import Base
from src.config.constants import OrderStatus

if TYPE_CHECKING:
    from src.database.models.user import User
    from src.database.models.product import Product
    from src.database.models.store import Store

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index('idx_orders_user_id', 'user_id'),
        Index('idx_orders_status', 'status'),
        Index('idx_orders_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), ForeignKey("users.firebase_uid"), nullable=False)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'), nullable=False)

    # Relationships
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    user: Mapped["User"] = relationship("User", back_populates="orders")
    store: Mapped["Store"] = relationship("Store")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index('idx_order_items_order_id', 'order_id'),
        Index('idx_order_items_source_cart_id', 'source_cart_id'),
        Index('idx_order_items_product_id', 'product_id'),
        CheckConstraint('quantity > 0', name='check_order_item_quantity_positive'),
        CheckConstraint('unit_price >= 0', name='check_order_item_unit_price_positive'),
        CheckConstraint('total_price >= 0', name='check_order_item_total_price_positive'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    source_cart_id: Mapped[int] = mapped_column(Integer, ForeignKey("carts.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product")

# The back-population for User.orders is now defined in the User model in user.py
