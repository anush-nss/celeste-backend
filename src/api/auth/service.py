import os
from typing import Optional
from firebase_admin import auth
from src.api.auth.models import UserRegistration, DecodedToken
from src.api.users.models import CreateUserSchema, UserSchema
from src.api.users.service import UserService
from src.config.constants import UserRole, CustomerTier
from src.shared.exceptions import ResourceNotFoundException
import requests


class AuthService:
    def __init__(self):
        self.user_service = UserService()

    async def register_user(self, user_registration: UserRegistration) -> dict:
        """
        Register a new user by verifying their Firebase ID token and creating user records.

        Args:
            user_registration: User registration data including ID token and name

        Returns:
            dict: Registration result with user info

        Raises:
            Exception: If token verification or user creation fails
        """
        try:
            # Verify the ID token
            decoded_token_dict = auth.verify_id_token(user_registration.idToken)
            decoded_token = DecodedToken(**decoded_token_dict)
            uid = decoded_token.uid
            phone_number = decoded_token.phone_number

            # Add custom claim for user role
            auth.set_custom_user_claims(uid, {"role": UserRole.CUSTOMER.value})

            # Create user in Firestore with explicit defaults
            create_user_data = CreateUserSchema(
                name=user_registration.name,
                phone=phone_number,
                role=UserRole.CUSTOMER,
                customer_tier=CustomerTier.BRONZE,
            )
            new_user = await self.user_service.create_user(create_user_data, uid)

            return {
                "message": "Registration successful",
                "user": {
                    "uid": new_user.id,
                    "role": new_user.role,
                    "customer_tier": new_user.customer_tier,
                },
            }
        except Exception as e:
            raise Exception(f"Registration failed: {e}")

    def verify_id_token(self, id_token: str) -> DecodedToken:
        """
        Verify a Firebase ID token and return decoded token data.

        Args:
            id_token: Firebase ID token string

        Returns:
            DecodedToken: Decoded and validated token data

        Raises:
            Exception: If token verification fails
        """
        try:
            decoded_token_dict = auth.verify_id_token(id_token)
            return DecodedToken(**decoded_token_dict)
        except Exception as e:
            raise Exception(f"Token verification failed: {e}")

    def set_user_role(self, uid: str, role: UserRole) -> None:
        """
        Set custom claims for a user in Firebase Auth.

        Args:
            uid: User UID
            role: User role to set

        Raises:
            Exception: If setting custom claims fails
        """
        try:
            auth.set_custom_user_claims(uid, {"role": role.value})
        except Exception as e:
            raise Exception(f"Failed to set user role: {e}")

    def get_user_by_uid(self, uid: str):
        """
        Get Firebase Auth user record by UID.

        Args:
            uid: User UID

        Returns:
            UserRecord: Firebase user record

        Raises:
            Exception: If user not found or other error
        """
        try:
            return auth.get_user(uid)
        except auth.UserNotFoundError:
            raise ResourceNotFoundException(
                detail=f"User with UID {uid} not found in Firebase Auth"
            )
        except Exception as e:
            raise Exception(f"Failed to get user: {e}")

    def generate_development_id_token(self, uid: str) -> dict:
        """
        Generate an ID token for an existing Firebase user for development purposes.

        Args:
            uid: User UID

        Returns:
            dict: Token data including ID token, refresh token, etc.

        Raises:
            Exception: If token generation fails
        """
        try:
            # Verify the user exists in Firebase Auth
            user_record = self.get_user_by_uid(uid)

            # Create custom token for existing user
            custom_token = auth.create_custom_token(uid)

            # Get Firebase Web API key from environment
            firebase_web_api_key = os.getenv("FIREBASE_WEB_API_KEY")
            if not firebase_web_api_key:
                raise Exception(
                    "FIREBASE_WEB_API_KEY environment variable is required to generate ID tokens"
                )

            # Exchange custom token for ID token using Firebase Auth REST API
            auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={firebase_web_api_key}"

            response = requests.post(
                auth_url,
                json={"token": custom_token.decode("utf-8"), "returnSecureToken": True},
            )

            if response.status_code != 200:
                error_data = (
                    response.json()
                    if response.headers.get("content-type") == "application/json"
                    else response.text
                )
                raise Exception(
                    f"Failed to exchange custom token for ID token: {error_data}"
                )

            auth_data = response.json()

            return {
                "id_token": auth_data.get("idToken"),
                "refresh_token": auth_data.get("refreshToken"),
                "uid": uid,
                "email": user_record.email,
                "expires_in": auth_data.get("expiresIn"),
                "message": f"ID token generated successfully for user {uid}",
            }

        except Exception as e:
            raise Exception(f"Failed to create ID token: {e}")

    async def get_user_profile(self, uid: str) -> Optional[UserSchema]:
        """
        Get user profile from Firestore by UID.

        Args:
            uid: User UID

        Returns:
            UserSchema: User profile data or None if not found
        """
        return await self.user_service.get_user_by_id(uid)
