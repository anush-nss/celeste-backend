from sqlalchemy import String, ForeignKey, Integer, Index, CheckConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from typing import Optional, List
from src.database.base import Base

class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (
        Index('idx_carts_created_by', 'created_by'),
        Index('idx_carts_status', 'status'),
        Index('idx_carts_created_at', 'created_at'),
        CheckConstraint("status IN ('active', 'inactive', 'ordered')", name='check_cart_status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default='Cart')
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='active')
    created_by: Mapped[str] = mapped_column(String(128), ForeignKey("users.firebase_uid", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'), nullable=False)
    ordered_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    users: Mapped[List["CartUser"]] = relationship("CartUser", back_populates="cart", cascade="all, delete-orphan")


class CartUser(Base):
    __tablename__ = "cart_users"
    __table_args__ = (
        Index('idx_cart_users_user_id', 'user_id'),
        Index('idx_cart_users_role', 'role'),
        CheckConstraint("role IN ('owner', 'viewer')", name='check_cart_user_role'),
    )

    cart_id: Mapped[int] = mapped_column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), ForeignKey("users.firebase_uid", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default='owner')
    shared_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)

    # Relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="users")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint('cart_id', 'product_id', name='unique_cart_product'),
        Index('idx_cart_items_cart_id', 'cart_id'),
        Index('idx_cart_items_product_id', 'product_id'),
        CheckConstraint('quantity > 0', name='check_cart_item_quantity_positive'),
        CheckConstraint('quantity <= 1000', name='check_cart_item_quantity_reasonable'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'), nullable=False)

    # Relationships
    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")