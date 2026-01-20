from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class UserPaymentToken(Base):
    """
    Stores tokenized card details for a user.
    These tokens are provided by the payment gateway (MPGS).
    """

    __tablename__ = "user_payment_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.firebase_uid"), nullable=False, index=True
    )

    # Provider checks (in case you switch or use multiple)
    provider: Mapped[str] = mapped_column(String(50), default="mastercard_mpgs")

    # The Token returned by MPGS
    token: Mapped[str] = mapped_column(String(255), nullable=False)

    # Display info
    masked_card: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # e.g., "XXXXXXXXXXXX1111"
    card_type: Mapped[str] = mapped_column(String(20))  # VISA, MASTERCARD
    expiry_month: Mapped[str] = mapped_column(String(2))
    expiry_year: Mapped[str] = mapped_column(String(4))

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=False
    )
