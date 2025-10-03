from typing import Optional

from fastapi import Depends

from src.api.auth.models import DecodedToken
from src.api.tiers.service import TierService
from src.dependencies.auth import get_optional_user


async def get_user_tier(
    current_user: Optional[DecodedToken] = Depends(get_optional_user),
) -> Optional[int]:
    """
    Extract customer tier ID from user database record.
    Returns tier ID if user is authenticated and has tier information,
    otherwise returns None for default/guest pricing.
    """
    if not current_user:
        return None

    try:
        tier_service = TierService()
        user_tier_id = await tier_service.get_user_tier_id(current_user.uid)
        return user_tier_id
    except Exception:
        # If there's any error fetching user data, return None for default pricing
        pass

    return None
