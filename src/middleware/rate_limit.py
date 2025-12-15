from typing import Optional

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config.settings import settings


def get_ip_key(request: Request) -> Optional[str]:
    """
    Custom key function for rate limiting.
    Returns the IP address to rate limit by.
    Returns None if the IP is exempt (bypassing rate limits).
    """
    # Check for exempt IPs
    remote_addr = get_remote_address(request)
    
    # Bypass if in development mode
    if settings.ENVIRONMENT == "development":
        return None

    if remote_addr and remote_addr in settings.RATE_LIMIT_EXEMPT_IPS:
        return None  # Return None to skip rate limiting
            
    return remote_addr


# Initialize limiter with our custom key function
# default_limits can be overridden per route
limiter = Limiter(
    key_func=get_ip_key,  # type: ignore
    default_limits=["100/minute"] # Default "minimum effort" global limit
)
