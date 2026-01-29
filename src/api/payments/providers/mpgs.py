import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional
import httpx
from src.api.payments.providers.base import BasePaymentProvider
from src.config.settings import settings
from src.shared.error_handler import ErrorHandler


class MPGSProvider(BasePaymentProvider):
    """
    Mastercard MPGS Payment Provider implementation.
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.merchant_id = settings.MPGS_MERCHANT_ID
        self.api_username = settings.MPGS_API_USERNAME or f"merchant.{self.merchant_id}"
        self.api_password = settings.MPGS_API_PASSWORD
        self.gateway_url = settings.MPGS_GATEWAY_URL

    async def initiate_checkout(
        self,
        amount: Decimal,
        currency: str,
        reference: str,
        return_url: str,
        source_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        endpoint = f"{self.gateway_url}/merchant/{self.merchant_id}/session"

        payload = {
            "apiOperation": "INITIATE_CHECKOUT",
            "order": {
                "id": reference,
                "amount": "{:.2f}".format(
                    amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ),
                "currency": currency,
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
                "returnUrl": return_url,
            },
        }

        if source_token:
            payload["sourceOfFunds"] = {"type": "CARD", "token": source_token}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                json=payload,
                auth=(str(self.api_username), str(self.api_password)),
            )
            response.raise_for_status()
            data = response.json()

            return {
                "session_id": data.get("session", {}).get("id"),
                "success_indicator": data.get("successIndicator"),
                "merchant_id": self.merchant_id,
            }

    async def verify_transaction(self, reference: str, **kwargs) -> Dict[str, Any]:
        endpoint = f"{self.gateway_url}/merchant/{self.merchant_id}/order/{reference}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                endpoint, auth=(str(self.api_username), str(self.api_password))
            )
            response.raise_for_status()
            return response.json()

    async def handle_webhook(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        # Logic to verify webhook secret could also go here
        return payload

    async def tokenize_from_session(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """
        Calls the MPGS 'Create or Update Token' API using a session.
        Uses a random UUID as the tokenId if not provided.
        """
        token_id = kwargs.get("token_id") or f"TOK{uuid.uuid4().hex[:12].upper()}"
        endpoint = f"{self.gateway_url}/merchant/{self.merchant_id}/token/{token_id}"

        payload = {
            "apiOperation": "TOKENIZE",
            "session": {"id": session_id},
            "sourceOfFunds": {"type": "CARD"},
        }

        async with httpx.AsyncClient() as client:
            self._error_handler.logger.info(f"Calling Token API at {endpoint} with session {session_id}")
            response = await client.put(
                endpoint,
                json=payload,
                auth=(str(self.api_username), str(self.api_password)),
            )
            self._error_handler.logger.info(f"Token API response: {response.status_code} - {response.text}")
            
            if response.status_code not in [200, 201]:
                self._error_handler.logger.error(
                    f"Tokenization failed: {response.text}"
                )
                return {}

            data = response.json()
            # Ensure the token_id is included in the response for our service to use
            if "token" not in data:
                data["token"] = token_id
            return data

    async def initiate_add_card(
        self, reference: str, return_url: str
    ) -> Dict[str, Any]:
        """
        Initiate a session for adding a card (operation=NONE).
        """
        endpoint = f"{self.gateway_url}/merchant/{self.merchant_id}/session"

        payload = {
            "apiOperation": "INITIATE_CHECKOUT",
            "order": {
                "id": reference,
                "amount": "1.00",
                "currency": "LKR",
                "description": "Card Setup",
            },
            "interaction": {
                "operation": "NONE",
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
                "returnUrl": return_url,
            },
        }

        async with httpx.AsyncClient() as client:
            try:
                self._error_handler.logger.info(f"Initiating Add Card session with payload: {payload}")
                response = await client.post(
                    endpoint,
                    json=payload,
                    auth=(str(self.api_username), str(self.api_password)),
                )
                if response.status_code != 201:
                    self._error_handler.logger.error(f"MPGS Session Initiation Failed: {response.status_code} - {response.text}")
                response.raise_for_status()
                data = response.json()

                return {
                    "session_id": data.get("session", {}).get("id"),
                    "success_indicator": data.get("successIndicator"),
                    "merchant_id": self.merchant_id,
                }
            except httpx.HTTPStatusError as e:
                self._error_handler.logger.error(
                    f"MPGS Add Card Initiation Error: {e.response.text}"
                )
                raise
