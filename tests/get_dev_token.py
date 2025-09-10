import httpx
import json
import os

# --- Configuration ---
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DEV_TOKEN_ENDPOINT = "/dev/auth/token"

# IMPORTANT: Hardcode the UID for which to generate the token
# This user must already exist in Firebase Auth
UID_TO_GENERATE_TOKEN_FOR = "nXhOA9apOdfY915h35yz1XvHBQE2" 

def get_base_url() -> str:
    """Returns the base URL for the API."""
    return BASE_URL

async def get_dev_token(uid: str | None = None) -> str:
    """Generates a development ID token for the given UID."""
    url = f"{BASE_URL}{DEV_TOKEN_ENDPOINT}"
    headers = {"Content-Type": "application/json"} # Still need this header for FastAPI
    if not uid:
        uid = UID_TO_GENERATE_TOKEN_FOR
    
    # Change: Send UID as a query parameter
    params = {"uid": uid}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, params=params) # Use params instead of data
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            
            response_json = response.json()
            token = response_json["data"]["id_token"]
            return token

    except httpx.RequestError as e:
        print(f"Error generating token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        raise

if __name__ == "__main__":
    import asyncio
    try:
        token = asyncio.run(get_dev_token(UID_TO_GENERATE_TOKEN_FOR))
        print(token) # Print the token to stdout for the load test script to capture
    except Exception as e:
        print(f"Failed to get dev token: {e}")
        exit(1)
