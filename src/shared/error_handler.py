"""
Centralized error handling utilities for consistent error management across services.
"""
import logging
import inspect
from typing import Optional, Any, Dict
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DatabaseError
from src.shared.exceptions import (
    ResourceNotFoundException,
    ConflictException,
    UnauthorizedException,
    ForbiddenException
)
from src.shared.utils import get_logger


class ServiceError(Exception):
    """Base service error with context"""
    def __init__(self, message: str, original_error: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.original_error = original_error
        self.context = context or {}
        super().__init__(self.message)


class ErrorHandler:
    """Centralized error handler for services"""

    def __init__(self, logger_name: str):
        self.logger = get_logger(logger_name)

    def handle_database_error(self, error: Exception, operation: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Handle database-related errors with proper logging and exceptions"""
        context = context or {}

        if isinstance(error, IntegrityError):
            error_msg = str(error.orig) if hasattr(error, 'orig') else str(error)
            self.logger.error(f"Database integrity error during {operation}: {error_msg}", extra=context)

            # Check for common integrity constraint violations
            if "foreign key constraint" in error_msg.lower():
                raise ResourceNotFoundException(detail=f"Referenced resource not found for {operation}")
            elif "unique constraint" in error_msg.lower() or "duplicate key" in error_msg.lower():
                raise ConflictException(detail=f"Resource already exists for {operation}")
            else:
                raise ServiceError(f"Data integrity error during {operation}", error, context)

        elif isinstance(error, DatabaseError):
            self.logger.error(f"Database error during {operation}: {str(error)}", extra=context)
            raise ServiceError(f"Database operation failed for {operation}", error, context)

        elif isinstance(error, SQLAlchemyError):
            self.logger.error(f"SQLAlchemy error during {operation}: {str(error)}", extra=context)
            raise ServiceError(f"Database operation failed for {operation}", error, context)

        else:
            # Not a database error, re-raise as is
            raise error

    def handle_firebase_error(self, error: Exception, operation: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Handle Firebase-related errors"""
        context = context or {}
        error_type = type(error).__name__

        # Use string matching since Firebase error classes may vary
        if "UserNotFoundError" in error_type:
            self.logger.warning(f"Firebase user not found during {operation}", extra=context)
            raise ResourceNotFoundException(detail="User not found")

        elif "InvalidIdTokenError" in error_type or "InvalidTokenError" in error_type:
            self.logger.warning(f"Invalid Firebase token during {operation}", extra=context)
            raise UnauthorizedException(detail="Invalid authentication token")

        elif "ExpiredIdTokenError" in error_type or "ExpiredTokenError" in error_type:
            self.logger.warning(f"Expired Firebase token during {operation}", extra=context)
            raise UnauthorizedException(detail="Authentication token expired")

        elif "RevokedIdTokenError" in error_type or "RevokedTokenError" in error_type:
            self.logger.warning(f"Revoked Firebase token during {operation}", extra=context)
            raise UnauthorizedException(detail="Authentication token revoked")

        else:
            self.logger.error(f"Firebase error during {operation}: {str(error)}", extra=context)
            raise ServiceError(f"Authentication service error during {operation}", error, context)

    def handle_general_error(self, error: Exception, operation: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Handle general errors with proper logging"""
        context = context or {}

        if isinstance(error, (ResourceNotFoundException, ConflictException, UnauthorizedException, ForbiddenException)):
            # Already a proper HTTP exception, just log and re-raise
            self.logger.info(f"Known error during {operation}: {error.detail}", extra=context)
            raise error

        elif isinstance(error, ServiceError):
            # Already a service error, log and convert to appropriate HTTP exception
            self.logger.error(f"Service error during {operation}: {error.message}", extra=context)
            raise ServiceError(error.message, error.original_error, error.context)

        else:
            # Unknown error, log with full context
            self.logger.error(f"Unexpected error during {operation}: {str(error)}",
                            extra=context, exc_info=True)
            raise ServiceError(f"Unexpected error during {operation}", error, context)

    def log_success(self, operation: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log successful operations"""
        context = context or {}
        self.logger.info(f"Successfully completed {operation}", extra=context)


def handle_service_errors(operation: str):
    """Decorator for handling service method errors"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            error_handler = getattr(self, '_error_handler', None)
            if not error_handler:
                # Fallback to basic logging if no error handler
                logger = get_logger(self.__class__.__name__)
                error_handler = ErrorHandler(self.__class__.__name__)

            try:
                result = await func(self, *args, **kwargs)
                error_handler.log_success(operation, {"function_args": str(args)[:100], "function_kwargs": str(kwargs)[:100]})
                return result
            except Exception as e:
                context = {
                    "method": func.__name__,
                    "function_args": str(args)[:100],
                    "function_kwargs": str(kwargs)[:100]
                }

                # Handle different error types
                # Let HTTPException (business logic exceptions) pass through
                from fastapi import HTTPException
                if isinstance(e, HTTPException):
                    raise e
                elif isinstance(e, (IntegrityError, DatabaseError, SQLAlchemyError)):
                    error_handler.handle_database_error(e, operation, context)
                elif "firebase" in str(type(e)).lower() or "auth" in str(type(e)).lower():
                    error_handler.handle_firebase_error(e, operation, context)
                else:
                    error_handler.handle_general_error(e, operation, context)

        @wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            error_handler = getattr(self, '_error_handler', None)
            if not error_handler:
                error_handler = ErrorHandler(self.__class__.__name__)

            try:
                result = func(self, *args, **kwargs)
                error_handler.log_success(operation, {"function_args": str(args)[:100], "function_kwargs": str(kwargs)[:100]})
                return result
            except Exception as e:
                context = {
                    "method": func.__name__,
                    "function_args": str(args)[:100],
                    "function_kwargs": str(kwargs)[:100]
                }

                # Handle different error types
                # Let HTTPException (business logic exceptions) pass through
                from fastapi import HTTPException
                if isinstance(e, HTTPException):
                    raise e
                elif isinstance(e, (IntegrityError, DatabaseError, SQLAlchemyError)):
                    error_handler.handle_database_error(e, operation, context)
                elif "firebase" in str(type(e)).lower() or "auth" in str(type(e)).lower():
                    error_handler.handle_firebase_error(e, operation, context)
                else:
                    error_handler.handle_general_error(e, operation, context)

        # Return appropriate wrapper based on whether function is async
        return async_wrapper if hasattr(func, '__code__') and func.__code__.co_flags & 0x80 else sync_wrapper

    return decorator