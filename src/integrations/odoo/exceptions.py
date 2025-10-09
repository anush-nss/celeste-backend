"""
Odoo Integration Exceptions

Custom exception classes for Odoo ERP integration errors.
"""

from typing import Optional


class OdooConnectionError(Exception):
    """Raised when connection to Odoo fails"""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self):
        if self.original_error:
            return f"{self.message} | Original error: {str(self.original_error)}"
        return self.message


class OdooAuthenticationError(Exception):
    """Raised when authentication with Odoo fails"""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self):
        if self.original_error:
            return f"{self.message} | Original error: {str(self.original_error)}"
        return self.message


class OdooSyncError(Exception):
    """Raised when order sync to Odoo fails"""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self):
        if self.original_error:
            return f"{self.message} | Original error: {str(self.original_error)}"
        return self.message
