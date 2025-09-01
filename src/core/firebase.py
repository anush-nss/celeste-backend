import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
from dotenv import load_dotenv

load_dotenv()

# Path to your Firebase service account JSON file
SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if not SERVICE_ACCOUNT_PATH:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")

# Initialize Firebase Admin SDK
cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)

def get_firebase_auth():
    return auth

def get_firestore_db():
    return firestore.client()
