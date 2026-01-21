import uuid
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
import httpx

from sqlalchemy import select, update

from src.api.payments.models import InitiatePaymentSchema, SavedCardSchema
from src.config.settings import settings
from src.database.connection import AsyncSessionLocal
from src.database.models.payment import PaymentTransaction
from src.database.models.payment_token import UserPaymentToken
from src.shared.error_handler import ErrorHandler
from src.shared.exceptions import ResourceNotFoundException, ValidationException


class PaymentService:
    """
    Payment Logic for Mastercard MPGS.
    Handles session creation, tokenization, and callback processing.
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.merchant_id = settings.MPGS_MERCHANT_ID
        self.api_username = settings.MPGS_API_USERNAME or f"merchant.{self.merchant_id}"
        self.api_password = settings.MPGS_API_PASSWORD
        self.gateway_url = settings.MPGS_GATEWAY_URL

        if not all([self.merchant_id, self.api_password, self.gateway_url]):
            self._error_handler.logger.warning("MPGS credentials missing in settings.")

    async def get_saved_cards(self, user_id: str) -> List[SavedCardSchema]:
        """Fetch saved cards for a user."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserPaymentToken)
                .filter(UserPaymentToken.user_id == user_id)
                .order_by(
                    UserPaymentToken.is_default.desc(),
                    UserPaymentToken.created_at.desc(),
                )
            )
            tokens = result.scalars().all()
            return [SavedCardSchema.model_validate(t) for t in tokens]

    async def initiate_payment(
        self,
        payment_data: InitiatePaymentSchema,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Initiate MPGS Hosted Checkout Session.
        """
        # 1. Generate Payment Reference
        payment_reference = f"PAY-{uuid.uuid4().hex[:12].upper()}"

        # 2. Persist Transaction
        async with AsyncSessionLocal() as session:
            async with session.begin():
                new_transaction = PaymentTransaction(
                    payment_reference=payment_reference,
                    user_id=user_id,
                    cart_ids=payment_data.cart_ids,
                    amount=payment_data.amount,
                    save_card_on_success=payment_data.save_card,
                    checkout_data=json.dumps(payment_data.checkout_data)
                    if payment_data.checkout_data
                    else None,
                    status="initiated",
                )
                session.add(new_transaction)
                await session.flush()

                # Link Orders (optional, if we want orders to know their text-ref immediately)
                # Note: order creation might happen before or we might link by cart_ids
                # For now, linking is done during order creation or updated here if orders exist

        # 3. Resolve Token specific data
        source_token = None
        if payment_data.source_token_id:
            async with AsyncSessionLocal() as session:
                token_record = await session.get(
                    UserPaymentToken, payment_data.source_token_id
                )
                if token_record and token_record.user_id == user_id:
                    source_token = token_record.token

        # 4. Build Gateway Request
        # API: INITIATE CHECKOUT
        endpoint = f"{self.gateway_url}/merchant/{self.merchant_id}/session"

        payload = {
            "apiOperation": "INITIATE_CHECKOUT",
            "order": {
                "id": payment_reference,
                "amount": "{:.2f}".format(
                    payment_data.amount.quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                ),
                "currency": payment_data.currency,
                "description": "Order Payment",
            },
            "interaction": {
                "operation": "PURCHASE",
                "displayControl": {
                    "billingAddress": "HIDE",
                    "customerEmail": "HIDE",
                    "shipping": "HIDE",
                },
                "merchant": {
                    "name": "Celeste",
                    "url": "https://celeste.com",
                    "address": {"line1": "200 Sample St", "line2": "1234"},
                },
                "returnUrl": f"{settings.API_BASE_URL}/payments/callback?ref={payment_reference}",
            },
        }

        if source_token:
            payload["sourceOfFunds"] = {"type": "CARD", "token": source_token}

        # 5. Call Gateway
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    endpoint,
                    json=payload,
                    auth=(str(self.api_username), str(self.api_password)),
                )
                response.raise_for_status()
                data = response.json()

                session_id = data.get("session", {}).get("id")
                success_indicator = data.get("successIndicator")

                return {
                    "session_id": session_id,
                    "payment_reference": payment_reference,
                    "merchant_id": self.merchant_id,
                    "success_indicator": success_indicator,
                }

            except httpx.HTTPError as e:
                self._error_handler.logger.error(f"MPGS Initiate Error: {str(e)}")
                # Log response body if available
                if isinstance(e, httpx.HTTPStatusError):
                    self._error_handler.logger.error(
                        f"MPGS Response: {e.response.text}"
                    )
                raise ValidationException("Failed to initiate payment gateway session.")

    async def process_payment_callback(
        self,
        payment_reference: str,
        result_indicator: Optional[str] = None,
        background_tasks: Any = None,
    ):
        """
        Finalize payment after user completes hosted checkout.
        """

        # 1. Fetch Transaction
        async with AsyncSessionLocal() as session:
            transaction_result = await session.execute(
                select(PaymentTransaction).filter(
                    PaymentTransaction.payment_reference == payment_reference
                )
            )
            transaction = transaction_result.scalars().first()

            if not transaction:
                raise ResourceNotFoundException("Payment transaction not found.")

            # 2. Verify with Gateway (using simple GET order or RETRIEVE SESSION)
            # We typically use GET /order/{orderId} to check status
            endpoint = f"{self.gateway_url}/merchant/{self.merchant_id}/order/{payment_reference}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    endpoint, auth=(str(self.api_username), str(self.api_password))
                )
                if response.status_code == 200:
                    order_data = response.json()
                    status = order_data.get("result")  # e.g. "SUCCESS"

                    if status == "SUCCESS":
                        transaction.status = "success"

                        # Deferred Order Creation: Create orders only now that payment is successful
                        if transaction.checkout_data:
                            from src.api.users.checkout_service import CheckoutService
                            from src.api.users.checkout_models import (
                                CheckoutRequestSchema,
                            )

                            checkout_service = CheckoutService()

                            # Handle both string and dict cases for checkout_data
                            data_to_validate = transaction.checkout_data
                            if isinstance(data_to_validate, str):
                                data_to_validate = json.loads(data_to_validate)

                            checkout_request = CheckoutRequestSchema.model_validate(
                                data_to_validate
                            )

                            # Create the orders (this also updates carts to ORDERED and places inventory holds)
                            await checkout_service.create_order(
                                transaction.user_id, checkout_request
                            )

                            # Now confirm the newly created orders (triggers Odoo sync)
                            from src.api.orders.service import OrderService

                            order_service = OrderService()
                            await order_service.confirm_orders_by_cart_ids(
                                transaction.cart_ids, background_tasks=background_tasks
                            )

                        # 3. Handle Save Card (Tokenization)
                        if transaction.save_card_on_success:
                            await self._create_payment_token(
                                session, transaction, order_data
                            )

                    else:
                        transaction.status = "failed"
                else:
                    transaction.status = "unknown_gateway_error"

            # Commit updates
            session.add(transaction)
            await session.commit()

            return {
                "status": transaction.status,
                "payment_reference": payment_reference,
            }

    async def get_transaction_status(self, payment_reference: str) -> Dict[str, Any]:
        """Check the current local status of a transaction."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PaymentTransaction).filter(
                    PaymentTransaction.payment_reference == payment_reference
                )
            )
            transaction = result.scalars().first()
            if not transaction:
                raise ResourceNotFoundException("Transaction not found")

            return {
                "status": transaction.status,
                "payment_reference": payment_reference,
                "updated_at": transaction.updated_at.isoformat() if transaction.updated_at else None,
            }

    async def _create_payment_token(self, session, transaction, order_data):
        """
        Internal: Create token from successful transaction data.
        """
        source_of_funds = order_data.get("sourceOfFunds", {})
        provided = source_of_funds.get("provided", {})
        card = provided.get("card", {})

        # In Hosted Checkout, MPGS can return a token if configured,
        # or we might need to call the Tokenize API if we only have the card details.
        # Typically, for 'PURCHASE' with 'save_card' intent, we use the session to tokenize.

        token = provided.get("token") or source_of_funds.get("token")

        if not token:
            # If no token in response, we might need a separate call or check MPGS config
            self._error_handler.logger.warning(
                f"No token found in MPGS response for order {transaction.payment_reference}"
            )
            return

        # Prepare masked card info
        masked_number = card.get("number", "#### #### #### ####")
        expiry = card.get("expiry", {})

        # Check if token already exists for this user to avoid duplicates
        existing_result = await session.execute(
            select(UserPaymentToken).filter(
                UserPaymentToken.user_id == transaction.user_id,
                UserPaymentToken.token == token,
            )
        )
        if existing_result.scalars().first():
            return

        new_token = UserPaymentToken(
            user_id=transaction.user_id,
            token=token,
            masked_card=masked_number,
            card_type=card.get("scheme"),
            expiry_month=expiry.get("month"),
            expiry_year=expiry.get("year"),
            is_default=True,  # Logic can be more complex to determine default
        )

        # Reset other cards from default
        await session.execute(
            update(UserPaymentToken)
            .filter(UserPaymentToken.user_id == transaction.user_id)
            .values(is_default=False)
        )

        session.add(new_token)
        # Session is committed by the caller (process_payment_callback)
