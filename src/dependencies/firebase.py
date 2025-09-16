from firebase_admin import auth, credentials
import firebase_admin
import os

def initialize_firebase():
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not service_account_path:
        return

    if not os.path.exists(service_account_path):
        return

    try:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
    except Exception:
        pass

if os.getenv("TESTING") != "True":
    initialize_firebase()
