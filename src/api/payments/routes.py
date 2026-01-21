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
from fastapi.responses import HTMLResponse

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
    Returns HTML for browser/WebView compatibility.
    """
    result = await payment_service.process_payment_callback(
        ref, resultIndicator, background_tasks
    )
    
    # Return HTML instead of JSON for WebView compatibility
    status = result.get("status", "unknown")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payment {status.title()}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: #f5f5f5;
            }}
            .container {{
                text-align: center;
                padding: 2rem;
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            .success {{ color: #10b981; }}
            .failed {{ color: #ef4444; }}
            .processing {{ color: #f59e0b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="{status}">Payment {status.title()}</h1>
            <p>Reference: {ref}</p>
            <p>You can close this window.</p>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


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
