from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from decimal import Decimal


class BasePaymentProvider(ABC):
    """
    Abstract Base Class for all Payment Providers.
    Ensures a consistent interface for the PaymentService.
    """

    @abstractmethod
    async def initiate_checkout(
        self,
        amount: Decimal,
        currency: str,
        reference: str,
        return_url: str,
        save_card: bool = False,
        source_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Initiate a payment session/checkout."""
        pass

    @abstractmethod
    async def verify_transaction(self, reference: str, **kwargs) -> Dict[str, Any]:
        """Verify the status of a transaction with the gateway."""
        pass

    @abstractmethod
    async def handle_webhook(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Process an incoming webhook notification."""
        pass

    @abstractmethod
    async def tokenize_from_session(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """Create a permanent token from a payment session."""
        pass

    @abstractmethod
    async def initiate_add_card(
        self, reference: str, return_url: str
    ) -> Dict[str, Any]:
        """Initiate a session specifically for adding/saving a card without a purchase."""
        pass
