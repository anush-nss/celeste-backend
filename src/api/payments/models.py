from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SavedCardSchema(BaseModel):
    id: int
    masked_card: str
    card_type: Optional[str] = None
    expiry_month: Optional[str] = None
    expiry_year: Optional[str] = None
    is_default: bool

    class Config:
        from_attributes = True


class InitiatePaymentSchema(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Total amount to charge")
    currency: str = Field("LKR", description="Currency code")
    cart_ids: List[int] = Field(..., description="List of cart IDs to link")
    source_token_id: int = Field(..., description="ID of saved card token")
    checkout_data: Optional[Dict[str, Any]] = None


class PaymentResponseSchema(BaseModel):
    session_id: str
    payment_reference: str
    merchant_id: str
    success_indicator: Optional[str] = None


class PaymentCallbackSchema(BaseModel):
    """
    Schema for receiving callback data.
    Fields depend on what the gateway actually POSTs or what we verify from the URL query params.
    MPGS typically requires us to fetch result, but if we use a return URL, we might get params.
    For this implementation, we assume we receive transaction reference details.
    """

    resultIndicator: Optional[str] = None
    sessionVersion: Optional[str] = None

    # We might just receive the whole payload
    class Config:
        extra = "allow"
