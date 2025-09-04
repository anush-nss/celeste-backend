from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from src.api.auth.models import (
    RegisterSchema,
    LoginSchema,
    UserRegistration,
    DecodedToken,
)
from src.api.auth.service import AuthService
from src.dependencies.auth import get_current_user
from src.shared.responses import success_response

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
auth_service = AuthService()


@auth_router.post(
    "/register", summary="Register a new user", status_code=status.HTTP_201_CREATED
)
async def register_user(user_registration: UserRegistration):
    try:
        result = await auth_service.register_user(user_registration)
        return success_response(result, status_code=status.HTTP_201_CREATED)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@auth_router.get("/profile", summary="Get current user profile")
async def get_profile(current_user: Annotated[DecodedToken, Depends(get_current_user)]):
    return success_response(current_user.model_dump())
