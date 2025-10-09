"""
Odoo Integration Models

Pydantic schemas for Odoo API requests and responses
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OdooCustomerData(BaseModel):
    """Customer data for creation in Odoo"""

    name: str = Field(..., description="Customer name (required)")
    email: Optional[str] = Field(None, description="Customer email")
    phone: Optional[str] = Field(None, description="Customer phone number")
    mobile: Optional[str] = Field(None, description="Customer mobile number")
    street: Optional[str] = Field(None, description="Street address")
    street2: Optional[str] = Field(None, description="Street address line 2")
    city: Optional[str] = Field(None, description="City")
    zip: Optional[str] = Field(None, description="ZIP/Postal code")
    country_id: Optional[int] = Field(None, description="Country ID in Odoo")
    state_id: Optional[int] = Field(None, description="State/Province ID in Odoo")
    vat: Optional[str] = Field(None, description="Tax ID / VAT number")
    comment: Optional[str] = Field(None, description="Internal notes")


class OdooTestRequest(BaseModel):
    """Request schema for Odoo connection test"""

    test_type: str = Field(
        "connection",
        description="Type of test to run: 'connection', 'product', or 'customer'",
    )
    product_id: Optional[int] = Field(
        None,
        description="Optional product ID to read (for product test)",
    )
    limit: int = Field(
        1,
        description="Number of products to read (for product test without ID)",
        ge=1,
        le=100,
    )
    customer_data: Optional[OdooCustomerData] = Field(
        None,
        description="Customer data for creation (for customer test)",
    )


class OdooConnectionResponse(BaseModel):
    """Response schema for Odoo connection test"""

    status: str = Field(..., description="Connection status: 'success' or 'error'")
    connected: bool = Field(..., description="Whether connection was established")
    authenticated: bool = Field(..., description="Whether authentication succeeded")
    server_version: Optional[str] = Field(None, description="Odoo server version")
    protocol_version: Optional[int] = Field(
        None, description="XML-RPC protocol version"
    )
    uid: Optional[int] = Field(None, description="Authenticated user ID")
    user_info: Optional[Dict[str, Any]] = Field(None, description="User information")
    database: str = Field(..., description="Database name")
    url: str = Field(..., description="Odoo server URL")
    error: Optional[str] = Field(None, description="Error message if failed")


class OdooProductResponse(BaseModel):
    """Response schema for Odoo product read test"""

    status: str = Field(..., description="Status: 'success' or 'error'")
    count: int = Field(..., description="Number of products returned")
    products: List[Dict[str, Any]] = Field(..., description="Product data")
    error: Optional[str] = Field(None, description="Error message if failed")


class OdooCustomerResponse(BaseModel):
    """Response schema for Odoo customer creation test"""

    status: str = Field(..., description="Status: 'success' or 'error'")
    customer_id: Optional[int] = Field(None, description="Created customer ID in Odoo")
    customer_data: Optional[Dict[str, Any]] = Field(
        None, description="Customer data returned from Odoo"
    )
    error: Optional[str] = Field(None, description="Error message if failed")


class OdooTestResponse(BaseModel):
    """Combined response schema for Odoo test endpoint"""

    test_type: str = Field(..., description="Type of test executed")
    connection: Optional[OdooConnectionResponse] = Field(
        None, description="Connection test results"
    )
    products: Optional[OdooProductResponse] = Field(
        None, description="Product read test results"
    )
    customer: Optional[OdooCustomerResponse] = Field(
        None, description="Customer creation test results"
    )
    timestamp: str = Field(..., description="Test execution timestamp")
    success: bool = Field(..., description="Overall test success status")


class OdooSearchRequest(BaseModel):
    """Request schema for generic Odoo search"""

    model: str = Field(..., description="Odoo model name (e.g., 'product.product')")
    domain: List[Any] = Field(
        default_factory=list,
        description="Search domain in Odoo format",
    )
    fields: Optional[List[str]] = Field(
        None,
        description="Fields to retrieve (None = all fields)",
    )
    limit: int = Field(
        100,
        description="Maximum number of records to return",
        ge=1,
        le=1000,
    )


class OdooCreateRequest(BaseModel):
    """Request schema for creating Odoo record"""

    model: str = Field(..., description="Odoo model name")
    values: Dict[str, Any] = Field(..., description="Field values for new record")


class OdooUpdateRequest(BaseModel):
    """Request schema for updating Odoo records"""

    model: str = Field(..., description="Odoo model name")
    ids: List[int] = Field(..., description="Record IDs to update")
    values: Dict[str, Any] = Field(..., description="Field values to update")


class OdooDeleteRequest(BaseModel):
    """Request schema for deleting Odoo records"""

    model: str = Field(..., description="Odoo model name")
    ids: List[int] = Field(..., description="Record IDs to delete")
