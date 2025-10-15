"""
Dependencies related to application environment.
"""

from fastapi import Depends, HTTPException, status

from src.config.settings import settings

def dev_mode_only():
    """Dependency that raises a 404 error if the app is not in development mode."""
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )
