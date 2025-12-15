"""
Payment service for bank payment gateway integration
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update

from src.shared.error_handler import ErrorHandler


import uuid

from src.database.connection import AsyncSessionLocal
from src.database.models.order import Order, OrderItem
from src.database.models.payment import PaymentTransaction


class PaymentService:
    """Bank payment gateway service with proper logging and security"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        # In production, these would come from environment variables
        self.merchant_id = "MERCHANT_PLACEHOLDER"
        self.secret_key = "SECRET_KEY_PLACEHOLDER"
        self.gateway_url = "https://payment-gateway.placeholder.com"

    async def initiate_payment(
        self,
        cart_ids: List[int],
        total_amount: Decimal,
        user_id: str,
        payment_method: str = "card",
    ) -> Dict[str, Any]:
        """Initiate payment process with bank gateway"""

        # Generate unique payment reference
        payment_reference = str(uuid.uuid4())

        # Create PaymentTransaction record
        async with AsyncSessionLocal() as session:
            async with session.begin():
                new_transaction = PaymentTransaction(
                    payment_reference=payment_reference,
                    cart_ids=cart_ids,
                    amount=total_amount,
                )
                session.add(new_transaction)
                await session.flush()

                # Link relevant orders to this payment transaction
                await session.execute(
                    update(Order)
                    .where(
                        Order.id.in_(
                            select(OrderItem.order_id).where(
                                OrderItem.source_cart_id.in_(cart_ids)
                            )
                        )
                    )
                    .values(payment_transaction_id=new_transaction.id)
                )

        # Prepare payment data for bank gateway
        payment_data = {
            "merchant_id": self.merchant_id,
            "payment_reference": payment_reference,
            "amount": f"{total_amount:.2f}",
            "currency": "LKR",
            "payment_method": payment_method,
            "customer_id": user_id,
            "return_url": f"https://yourapp.com/payment/return/{payment_reference}",
            "cancel_url": f"https://yourapp.com/payment/cancel/{payment_reference}",
            "notify_url": "https://yourapp.com/api/orders/payment/callback",
            "expires_at": datetime.now() + timedelta(minutes=30),
        }

        # Generate payment URL (placeholder)
        payment_url = f"{self.gateway_url}/pay?ref={payment_reference}"

        # Create response
        payment_result = {
            "payment_reference": payment_reference,
            "status": "initiated",
            "payment_url": payment_url,
            "expires_at": payment_data["expires_at"],
            "amount": float(total_amount),
            "currency": "LKR",
            "payment_method": payment_method,
            "cart_ids": cart_ids,
            "user_id": user_id,
        }

        # Log payment initiation
        self._error_handler.logger.info(
            f"Payment initiated for carts {cart_ids} | "
            f"Reference: {payment_reference} | "
            f"Amount: LKR {total_amount} | "
            f"User: {user_id} | "
            f"Method: {payment_method}"
        )

        return payment_result

    async def process_payment_callback(
        self, callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process payment gateway callback with signature verification"""

        # Extract callback data
        payment_reference = callback_data.get("payment_reference")
        amount = callback_data.get("amount")
        status_code = callback_data.get("status_code")
        transaction_id = callback_data.get("transaction_id")
        signature = callback_data.get("signature")

        # Log callback received
        self._error_handler.logger.info(
            f"Payment callback received | "
            f"Reference: {payment_reference} | "
            f"Amount: {amount} | "
            f"Status: {status_code} | "
            f"Transaction: {transaction_id}"
        )

        # Verify callback signature (placeholder verification)
        is_valid_signature = self._verify_callback_signature(
            callback_data, str(signature) if signature is not None else ""
        )

        if not is_valid_signature:
            self._error_handler.logger.error(
                f"Invalid callback signature for payment {payment_reference}"
            )
            return {"status": "error", "message": "Invalid signature"}

        # Get payment transaction from DB
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(PaymentTransaction).filter(
                        PaymentTransaction.payment_reference == payment_reference
                    )
                )
                payment_transaction = result.scalars().first()

                if not payment_transaction:
                    self._error_handler.logger.error(
                        f"Payment transaction not found for reference {payment_reference}"
                    )
                    return {
                        "status": "error",
                        "message": "Payment transaction not found",
                    }

                # Determine payment status
                payment_status = "success" if status_code == "2" else "failed"

                # Update payment transaction status
                payment_transaction.status = payment_status
                if transaction_id:
                    payment_transaction.transaction_id = str(transaction_id)
                await session.flush()

                callback_result = {
                    "payment_reference": payment_reference,
                    "cart_ids": payment_transaction.cart_ids,
                    "status": payment_status,
                    "transaction_id": transaction_id,
                    "amount_charged": float(amount) if amount else 0.0,
                    "processed_at": datetime.now(),
                    "signature_valid": is_valid_signature,
                    "raw_callback_data": callback_data,
                }

        # Log callback processing result
        self._error_handler.logger.info(
            f"Payment callback processed | "
            f"Reference: {payment_reference} | "
            f"Status: {payment_status} | "
            f"Valid: {is_valid_signature}"
        )

        return callback_result

    def _verify_callback_signature(
        self, callback_data: Dict[str, Any], received_signature: str
    ) -> bool:
        """Verify callback signature for security (placeholder)"""

        # In production, this would verify the actual bank signature
        # Example verification logic:
        # 1. Concatenate key fields in specific order
        # 2. Generate HMAC hash with secret key
        # 3. Compare with received signature

        # For now, log the verification attempt
        self._error_handler.logger.info(
            f"Verifying callback signature for payment reference: {callback_data.get('payment_reference')} | "
            f"Signature verification: PLACEHOLDER_IMPLEMENTATION"
        )

        # Return True for development (in production, implement actual verification)
        return True

    async def verify_payment(
        self, payment_reference: str, order_id: int
    ) -> Dict[str, Any]:
        """Verify payment status with bank gateway"""

        # Log verification attempt
        self._error_handler.logger.info(
            f"Verifying payment status | "
            f"Reference: {payment_reference} | "
            f"Order: {order_id}"
        )

        # In production, this would query the bank API
        # For now, placeholder verification
        verification_result = {
            "payment_reference": payment_reference,
            "order_id": order_id,
            "status": "completed",  # Placeholder: success for development
            "verified": True,
            "amount_paid": 0.0,  # Would be actual amount from bank
            "verification_time": datetime.now(),
            "bank_reference": f"BANK_REF_{payment_reference}",
            "transaction_details": {
                "bank_transaction_id": f"BTX_{payment_reference}",
                "payment_method": "card",
                "bank_response_code": "00",  # Success code
            },
        }

        # Log verification result
        self._error_handler.logger.info(
            f"Payment verification completed | "
            f"Reference: {payment_reference} | "
            f"Status: {verification_result['status']} | "
            f"Verified: {verification_result['verified']}"
        )

        return verification_result

    async def refund_payment(
        self,
        payment_reference: str,
        refund_amount: Optional[Decimal] = None,
        reason: str = "Customer request",
    ) -> Dict[str, Any]:
        """Process payment refund through bank gateway"""

        refund_reference = f"REF_{payment_reference}_{int(datetime.now().timestamp())}"

        # Log refund initiation
        self._error_handler.logger.info(
            f"Refund initiated | "
            f"Payment Reference: {payment_reference} | "
            f"Refund Reference: {refund_reference} | "
            f"Amount: LKR {refund_amount} | "
            f"Reason: {reason}"
        )

        # In production, this would call bank refund API
        refund_result = {
            "refund_reference": refund_reference,
            "payment_reference": payment_reference,
            "status": "processed",
            "refund_amount": float(refund_amount) if refund_amount else 0.0,
            "reason": reason,
            "processed_at": datetime.now(),
            "estimated_completion": datetime.now() + timedelta(days=3),
            "bank_refund_id": f"BANK_REF_{refund_reference}",
            "refund_method": "original_payment_method",
        }

        # Log refund processing
        self._error_handler.logger.info(
            f"Refund processed | "
            f"Refund Reference: {refund_reference} | "
            f"Status: {refund_result['status']} | "
            f"Amount: LKR {refund_amount}"
        )

        return refund_result

    def get_supported_payment_methods(self) -> List[Dict[str, Any]]:
        """Get list of supported payment methods (placeholder)"""

        return [
            {
                "method": "card",
                "name": "Credit/Debit Card",
                "supported_cards": ["visa", "mastercard", "amex"],
                "enabled": True,
            },
            {"method": "paypal", "name": "PayPal", "enabled": True},
            {"method": "apple_pay", "name": "Apple Pay", "enabled": True},
            {"method": "google_pay", "name": "Google Pay", "enabled": True},
            {
                "method": "bank_transfer",
                "name": "Bank Transfer",
                "enabled": False,  # Coming soon
            },
        ]
