from src.core.firebase import get_firestore_db
from src.models.user_models import CreateUserSchema, UserSchema
from src.shared.constants import UserRole

class UserService:
    def __init__(self):
        self.db = get_firestore_db()
        self.users_collection = self.db.collection('users')

    async def create_user(self, user_data: CreateUserSchema, uid: str) -> UserSchema:
        user_dict = user_data.model_dump()
        user_dict['id'] = uid
        # Ensure role is set, default to CUSTOMER if not provided
        if 'role' not in user_dict:
            user_dict['role'] = UserRole.CUSTOMER.value
        
        self.users_collection.document(uid).set(user_dict)
        created_user_doc = self.users_collection.document(uid).get()
        created_dict = created_user_doc.to_dict()
        if created_dict:  # Ensure created_dict is not None
            return UserSchema(**created_dict)
        else:
            # Handle the case where the document doesn't exist after creation
            raise Exception("Failed to create user")

    async def get_user_by_id(self, user_id: str) -> UserSchema | None:
        user_doc = self.users_collection.document(user_id).get()
        if user_doc.exists:
            user_dict = user_doc.to_dict()
            if user_dict:  # Ensure user_dict is not None
                return UserSchema(**user_dict)
        return None
