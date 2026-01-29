from typing import Dict
from src.api.payments.providers.base import BasePaymentProvider
from src.api.payments.providers.mpgs import MPGSProvider


class PaymentFactory:
    _providers: Dict[str, BasePaymentProvider] = {}

    @classmethod
    def get_provider(cls, provider_id: str = "mastercard_mpgs") -> BasePaymentProvider:
        if provider_id not in cls._providers:
            if provider_id == "mastercard_mpgs":
                cls._providers[provider_id] = MPGSProvider()
            else:
                raise ValueError(f"Unknown payment provider: {provider_id}")

        return cls._providers[provider_id]
