import uuid
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update

from src.api.payments.models import InitiatePaymentSchema, SavedCardSchema
from src.config.settings import settings
from src.database.connection import AsyncSessionLocal
from src.database.models.payment import PaymentTransaction
from src.database.models.payment_token import UserPaymentToken
from src.shared.error_handler import ErrorHandler
from src.shared.exceptions import ResourceNotFoundException, ValidationException
from src.api.payments.providers.factory import PaymentFactory


class PaymentService:
    """
    Modular Payment Service.
    Coordinates between different payment providers and internal business logic.
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

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
        provider_id: str = "mastercard_mpgs",
    ) -> Dict[str, Any]:
        """
        Initiate Payment Session via Provider using a saved card.
        """
        # 1. Fetch the token record
        async with AsyncSessionLocal() as session:
            token_record = await session.get(
                UserPaymentToken, payment_data.source_token_id
            )
            if not token_record or token_record.user_id != user_id:
                raise ResourceNotFoundException("Saved card not found or invalid.")
            source_token = token_record.token

        # 2. Generate Payment Reference
        payment_reference = f"PAY-{uuid.uuid4().hex[:12].upper()}"

        # 3. Persist Transaction
        async with AsyncSessionLocal() as session:
            async with session.begin():
                new_transaction = PaymentTransaction(
                    payment_reference=payment_reference,
                    user_id=user_id,
                    provider=provider_id,
                    cart_ids=payment_data.cart_ids,
                    amount=payment_data.amount,
                    save_card_on_success=False,  # Already using a saved card
                    checkout_data=json.dumps(payment_data.checkout_data)
                    if payment_data.checkout_data
                    else None,
                    status="initiated",
                )
                session.add(new_transaction)
                await session.flush()

        # 4. Get Provider and Initiate
        provider = PaymentFactory.get_provider(provider_id)
        return_url = (
            f"{settings.API_BASE_URL}/payments/callback?ref={payment_reference}"
        )

        try:
            result = await provider.initiate_checkout(
                amount=payment_data.amount,
                currency=payment_data.currency,
                reference=payment_reference,
                return_url=return_url,
                source_token=source_token,
            )

            # Update transaction with session_id
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(PaymentTransaction)
                    .filter(PaymentTransaction.payment_reference == payment_reference)
                    .values(session_id=result.get("session_id"))
                )
                await session.commit()

            return {
                "session_id": result.get("session_id"),
                "payment_reference": payment_reference,
                "merchant_id": result.get("merchant_id"),
                "success_indicator": result.get("success_indicator"),
            }

        except Exception as e:
            self._error_handler.logger.error(
                f"Payment Initiation Error ({provider_id}): {str(e)}"
            )
            raise ValidationException(f"Failed to initiate payment with {provider_id}.")

    async def initiate_add_card(
        self,
        user_id: str,
        provider_id: str = "mastercard_mpgs",
    ) -> Dict[str, Any]:
        """
        Initiate a session specifically to add/save a card.
        """
        payment_reference = f"SETUP-{uuid.uuid4().hex[:12].upper()}"

        async with AsyncSessionLocal() as session:
            async with session.begin():
                new_transaction = PaymentTransaction(
                    payment_reference=payment_reference,
                    user_id=user_id,
                    provider=provider_id,
                    cart_ids=[],  # No carts for card setup
                    amount=Decimal("0.00"),
                    save_card_on_success=True,
                    status="initiated",
                )
                session.add(new_transaction)

        provider = PaymentFactory.get_provider(provider_id)
        return_url = (
            f"{settings.API_BASE_URL}/payments/callback?ref={payment_reference}"
        )

        result = await provider.initiate_add_card(payment_reference, return_url)

        async with AsyncSessionLocal() as session:
            await session.execute(
                update(PaymentTransaction)
                .filter(PaymentTransaction.payment_reference == payment_reference)
                .values(session_id=result.get("session_id"))
            )
            await session.commit()

        return {
            "session_id": result.get("session_id"),
            "payment_reference": payment_reference,
            "merchant_id": result.get("merchant_id"),
            "success_indicator": result.get("success_indicator"),
        }

    async def process_payment_callback(
        self,
        payment_reference: str,
        result_indicator: Optional[str] = None,
        background_tasks: Any = None,
    ):
        """
        Finalize payment or card setup after user completes interaction.
        """
        async with AsyncSessionLocal() as session:
            self._error_handler.logger.info(f"Processing callback for reference: {payment_reference}")
            
            # Raw lookup for debugging
            from sqlalchemy import text
            raw_result = await session.execute(
                text("SELECT id FROM payment_transactions WHERE payment_reference = :ref"),
                {"ref": payment_reference}
            )
            raw_id = raw_result.scalar()
            self._error_handler.logger.info(f"Raw SQL lookup ID for '{payment_reference}': {raw_id}")

            transaction_result = await session.execute(
                select(PaymentTransaction).filter(
                    PaymentTransaction.payment_reference == payment_reference
                )
            )
            transaction = transaction_result.scalars().first()

            if not transaction:
                self._error_handler.logger.error(f"Transaction not found for reference: {payment_reference}")
                raise ResourceNotFoundException("Payment transaction not found.")

            if transaction.status in ["success", "failed"]:
                return {
                    "status": transaction.status,
                    "payment_reference": payment_reference,
                }

            # 1. Get Provider
            provider = PaymentFactory.get_provider(transaction.provider)

            # 2. Verify with Gateway
            try:
                order_data = await provider.verify_transaction(payment_reference)
                # MPGS uses 'result', other gateways might use something else.
                # Base provider handle_webhook or a common status mapper could be used.
                status = order_data.get("result") or order_data.get("status")

                if status in ["SUCCESS", "CAPTURED", "APPROVED"]:
                    transaction.status = "success"

                    # 3. Deferred Order Creation (if checkout)
                    if transaction.cart_ids and transaction.checkout_data:
                        await self._create_orders(transaction, background_tasks)

                    # 4. Handle Save Card
                    if transaction.save_card_on_success:
                        await self._handle_tokenization(
                            session, transaction, order_data, provider
                        )

                else:
                    transaction.status = "failed"

            except Exception as e:
                self._error_handler.logger.error(
                    f"Callback verification failed: {str(e)}"
                )
                transaction.status = "error"

            session.add(transaction)
            await session.commit()
            return {
                "status": transaction.status,
                "payment_reference": payment_reference,
            }

    async def _handle_tokenization(self, session, transaction, order_data, provider):
        """Standardized tokenization handling."""
        source_of_funds = order_data.get("sourceOfFunds", {})
        token = source_of_funds.get("token") or source_of_funds.get("provided", {}).get(
            "token"
        )
        self._error_handler.logger.info(f"Initial token from order_data: {token}")

        if not token and transaction.session_id:
            self._error_handler.logger.info(f"No token found, attempting tokenize_from_session for session: {transaction.session_id}")
            # Explicitly call provider to tokenize from session if not in order data
            token_data = await provider.tokenize_from_session(transaction.session_id)
            token = token_data.get("token")
            self._error_handler.logger.info(f"Token from session: {token}")
            # Update card details from token data if available
            if token_data:
                order_data["sourceOfFunds"] = token_data.get(
                    "sourceOfFunds", source_of_funds
                )

        if token:
            self._error_handler.logger.info(f"Proceeding to create token record for token: {token}")
            await self._create_payment_token_record(
                session, transaction, token, order_data
            )
        else:
            self._error_handler.logger.warning(f"No token could be resolved for transaction {transaction.payment_reference}")

    async def _create_payment_token_record(
        self, session, transaction, token, order_data
    ):
        """Create or update UserPaymentToken record."""
        source_of_funds = order_data.get("sourceOfFunds", {})
        card = source_of_funds.get("provided", {}).get("card", {})
        masked_number = card.get("number", "#### #### #### ####")
        expiry = card.get("expiry", {})
        
        self._error_handler.logger.info(f"Creating token record: user_id={transaction.user_id}, provider={transaction.provider}, card_type={card.get('scheme')}")

        # Avoid duplicates
        existing = await session.execute(
            select(UserPaymentToken).filter(
                UserPaymentToken.user_id == transaction.user_id,
                UserPaymentToken.token == token,
                UserPaymentToken.provider == transaction.provider,
            )
        )
        if existing.scalars().first():
            self._error_handler.logger.info(f"Token {token} already exists for user {transaction.user_id}")
            return

        # Set others to non-default
        await session.execute(
            update(UserPaymentToken)
            .filter(UserPaymentToken.user_id == transaction.user_id)
            .values(is_default=False)
        )

        new_token = UserPaymentToken(
            user_id=transaction.user_id,
            token=token,
            provider=transaction.provider,
            masked_card=masked_number,
            card_type=card.get("scheme"),
            expiry_month=expiry.get("month"),
            expiry_year=expiry.get("year"),
            is_default=True,
        )
        session.add(new_token)
        self._error_handler.logger.info(f"Added new token record to session for user {transaction.user_id}")

    async def _create_orders(self, transaction, background_tasks):
        """Internal helper for order creation."""
        from src.api.users.checkout_service import CheckoutService
        from src.api.users.checkout_models import CheckoutRequestSchema
        from src.api.orders.service import OrderService

        checkout_service = CheckoutService()
        data_to_validate = transaction.checkout_data
        if isinstance(data_to_validate, str):
            data_to_validate = json.loads(data_to_validate)

        checkout_request = CheckoutRequestSchema.model_validate(data_to_validate)
        await checkout_service.create_order(transaction.user_id, checkout_request)

        order_service = OrderService()
        await order_service.confirm_orders_by_cart_ids(
            transaction.cart_ids, background_tasks=background_tasks
        )

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
                "updated_at": transaction.updated_at.isoformat()
                if transaction.updated_at
                else None,
            }
