"""
Webhook notification tracking model for MPGS payment webhooks.
"""

from datetime import datetime
from sqlalchemy import TIMESTAMP, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class WebhookNotification(Base):
    __tablename__ = "webhook_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    payment_reference: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="received"
    )  # received, processed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
