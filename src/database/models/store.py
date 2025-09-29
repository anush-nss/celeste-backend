from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, Text, Index, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TIMESTAMP
from datetime import datetime
from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.store_tag import StoreTag


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (
        CheckConstraint('latitude >= -90 AND latitude <= 90', name='check_latitude_bounds'),
        CheckConstraint('longitude >= -180 AND longitude <= 180', name='check_longitude_bounds'),

        # Coordinate-based indexes for location queries
        Index('idx_stores_lat_lng', 'latitude', 'longitude'),
        Index('idx_stores_longitude_latitude', 'longitude', 'latitude'),

        # Active stores with location for filtering
        Index('idx_stores_active_location', 'is_active', 'latitude', 'longitude',
              postgresql_where="is_active = true"),

        # Contact information indexes
        Index('idx_stores_email', 'email', postgresql_where="email IS NOT NULL"),
        Index('idx_stores_phone', 'phone', postgresql_where="phone IS NOT NULL"),

        # Name search index
        Index('idx_stores_name_trgm', 'name', postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'}),

        # Status and administrative indexes
        Index('idx_stores_active_name', 'is_active', 'name', postgresql_where="is_active = true"),
        Index('idx_stores_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'), nullable=False)

    # Relationships
    store_tags: Mapped[List["StoreTag"]] = relationship("StoreTag", back_populates="store", cascade="all, delete-orphan")