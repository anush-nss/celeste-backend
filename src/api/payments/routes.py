from typing import List, Annotated
from fastapi import APIRouter, Depends, Query, Request, BackgroundTasks

from src.api.auth.models import DecodedToken
from src.api.payments.models import (
    InitiatePaymentSchema,
    PaymentResponseSchema,
    SavedCardSchema,
)
from src.api.payments.service import PaymentService
from src.dependencies.auth import get_current_user, RoleChecker
from src.config.constants import UserRole
from src.shared.responses import success_response

payments_router = APIRouter(prefix="/payments", tags=["Payments"])
payment_service = PaymentService()


@payments_router.get(
    "/saved-cards",
    response_model=List[SavedCardSchema],
)
async def get_saved_cards(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    """
    Fetch all tokenized cards for the current user.
    """
    cards = await payment_service.get_saved_cards(current_user.uid)
    return success_response(cards)


@payments_router.post(
    "/initiate",
    response_model=PaymentResponseSchema,
    summary="Initiate a payment session (Internal/Admin Only)",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def initiate_payment(
    payment_data: InitiatePaymentSchema,
    current_user: DecodedToken = Depends(get_current_user),
):
    result = await payment_service.initiate_payment(payment_data, current_user.uid)
    return success_response(result)


@payments_router.get(
    "/callback",
    summary="Handle payment return/callback",
)
async def payment_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    ref: str = Query(..., description="Payment Reference (Order ID)"),
    resultIndicator: str = Query(None),
):
    """
    Callback endpoint where MPGS redirects after payment.
    We verify the transaction and update status.
    """
    result = await payment_service.process_payment_callback(
        ref, resultIndicator, background_tasks
    )
    return success_response(result)


@payments_router.get(
    "/status/{ref}",
    summary="Check status of a payment transaction",
)
async def get_payment_status(ref: str):
    """
    Polling endpoint for frontend to check if a payment was successful.
    """
    result = await payment_service.get_transaction_status(ref)
    return success_response(result)
