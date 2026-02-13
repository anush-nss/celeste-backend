from fastapi import APIRouter, Depends, status

from src.api.auth.models import (
    UserRegistration,
    RiderRegistrationRequest,
)
from src.api.auth.service import AuthService
from src.config.constants import UserRole
from src.dependencies.auth import RoleChecker
from src.shared.responses import success_response

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
auth_service = AuthService()


@auth_router.post(
    "/register", summary="Register a new user", status_code=status.HTTP_201_CREATED
)
async def register_user(user_registration: UserRegistration):
    result, status_code = await auth_service.register_user(user_registration)
    return success_response(result, status_code=status_code)


@auth_router.post(
    "/register/rider",
    summary="Register a new rider (Admin only)",
    description="Registers a user as a rider, linking them to an existing Rider Profile. Requires Admin privileges.",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def register_rider(user_registration: RiderRegistrationRequest):
    result, status_code = await auth_service.register_rider(user_registration)
    return success_response(result, status_code=status_code)
