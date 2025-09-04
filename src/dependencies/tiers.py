from typing import Optional
from fastapi import Depends
from src.api.auth.models import DecodedToken
from src.config.constants import CustomerTier
from src.dependencies.auth import get_optional_user
from src.api.tiers.service import TierService


async def get_user_tier(
    current_user: Optional[DecodedToken] = Depends(get_optional_user),
) -> Optional[CustomerTier]:
    """
    Extract customer tier from user database record.
    Returns CustomerTier if user is authenticated and has tier information,
    otherwise returns None for default/guest pricing.
    """
    if not current_user:
        return None

    try:
        tier_service = TierService()
        user_tier = await tier_service.get_user_tier(current_user.uid)
        return user_tier
    except Exception:
        # If there's any error fetching user data, return None for default pricing
        pass

    return None
