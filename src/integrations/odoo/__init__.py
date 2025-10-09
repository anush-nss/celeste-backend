"""
Odoo ERP Integration Module

Provides integration with Odoo ERP system for order management,
inventory synchronization, and product data.
"""

from src.integrations.odoo.exceptions import (
    OdooAuthenticationError,
    OdooConnectionError,
    OdooSyncError,
)
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
from src.integrations.odoo.service import OdooService

__all__ = [
    # Service
    "OdooService",
    # Exceptions
    "OdooAuthenticationError",
    "OdooConnectionError",
    "OdooSyncError",
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
