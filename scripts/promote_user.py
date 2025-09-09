import os
import sys
import asyncio
import argparse
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials

# Add project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.api.users.service import UserService
from src.api.auth.service import AuthService
from src.config.constants import UserRole

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    load_dotenv()
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not service_account_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")

    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)

async def promote_user(uid: str):
    """Promote a user to ADMIN."""
    print(f"Promoting user with UID: {uid}")
    
    auth_service = AuthService()
    user_service = UserService()

    try:
        # 1. Check if user exists in Firebase Auth
        auth_service.get_user_by_uid(uid)
        print(f"User {uid} found in Firebase Auth.")

        # 2. Check if user exists in Firestore
        user = await user_service.get_user_by_id(uid)
        if not user:
            print(f"User {uid} not found in Firestore. Cannot promote.")
            return

        print(f"User {uid} found in Firestore. Current role: {user.role}")

        # 3. Set custom claim in Firebase Auth
        print("Setting custom claim to ADMIN in Firebase Auth...")
        auth_service.set_user_role(uid, UserRole.ADMIN)
        print("Custom claim set successfully.")

        # 4. Update role in Firestore
        print("Updating user role to ADMIN in Firestore...")
        await user_service.update_user(uid, {"role": UserRole.ADMIN.value})
        print("User role updated successfully in Firestore.")

        # 5. Verify the change
        updated_user = await user_service.get_user_by_id(uid)
        
        # Verify Firebase Auth custom claims
        firebase_user = auth_service.get_user_by_uid(uid)
        
        if updated_user and updated_user.role == UserRole.ADMIN and firebase_user.custom_claims.get('role') == UserRole.ADMIN.value:
            print(f"\nSuccessfully promoted user {uid} to ADMIN.")
            print(f"Verified Firestore role: {updated_user.role}")
            print(f"Verified Firebase Auth role claim: {firebase_user.custom_claims.get('role')}")
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
