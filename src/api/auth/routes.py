from fastapi import APIRouter, status

from src.api.auth.models import (
    UserRegistration,
)
from src.api.auth.service import AuthService
from src.shared.responses import success_response

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
auth_service = AuthService()


@auth_router.post(
    "/register", summary="Register a new user", status_code=status.HTTP_201_CREATED
)
async def register_user(user_registration: UserRegistration):
    result = await auth_service.register_user(user_registration)
    return success_response(result, status_code=status.HTTP_201_CREATED)
