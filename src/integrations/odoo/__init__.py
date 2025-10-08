"""
Odoo ERP Integration Module

Provides integration with Odoo ERP system for order management,
inventory synchronization, and product data.
"""

from src.integrations.odoo.models import (
    OdooConnectionResponse,
    OdooCreateRequest,
    OdooCustomerData,
    OdooCustomerResponse,
    OdooDeleteRequest,
    OdooProductResponse,
    OdooSearchRequest,
    OdooTestRequest,
    OdooTestResponse,
    OdooUpdateRequest,
)
from src.integrations.odoo.service import (
    OdooAuthenticationError,
    OdooConnectionError,
    OdooService,
)

__all__ = [
    # Service
    "OdooService",
    "OdooAuthenticationError",
    "OdooConnectionError",
    # Models
    "OdooTestRequest",
    "OdooTestResponse",
    "OdooConnectionResponse",
    "OdooProductResponse",
    "OdooCustomerData",
    "OdooCustomerResponse",
    "OdooSearchRequest",
    "OdooCreateRequest",
    "OdooUpdateRequest",
    "OdooDeleteRequest",
]
