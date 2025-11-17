from datetime import datetime
from typing import List

from sqlalchemy import (
    ARRAY,
    BOOLEAN,
    INTEGER,
    CheckConstraint,
    Enum,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import TEXT, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.config.constants import PromotionType
from src.database.base import Base


class Promotion(Base):
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint("priority > 0", name="priority_must_be_positive"),
        Index(
            "idx_promotions_type_active_dates",
            "promotion_type",
            "is_active",
            "start_date",
            "end_date",
        ),
        Index("idx_promotions_product_ids", "product_ids", postgresql_using="gin"),
        Index("idx_promotions_category_ids", "category_ids", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    is_active: Mapped[bool] = mapped_column(
        BOOLEAN, nullable=False, server_default=text("TRUE")
    )
    promotion_type: Mapped[PromotionType] = mapped_column(
        Enum(
            PromotionType,
            values_callable=lambda obj: [e.value for e in obj],
            name="promotiontype",
            create_type=False,  # Type is created by migration
        ),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        INTEGER, nullable=False, server_default=text("1")
    )
    start_date: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    product_ids: Mapped[List[int] | None] = mapped_column(ARRAY(INTEGER))
    category_ids: Mapped[List[int] | None] = mapped_column(ARRAY(INTEGER))
    image_urls_web: Mapped[List[str] | None] = mapped_column(ARRAY(TEXT))
    image_urls_mobile: Mapped[List[str] | None] = mapped_column(ARRAY(TEXT))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
    )
