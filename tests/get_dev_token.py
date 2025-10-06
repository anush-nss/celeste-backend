import httpx
from tests.constants import BASE_URL, CUSTOMER_UID

# --- Configuration ---
DEV_TOKEN_ENDPOINT = "/dev/auth/token"


async def get_dev_token(uid: str | None = None) -> str:
    """Generates a development ID token for the given UID."""
    url = f"{BASE_URL}{DEV_TOKEN_ENDPOINT}"
    headers = {"Content-Type": "application/json"}  # Still need this header for FastAPI
    if not uid:
        uid = CUSTOMER_UID

    # Change: Send UID as a query parameter
    params = {"uid": uid}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url, headers=headers, params=params
            )  # Use params instead of data
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

            response_json = response.json()
            token = response_json["data"]["id_token"]
            return token

    except httpx.RequestError as e:
        print(f"Error generating token: {e}")
        if hasattr(e, "response") and e is not None:
            print(f"Response content: {e}")
        raise


if __name__ == "__main__":
    import asyncio

    try:
        token = asyncio.run(get_dev_token(CUSTOMER_UID))
        print(token)  # Print the token to stdout for the load test script to capture
    except Exception as e:
        print(f"Failed to get dev token: {e}")
        exit(1)
