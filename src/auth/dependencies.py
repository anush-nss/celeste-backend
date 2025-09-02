from fastapi import Depends, Security, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from typing import Annotated, List, Optional
from src.core.firebase import get_firebase_auth
from src.core.exceptions import UnauthorizedException, ForbiddenException
from src.shared.constants import UserRole
from src.models.token_models import DecodedToken

security = HTTPBearer()

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

async def get_current_user(decoded_token: Annotated[DecodedToken, Depends(verify_token)]):
    return decoded_token

class RoleChecker:
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    async def __call__(self, request: Request, current_user: Annotated[DecodedToken, Depends(get_current_user)]):
        user_role = current_user.role
        if user_role not in self.allowed_roles:
            raise ForbiddenException("You do not have permission to perform this action.")
        return current_user