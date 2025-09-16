import httpx
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")


async def get_dev_token(uid: str, email: str = "test@example.com"):
    """
    Returns a dummy token for testing purposes.
    """
    return "dummy-token"
