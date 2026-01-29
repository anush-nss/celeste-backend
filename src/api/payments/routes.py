from typing import List, Annotated
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    BackgroundTasks,
    Header,
    HTTPException,
)
from datetime import datetime

from src.api.auth.models import DecodedToken
from src.api.payments.models import (
    InitiatePaymentSchema,
    PaymentResponseSchema,
    SavedCardSchema,
)
from src.api.payments.service import PaymentService
from src.dependencies.auth import get_current_user
from src.config.settings import settings
from src.shared.responses import success_response
from src.shared.exceptions import UnauthorizedException
from fastapi.responses import HTMLResponse
from src.database.connection import AsyncSessionLocal
from src.database.models.webhook_notification import WebhookNotification

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
    summary="Initiate a payment session",
)
async def initiate_payment(
    payment_data: InitiatePaymentSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    result = await payment_service.initiate_payment(payment_data, current_user.uid)
    return success_response(result)


@payments_router.post(
    "/add-card",
    response_model=PaymentResponseSchema,
    summary="Initiate a session to add a new card",
)
async def add_card(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    provider: str = Query("mastercard_mpgs", description="Payment provider ID"),
):
    """
    Creates a setup session with the payment gateway to tokenize a card without a purchase.
    """
    result = await payment_service.initiate_add_card(current_user.uid, provider)
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


@payments_router.post(
    "/webhook/mpgs",
    summary="MPGS Webhook Notification Handler",
)
async def payment_webhook_mpgs(
    request: Request,
    background_tasks: BackgroundTasks,
    x_notification_secret: str = Header(None, alias="X-Notification-Secret"),
    x_notification_id: str = Header(None, alias="X-Notification-ID"),
    x_notification_attempt: int = Header(None, alias="X-Notification-Attempt"),
):
    """
    Webhook endpoint for MPGS payment notifications.
    Called server-to-server by Mastercard Gateway.

    Security: Verifies X-Notification-Secret header
    Idempotency: Uses X-Notification-ID to prevent duplicate processing
    Tracking: Logs all webhook attempts in webhook_notifications table
    """

    # 1. Verify webhook secret
    if not settings.MPGS_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    if x_notification_secret != settings.MPGS_WEBHOOK_SECRET:
        raise UnauthorizedException("Invalid webhook secret")

    # 2. Parse webhook payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")

    # 3. Extract payment reference
    payment_ref = payload.get("order", {}).get("id")
    if not payment_ref:
        raise HTTPException(status_code=400, detail="Missing order.id in payload")

    # 4. Check for duplicate notification using X-Notification-ID
    async with AsyncSessionLocal() as session:
        # Check if this notification was already processed
        from sqlalchemy import select

        existing = await session.execute(
            select(WebhookNotification).filter(
                WebhookNotification.notification_id == x_notification_id
            )
        )
        existing_notification = existing.scalars().first()

        if existing_notification:
            # Duplicate notification - return success without reprocessing
            return {
                "status": "already_processed",
                "notification_id": x_notification_id,
                "attempt": x_notification_attempt,
            }

        # 5. Log webhook notification
        webhook_log = WebhookNotification(
            notification_id=x_notification_id,
            payment_reference=payment_ref,
            attempt_number=x_notification_attempt or 1,
            payload=payload,
            status="received",
        )
        session.add(webhook_log)
        await session.commit()
        webhook_log_id = webhook_log.id

    # 6. Process payment (reuse callback logic)
    try:
        result = await payment_service.process_payment_callback(
            payment_ref, None, background_tasks
        )

        # 7. Update webhook log as processed
        async with AsyncSessionLocal() as session:
            webhook_log = await session.get(WebhookNotification, webhook_log_id)
            if webhook_log:
                webhook_log.status = "processed"
                webhook_log.processed_at = datetime.utcnow()
                await session.commit()

        # 8. Return HTTP 200 within 2 seconds (MPGS requirement)
        return {
            "status": "success",
            "notification_id": x_notification_id,
            "payment_reference": payment_ref,
            "result": result.get("status"),
        }

    except Exception as e:
        # Log error in webhook notification
        async with AsyncSessionLocal() as session:
            webhook_log = await session.get(WebhookNotification, webhook_log_id)
            if webhook_log:
                webhook_log.status = "failed"
                webhook_log.error_message = str(e)
                webhook_log.processed_at = datetime.utcnow()
                await session.commit()

        # Still return 200 to prevent retries for application errors
        # MPGS will retry anyway if we return non-200
        return {
            "status": "error",
            "notification_id": x_notification_id,
            "error": str(e),
        }


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
