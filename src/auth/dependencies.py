from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth
from typing import Annotated, List
from src.core.firebase import get_firebase_auth
from src.core.exceptions import UnauthorizedException, ForbiddenException
from src.shared.constants import UserRole
from src.models.token_models import DecodedToken

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/verify")

async def verify_token(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        decoded_token_dict = get_firebase_auth().verify_id_token(token)
        decoded_token = DecodedToken(**decoded_token_dict)
        return decoded_token
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