from typing import Optional
from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy import text
from datetime import datetime
from src.database.base import Base

class Tier(Base):
    __tablename__ = "tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    min_lifetime_value: Mapped[float] = mapped_column(Float, default=0.0)
    min_monthly_orders: Mapped[int] = mapped_column(Integer, default=0)
    min_orders: Mapped[int] = mapped_column(Integer, default=0)
    min_monthly_value: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text('NOW()'), onupdate=text('NOW()'))