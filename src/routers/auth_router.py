from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from src.models.auth_models import RegisterSchema, LoginSchema, UserRegistration
from src.models.user_models import UserSchema, CreateUserSchema
from src.auth.dependencies import verify_token, get_current_user
from src.services.user_service import UserService
from firebase_admin import auth
from src.core.responses import success_response
from src.shared.constants import UserRole

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
user_service = UserService()

@auth_router.post("/verify", summary="Verify a user token")
async def verify_user_token(token_data: LoginSchema):
    try:
        decoded_token = auth.verify_id_token(token_data.token)
        return success_response({"valid": True, "user": decoded_token})
    except Exception as e:
        return success_response({"valid": False, "message": f"Invalid token: {e}"}, status_code=status.HTTP_401_UNAUTHORIZED)

@auth_router.post("/register", summary="Register a new user", status_code=status.HTTP_201_CREATED)
async def register_user(user_registration: UserRegistration):
    try:
        # Verify the ID token
        decoded_token = auth.verify_id_token(user_registration.idToken)
        uid = decoded_token['uid']

        # Add custom claim for user role
        auth.set_custom_user_claims(uid, {'role': UserRole.CUSTOMER.value})

        # Create user in Firestore
        create_user_data = CreateUserSchema(name=user_registration.name)
        new_user = await user_service.create_user(create_user_data, uid)

        return success_response({"message": "Registration successful", "user": {"uid": new_user.id, "role": new_user.role}}, status_code=status.HTTP_201_CREATED)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Registration failed: {e}")

@auth_router.get("/profile", summary="Get current user profile")
async def get_profile(current_user: Annotated[dict, Depends(get_current_user)]):
    return success_response(current_user)