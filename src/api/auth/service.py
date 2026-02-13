import os
from typing import Optional

import requests
from dotenv import load_dotenv
from firebase_admin import auth

from src.api.auth.models import (
    DecodedToken,
    UserRegistration,
    RiderRegistrationRequest,
)
from src.api.users.models import CreateUserSchema, UserSchema
from src.api.users.service import UserService
from src.config.constants import UserRole
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import (
    ResourceNotFoundException,
    ServiceUnavailableException,
    ValidationException,
    ConflictException,
)

# Load environment variables from .env file
load_dotenv()


class AuthService:
    def __init__(self):
        self.user_service = UserService()
        self._error_handler = ErrorHandler(__name__)

    @handle_service_errors("user registration")
    async def register_user(
        self, user_registration: UserRegistration
    ) -> tuple[dict, int]:
        """
        Register a new user by verifying their Firebase ID token and creating user records.

        Args:
            user_registration: User registration data including ID token and name

        Returns:
            dict: Registration result with user info

        Raises:
            UnauthorizedException: If token verification fails
            ValidationException: If registration data is invalid
            ConflictException: If user already exists
        """
        if not user_registration.idToken:
            raise ValidationException(detail="ID token is required for registration")

        if not user_registration.name or len(user_registration.name.strip()) < 2:
            raise ValidationException(detail="Valid name is required for registration")

        # Verify the ID token
        decoded_token_dict = auth.verify_id_token(user_registration.idToken)
        decoded_token = DecodedToken(**decoded_token_dict)
        uid = decoded_token.uid
        phone_number = decoded_token.phone_number

        # Add custom claim for user role
        auth.set_custom_user_claims(uid, {"role": UserRole.CUSTOMER.value})

        # Check if user already exists
        existing_user = await self.user_service.get_user_by_id(uid)

        if existing_user:
            # Check if phone number is different
            if existing_user.phone != phone_number:
                # Update phone number
                updated_user = await self.user_service.update_user(
                    uid, {"phone": phone_number}
                )
                if not updated_user:
                    raise ResourceNotFoundException(
                        detail=f"User with ID {uid} not found during update"
                    )

                return {
                    "message": "User phone number updated successfully",
                    "user": {
                        "uid": updated_user.firebase_uid,
                        "role": updated_user.role,
                        "tier_id": updated_user.tier_id,
                    },
                }, 200
            else:
                # User exists and phone number is the same
                raise ConflictException(detail=f"User with UID {uid} already exists")

        # Create user in PostgreSQL database
        create_user_data = CreateUserSchema(
            name=user_registration.name.strip(),
            email=decoded_token.email,
            phone=phone_number,
            role=UserRole.CUSTOMER,
            tier_id=None,
        )
        new_user = await self.user_service.create_user(create_user_data, uid)

        return {
            "message": "Registration successful",
            "user": {
                "uid": new_user.firebase_uid,
                "role": new_user.role,
                "tier_id": new_user.tier_id,
            },
        }, 201

    @handle_service_errors("rider registration")
    async def register_rider(
        self, user_registration: "RiderRegistrationRequest"
    ) -> tuple[dict, int]:
        """
        Register a new rider (Admin only).
        Verifies ID token, creates/retrieves RiderProfile, creates User (RIDER), and links them.
        """
        if not user_registration.idToken:
            raise ValidationException(detail="ID token is required for registration")

        if not user_registration.name or len(user_registration.name.strip()) < 2:
            raise ValidationException(detail="Valid name is required for registration")

        # Verify the ID token
        decoded_token_dict = auth.verify_id_token(user_registration.idToken)
        decoded_token = DecodedToken(**decoded_token_dict)
        uid = decoded_token.uid
        phone_number = decoded_token.phone_number

        if not phone_number:
            raise ValidationException(
                detail="Phone number required in ID token for rider registration"
            )

        # Handle Rider Profile (Create or Link)
        from src.database.connection import AsyncSessionLocal
        from src.database.models.rider import RiderProfile
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            # Check if rider profile exists
            query = select(RiderProfile).filter(RiderProfile.phone == phone_number)
            result = await session.execute(query)
            rider_profile = result.scalars().first()

            if not rider_profile:
                # Create new Rider Profile
                rider_profile = RiderProfile(
                    phone=phone_number,
                    name=user_registration.name.strip(),
                    vehicle_type=user_registration.vehicle_type,
                    vehicle_registration_number=user_registration.vehicle_registration_number,
                    is_active=True,
                    user_id=uid,  # Link immediately
                )
                session.add(rider_profile)
            else:
                # Update existing profile
                rider_profile.user_id = uid
                rider_profile.name = (
                    user_registration.name.strip()
                )  # Update name if changed
                rider_profile.vehicle_type = user_registration.vehicle_type
                if user_registration.vehicle_registration_number:
                    rider_profile.vehicle_registration_number = (
                        user_registration.vehicle_registration_number
                    )

                if not rider_profile.is_active:
                    # Reactivate if it was inactive? Or error? Let's reactivate for registration.
                    rider_profile.is_active = True

            await session.commit()

        # Set custom claim RIDER
        auth.set_custom_user_claims(uid, {"role": UserRole.RIDER.value})

        # Check if user already exists
        existing_user = await self.user_service.get_user_by_id(uid)

        if existing_user:
            # If user exists, we've updated their profile link above.
            # Should we update their role in DB if it was different?
            # Assuming yes to self-correct.
            if existing_user.role != UserRole.RIDER:
                await self.user_service.update_user(uid, {"role": UserRole.RIDER})

            # Return existing user info
            return {
                "message": "Rider registered successfully (User linked)",
                "user": {
                    "uid": existing_user.firebase_uid,
                    "role": UserRole.RIDER,
                    "tier_id": existing_user.tier_id,
                },
            }, 200

        # Create user in PostgreSQL database as RIDER
        create_user_data = CreateUserSchema(
            name=user_registration.name.strip(),
            # Riders do not have email, explicitly set to None even if token has it
            email=None,
            phone=phone_number,
            role=UserRole.RIDER,
            tier_id=None,
        )
        new_user = await self.user_service.create_user(create_user_data, uid)

        return {
            "message": "Rider registered successfully",
            "user": {
                "uid": new_user.firebase_uid,
                "role": new_user.role,
                "tier_id": new_user.tier_id,
            },
        }, 201

    @handle_service_errors("token verification")
    def verify_id_token(self, id_token: str) -> DecodedToken:
        """
        Verify a Firebase ID token and return decoded token data.

        Args:
            id_token: Firebase ID token string

        Returns:
            DecodedToken: Decoded and validated token data

        Raises:
            UnauthorizedException: If token verification fails
            ValidationException: If token format is invalid
        """
        if not id_token or not id_token.strip():
            raise ValidationException(detail="Valid ID token is required")

        decoded_token_dict = auth.verify_id_token(id_token.strip())
        return DecodedToken(**decoded_token_dict)

    @handle_service_errors("setting user role")
    def set_user_role(self, uid: str, role: UserRole) -> None:
        """
        Set custom claims for a user in Firebase Auth.

        Args:
            uid: User UID
            role: User role to set

        Raises:
            ResourceNotFoundException: If user not found
            ValidationException: If parameters are invalid
        """
        if not uid or not uid.strip():
            raise ValidationException(detail="Valid user UID is required")

        if not isinstance(role, UserRole):
            raise ValidationException(detail="Valid user role is required")

        auth.set_custom_user_claims(uid.strip(), {"role": role.value})

    @handle_service_errors("retrieving user by UID")
    def get_user_by_uid(self, uid: str):
        """
        Get Firebase Auth user record by UID.

        Args:
            uid: User UID

        Returns:
            UserRecord: Firebase user record

        Raises:
            ResourceNotFoundException: If user not found
            ValidationException: If UID is invalid
        """
        if not uid or not uid.strip():
            raise ValidationException(detail="Valid user UID is required")

        try:
            return auth.get_user(uid.strip())
        except Exception as e:
            if "UserNotFoundError" in str(type(e)):
                raise ResourceNotFoundException(
                    detail=f"User with UID {uid} not found in Firebase Auth"
                )
            # Let the error handler deal with other Firebase errors
            raise

    @handle_service_errors("generating development ID token")
    def generate_development_id_token(self, uid: str) -> dict:
        """
        Generate an ID token for an existing Firebase user for development purposes.

        Args:
            uid: User UID

        Returns:
            dict: Token data including ID token, refresh token, etc.

        Raises:
            ResourceNotFoundException: If user not found
            ServiceUnavailableException: If token generation service is unavailable
            ValidationException: If parameters are invalid
        """
        if not uid or not uid.strip():
            raise ValidationException(detail="Valid user UID is required")

        # Verify the user exists in Firebase Auth
        user_record = self.get_user_by_uid(uid.strip())

        # Create custom token for existing user
        custom_token = auth.create_custom_token(uid.strip())

        # Get Firebase Web API key from environment
        is_local = os.getenv("DEPLOYMENT", "cloud") == "local"

        if is_local:
            # Local development: require FIREBASE_WEB_API_KEY from .env file
            firebase_web_api_key = os.getenv("FIREBASE_WEB_API_KEY")
            if not firebase_web_api_key:
                raise ServiceUnavailableException(
                    detail="FIREBASE_WEB_API_KEY environment variable not set for local development. "
                    "Add it to your .env file. Get this from Firebase Console → Project Settings → General → Web API Key"
                )
        else:
            # Cloud environment: this endpoint should not be used in production
            firebase_web_api_key = os.getenv("FIREBASE_WEB_API_KEY")
            if not firebase_web_api_key:
                raise ServiceUnavailableException(
                    detail="FIREBASE_WEB_API_KEY environment variable not set for local development. "
                    "Add it to your .env file. Get this from Firebase Console → Project Settings → General → Web API Key"
                )
            # raise ServiceUnavailableException(
            #     detail="Development token generation is not available in cloud environments"
            # )

        # Exchange custom token for ID token using Firebase Auth REST API
        auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={firebase_web_api_key}"

        try:
            response = requests.post(
                auth_url,
                json={"token": custom_token.decode("utf-8"), "returnSecureToken": True},
                timeout=10,  # Add timeout for better error handling
            )

            if response.status_code != 200:
                error_data = (
                    response.json()
                    if response.headers.get("content-type") == "application/json"
                    else response.text
                )
                self._error_handler.logger.error(f"Firebase API error: {error_data}")
                raise ServiceUnavailableException(
                    detail="Failed to generate authentication token"
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

        except requests.RequestException as e:
            self._error_handler.logger.error(
                f"Network error during token generation: {str(e)}"
            )
            raise ServiceUnavailableException(
                detail="Token generation service temporarily unavailable"
            )

    @handle_service_errors("retrieving user profile")
    async def get_user_profile(self, uid: str) -> Optional[UserSchema]:
        """
        Get user profile from PostgreSQL by UID.

        Args:
            uid: User UID

        Returns:
            UserSchema: User profile data or None if not found

        Raises:
            ValidationException: If UID is invalid
        """
        if not uid or not uid.strip():
            raise ValidationException(detail="Valid user UID is required")

        return await self.user_service.get_user_by_id(uid.strip())
