"""
Odoo ERP Integration Service

Provides integration with Odoo ERP system using XML-RPC API.
Handles authentication, CRUD operations, and error handling.
"""

import xmlrpc.client
from typing import Any, Dict, List, Optional

from src.config.settings import settings
from src.integrations.odoo.exceptions import (
    OdooAuthenticationError,
    OdooConnectionError,
)
from src.shared.error_handler import ErrorHandler


class OdooService:
    """
    Odoo ERP integration service using XML-RPC

    Provides methods to:
    - Authenticate with Odoo
    - Execute CRUD operations on Odoo models
    - Test connection
    - Read products and other entities
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

        # Load configuration from environment variables
        self.url = settings.ODOO_URL
        self.db = settings.ODOO_DB
        self.username = settings.ODOO_USERNAME
        self.password = settings.ODOO_PASSWORD

        # Validate required configuration
        if not self.url:
            raise ValueError("ODOO_URL environment variable is required")
        if not self.db:
            raise ValueError("ODOO_DB environment variable is required")
        if not self.username:
            raise ValueError("ODOO_USERNAME environment variable is required")
        if not self.password:
            raise ValueError("ODOO_PASSWORD environment variable is required")

        # API endpoints
        self.common_endpoint = f"{self.url}/xmlrpc/2/common"
        self.object_endpoint = f"{self.url}/xmlrpc/2/object"

        # Connection objects (lazy initialized)
        self._common = None
        self._models = None
        self._uid = None

        self._error_handler.logger.info(
            f"OdooService initialized | URL: {self.url} | DB: {self.db}"
        )

    def _get_common_proxy(self) -> xmlrpc.client.ServerProxy:
        """Get or create common API proxy"""
        if self._common is None:
            try:
                self._common = xmlrpc.client.ServerProxy(self.common_endpoint)
                self._error_handler.logger.debug("Common proxy created")
            except Exception as e:
                self._error_handler.logger.error(f"Failed to create common proxy: {e}")
                raise OdooConnectionError("Failed to connect to Odoo", e)
        return self._common

    def _get_models_proxy(self) -> xmlrpc.client.ServerProxy:
        """Get or create models API proxy"""
        if self._models is None:
            try:
                self._models = xmlrpc.client.ServerProxy(self.object_endpoint)
                self._error_handler.logger.debug("Models proxy created")
            except Exception as e:
                self._error_handler.logger.error(f"Failed to create models proxy: {e}")
                raise OdooConnectionError(f"Failed to connect to Odoo models: {e}")
        return self._models

    def authenticate(self) -> int:
        """
        Authenticate with Odoo and get user ID

        Returns:
            int: User ID (uid) if authentication successful

        Raises:
            OdooAuthenticationError: If authentication fails
            OdooConnectionError: If connection fails
        """
        try:
            common = self._get_common_proxy()

            # Get Odoo version info
            version_info = common.version()
            server_version = (
                version_info["server_version"]
                if isinstance(version_info, dict) and "server_version" in version_info
                else str(version_info)
            )
            self._error_handler.logger.info(
                f"Connected to Odoo | Version: {server_version}"
            )
            # Authenticate and get UID
            uid = common.authenticate(self.db, self.username, self.password, {})

            if not isinstance(uid, int) or uid <= 0:
                raise OdooAuthenticationError(
                    "Authentication failed - Invalid credentials"
                )

            self._uid = uid
            self._error_handler.logger.info(
                f"Authentication successful | UID: {uid} | User: {self.username}"
            )

            return int(uid)
            return uid

        except OdooAuthenticationError:
            raise
        except Exception as e:
            self._error_handler.logger.error(f"Authentication error: {e}")
            raise OdooConnectionError(f"Failed to authenticate with Odoo: {e}")

    def execute_kw(
        self,
        model: str,
        method: str,
        args: List[Any],
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a method on an Odoo model

        Args:
            model: Odoo model name (e.g., 'product.product', 'res.partner')
            method: Method to execute (e.g., 'search_read', 'create', 'write')
            args: Positional arguments for the method
            kwargs: Keyword arguments for the method

        Returns:
            Any: Result from Odoo API

        Raises:
            OdooAuthenticationError: If not authenticated
            OdooConnectionError: If execution fails
        """
        if self._uid is None:
            raise OdooAuthenticationError(
                "Not authenticated - call authenticate() first"
            )

        try:
            models = self._get_models_proxy()
            kwargs = kwargs or {}

            self._error_handler.logger.debug(
                f"Executing: {model}.{method} | Args: {args} | Kwargs: {kwargs}"
            )

            result = models.execute_kw(
                self.db, self._uid, self.password, model, method, args, kwargs
            )

            self._error_handler.logger.debug(
                f"Execution successful | Result type: {type(result)}"
            )

            return result

        except Exception as e:
            self._error_handler.logger.error(
                f"Execution failed | Model: {model} | Method: {method} | Error: {e}"
            )
            raise OdooConnectionError(f"Failed to execute {model}.{method}: {e}")

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Odoo and return server info

        Returns:
            Dict containing connection status and server info
        """
        try:
            # Get version info
            common = self._get_common_proxy()
            version_info = common.version()

            # Try to authenticate
            uid = self.authenticate()

            # Get current user info
            user_info = self.execute_kw(
                "res.users",
                "read",
                [[uid]],
                {"fields": ["name", "login", "company_id"]},
            )
            server_version = (
                version_info["server_version"]
                if isinstance(version_info, dict) and "server_version" in version_info
                else str(version_info)
            )
            protocol_version = (
                version_info["protocol_version"]
                if isinstance(version_info, dict) and "protocol_version" in version_info
                else None
            )
            result = {
                "status": "success",
                "connected": True,
                "authenticated": True,
                "server_version": server_version,
                "protocol_version": protocol_version,
                "uid": uid,
                "user_info": user_info[0] if user_info else None,
                "database": self.db,
                "url": self.url,
            }

            self._error_handler.logger.info("Connection test successful")
            return result

        except Exception as e:
            error_result = {
                "status": "error",
                "connected": False,
                "authenticated": False,
                "error": str(e),
                "database": self.db,
                "url": self.url,
            }

            self._error_handler.logger.error(f"Connection test failed: {e}")
            return error_result

    def read_product(
        self, product_id: Optional[int] = None, limit: int = 1
    ) -> Dict[str, Any]:
        """
        Read product(s) from Odoo for testing

        Args:
            product_id: Specific product ID to read, or None to read first product
            limit: Number of products to read if product_id is None

        Returns:
            Dict containing product data and metadata
        """
        try:
            # Ensure authenticated
            if self._uid is None:
                self.authenticate()

            if product_id:
                # Read specific product
                products = self.execute_kw(
                    "product.product",
                    "read",
                    [[product_id]],
                    {
                        "fields": [
                            "id",
                            "name",
                            "default_code",
                            "list_price",
                            "standard_price",
                            "qty_available",
                        ]
                    },
                )
            else:
                # Search and read first product(s)
                products = self.execute_kw(
                    "product.product",
                    "search_read",
                    [[]],
                    {
                        "fields": [
                            "id",
                            "name",
                            "default_code",
                            "list_price",
                            "standard_price",
                            "qty_available",
                        ],
                        "limit": limit,
                    },
                )

            result = {
                "status": "success",
                "count": len(products),
                "products": products,
            }

            self._error_handler.logger.info(
                f"Product read successful | Count: {len(products)}"
            )
            return result

        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "count": 0,
                "products": [],
            }

            self._error_handler.logger.error(f"Product read failed: {e}")
            return error_result

    def create_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a customer (partner) in Odoo for testing

        Args:
            customer_data: Dictionary with customer information
                Required: name
                Optional: email, phone, mobile, street, city, zip, country_id, state_id, vat, comment

        Returns:
            Dict containing created customer ID and data
        """
        try:
            # Ensure authenticated
            if self._uid is None:
                self.authenticate()

            # Prepare customer values (remove None values)
            values = {k: v for k, v in customer_data.items() if v is not None}

            # Create customer in Odoo (res.partner model)
            customer_id = self.execute_kw(
                "res.partner",
                "create",
                [values],
            )

            # Read back the created customer to get full data
            customer_record = self.execute_kw(
                "res.partner",
                "read",
                [[customer_id]],
                {
                    "fields": [
                        "id",
                        "name",
                        "email",
                        "phone",
                        "mobile",
                        "street",
                        "street2",
                        "city",
                        "zip",
                        "country_id",
                        "state_id",
                        "vat",
                        "comment",
                    ]
                },
            )

            result = {
                "status": "success",
                "customer_id": customer_id,
                "customer_data": customer_record[0] if customer_record else None,
            }

            self._error_handler.logger.info(
                f"Customer created successfully | ID: {customer_id} | Name: {values.get('name')}"
            )
            return result

        except Exception as e:
            error_result = {
                "status": "error",
                "customer_id": None,
                "customer_data": None,
                "error": str(e),
            }

            self._error_handler.logger.error(f"Customer creation failed: {e}")
            return error_result

    def search(self, model: str, domain: List[Any], limit: int = 100) -> List[int]:
        """
        Search for records in Odoo model

        Args:
            model: Odoo model name
            domain: Search domain (Odoo domain format)
            limit: Maximum number of records to return

        Returns:
            List of record IDs
        """
        if self._uid is None:
            self.authenticate()

        return self.execute_kw(model, "search", [domain], {"limit": limit})

    def read(
        self, model: str, ids: List[int], fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Read records from Odoo model

        Args:
            model: Odoo model name
            ids: List of record IDs to read
            fields: List of fields to retrieve (None = all fields)

        Returns:
            List of record dictionaries
        """
        if self._uid is None:
            self.authenticate()

        kwargs = {"fields": fields} if fields else {}
        return self.execute_kw(model, "read", [ids], kwargs)

    def search_read(
        self,
        model: str,
        domain: List[Any],
        fields: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search and read records in one call

        Args:
            model: Odoo model name
            domain: Search domain
            fields: List of fields to retrieve
            limit: Maximum number of records

        Returns:
            List of record dictionaries
        """
        kwargs = {"limit": limit}
        if fields is not None:
            kwargs["fields"] = fields  # type: ignore

        return self.execute_kw(model, "search_read", [domain], kwargs)

    def create(self, model: str, values: Dict[str, Any]) -> int:
        """
        Create a new record in Odoo

        Args:
            model: Odoo model name
            values: Dictionary of field values

        Returns:
            ID of created record
        """
        if self._uid is None:
            self.authenticate()

        record_id = self.execute_kw(model, "create", [values])
        self._error_handler.logger.info(
            f"Record created | Model: {model} | ID: {record_id}"
        )
        return record_id

    def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> bool:
        """
        Update existing records in Odoo

        Args:
            model: Odoo model name
            ids: List of record IDs to update
            values: Dictionary of field values to update

        Returns:
            True if successful
        """
        if self._uid is None:
            self.authenticate()

        result = self.execute_kw(model, "write", [ids, values])
        self._error_handler.logger.info(
            f"Records updated | Model: {model} | IDs: {ids} | Success: {result}"
        )
        return result

    def unlink(self, model: str, ids: List[int]) -> bool:
        """
        Delete records from Odoo

        Args:
            model: Odoo model name
            ids: List of record IDs to delete

        Returns:
            True if successful
        """
        if self._uid is None:
            self.authenticate()

        result = self.execute_kw(model, "unlink", [ids])
        self._error_handler.logger.warning(
            f"Records deleted | Model: {model} | IDs: {ids} | Success: {result}"
        )
        return result
