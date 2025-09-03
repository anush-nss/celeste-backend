from fastapi import Depends, Security, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from typing import Annotated, List, Optional
from src.core.firebase import get_firebase_auth
from src.core.exceptions import UnauthorizedException, ForbiddenException
from src.shared.constants import UserRole, CustomerTier
from src.models.token_models import DecodedToken

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

async def get_current_user(decoded_token: Annotated[DecodedToken, Depends(verify_token)]):
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

async def get_user_tier(
    current_user: Optional[DecodedToken] = Depends(get_optional_user)
) -> Optional[CustomerTier]:
    """
    Extract customer tier from user database record.
    Returns CustomerTier if user is authenticated and has tier information,
    otherwise returns None for default/guest pricing.
    """
    if not current_user:
        return None
    
    # Get user's tier from the users table in Firestore
    try:
        from src.services.user_service import UserService
        user_service = UserService()
        user = await user_service.get_user_by_id(current_user.uid)
        
        if user and user.customer_tier:
            return user.customer_tier
    except Exception:
        # If there's any error fetching user data, continue with fallback
        pass
    
    # Placeholder logic - replace with actual user service integration
    tier_mapping = {
        'bronze': CustomerTier.BRONZE,
        'silver': CustomerTier.SILVER, 
        'gold': CustomerTier.GOLD,
        'platinum': CustomerTier.PLATINUM
    }
    
    # Check if tier is in custom claims (fallback)
    user_tier = getattr(current_user, 'customer_tier', None)
    if user_tier and user_tier.lower() in tier_mapping:
        return tier_mapping[user_tier.lower()]
    
    # Default to Bronze for authenticated users
    return None

class RoleChecker:
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    async def __call__(self, request: Request, current_user: Annotated[DecodedToken, Depends(get_current_user)]):
        user_role = current_user.role
        if user_role not in self.allowed_roles:
            raise ForbiddenException("You do not have permission to perform this action.")
        return current_user