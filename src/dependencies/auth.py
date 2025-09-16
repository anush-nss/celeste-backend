from fastapi import Depends, Security, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.dependencies.firebase import auth
from typing import Annotated, List, Optional
from src.shared.database import get_firebase_auth
from src.shared.exceptions import UnauthorizedException, ForbiddenException
from src.config.constants import UserRole
from src.api.auth.models import DecodedToken

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> DecodedToken:
    if not credentials or not credentials.credentials:
        raise UnauthorizedException(detail="Authentication token is missing")

    token = credentials.credentials
    try:
        decoded_token_dict = auth.verify_id_token(token)
        return DecodedToken(**decoded_token_dict)
    except Exception as e:
        raise UnauthorizedException(detail=f"Invalid authentication credentials: {e}")


async def get_current_user(
    decoded_token: Annotated[DecodedToken, Depends(verify_token)],
):
    return decoded_token


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security),
) -> Optional[DecodedToken]:
    """
    Extract user information from Bearer token if provided.
    Returns None if no token or invalid token (silent failure).
    Used for optional authentication in public endpoints.
    """
    if not credentials or not credentials.credentials:
        return None

    try:
        decoded_token_dict = auth.verify_id_token(credentials.credentials)
        return DecodedToken(**decoded_token_dict)
    except Exception:
        # Silently fail for optional authentication
        return None


# Tier functionality has been moved to src/dependencies/tiers.py
# Import get_user_tier from there if needed


class RoleChecker:
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        request: Request,
        current_user: Annotated[DecodedToken, Depends(get_current_user)],
    ):
        user_role = current_user.role
        if user_role not in self.allowed_roles:
            raise ForbiddenException(
                "You do not have permission to perform this action."
            )
        return current_user
