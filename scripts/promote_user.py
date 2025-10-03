import argparse
import asyncio
import os
import sys

import firebase_admin
import google.auth
from firebase_admin import credentials

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.auth.service import AuthService
from src.api.users.service import UserService
from src.config.constants import UserRole

# Import all database models to ensure SQLAlchemy relationships are properly registered


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    if not firebase_admin._apps:
        is_local = os.getenv("DEPLOYMENT", "cloud") == "local"

        if is_local:
            # Local dev: must use service account key
            service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not service_account_path:
                raise ValueError(
                    "GOOGLE_APPLICATION_CREDENTIALS environment variable not set."
                )
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
        else:
            # Cloud Run (or any Google-managed environment): use ADC
            try:
                cred, project_id = google.auth.default()
            except Exception as e:
                raise RuntimeError(f"Failed to get default credentials: {e}")

            if not project_id:
                raise ValueError("Project ID could not be inferred from environment.")

            firebase_admin.initialize_app(
                credential=credentials.ApplicationDefault(),
                options={"projectId": project_id},
            )


async def promote_user(uid: str):
    """Promote a user to ADMIN."""
    print(f"Promoting user with UID: {uid}")

    auth_service = AuthService()
    user_service = UserService()

    try:
        # 1. Check if user exists in Firebase Auth
        auth_service.get_user_by_uid(uid)
        print(f"User {uid} found in Firebase Auth.")

        # 2. Check if user exists in PostgreSQL database
        user = await user_service.get_user_by_id(uid)
        if not user:
            print(f"User {uid} not found in PostgreSQL database. Cannot promote.")
            return

        print(f"User {uid} found in PostgreSQL database. Current role: {user.role}")

        # 3. Set custom claim in Firebase Auth
        print("Setting custom claim to ADMIN in Firebase Auth...")
        auth_service.set_user_role(uid, UserRole.ADMIN)
        print("Custom claim set successfully.")

        # 4. Update role in PostgreSQL
        print("Updating user role to ADMIN in PostgreSQL...")
        await user_service.update_user(uid, {"role": UserRole.ADMIN.value})
        print("User role updated successfully in PostgreSQL.")

        # 5. Verify the change
        updated_user = await user_service.get_user_by_id(uid)

        # Verify Firebase Auth custom claims
        firebase_user = auth_service.get_user_by_uid(uid)

        if (
            updated_user
            and updated_user.role == UserRole.ADMIN
            and firebase_user.custom_claims.get("role") == UserRole.ADMIN.value
        ):
            print(f"\nSuccessfully promoted user {uid} to ADMIN.")
            print(f"Verified PostgreSQL role: {updated_user.role}")
            print(
                f"Verified Firebase Auth role claim: {firebase_user.custom_claims.get('role')}"
            )
        else:
            print("\nError: Promotion verification failed.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote a user to an admin role.")
    parser.add_argument("uid", type=str, help="The UID of the user to promote.")
    args = parser.parse_args()

    initialize_firebase()
    asyncio.run(promote_user(args.uid))
