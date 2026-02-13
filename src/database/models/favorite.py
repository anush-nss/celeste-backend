from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, Integer, String, text, ARRAY
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base

if TYPE_CHECKING:
    from src.database.models.user import User


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.firebase_uid", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    product_ids: Mapped[List[int]] = mapped_column(
        ARRAY(Integer), default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="favorites")
