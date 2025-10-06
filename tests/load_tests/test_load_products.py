import asyncio
import os
import sys
import threading
import time

import requests
from tests.constants import BASE_URL
from tests.get_dev_token import get_dev_token

# Add the project root to Python path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)


ENDPOINT = "/products/"

NUM_REQUESTS = 100  # Total number of requests to send
NUM_CONCURRENT_USERS = 10  # Number of simulated concurrent users

# --- Globals for storing results ---
response_times = []
successful_requests = 0
failed_requests = 0
lock = threading.Lock()


def send_request(request_num, bearer_token):
    """Sends a single request to the target endpoint and records the result."""
    global successful_requests, failed_requests

    url = f"{BASE_URL}{ENDPOINT}"
    headers = {"Authorization": f"Bearer {bearer_token}"}

    start_time = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=30)
        end_time = time.time()

        with lock:
            response_times.append(end_time - start_time)

        if response.status_code == 200:
            with lock:
                successful_requests += 1
        else:
            with lock:
                failed_requests += 1
            print(
                f"Request {request_num}: Failed with status {response.status_code} - {response.text[:100]}"
            )

    except requests.exceptions.RequestException as e:
        end_time = time.time()
        with lock:
            response_times.append(end_time - start_time)
            failed_requests += 1
        print(f"Request {request_num}: Failed with exception: {e}")


def worker(requests_per_worker, worker_id, bearer_token):
    """A worker thread that sends a batch of requests sequentially."""
    print(f"Worker {worker_id}: Starting...")
    for i in range(requests_per_worker):
        request_num = worker_id * requests_per_worker + i
        send_request(request_num, bearer_token)
    print(f"Worker {worker_id}: Finished.")


async def main():
    """Main function to run the load test."""
    # Get the bearer token using the async function
    try:
        bearer_token = await get_dev_token()
        print("Successfully obtained dev token")
    except Exception as e:
        print(f"\033[91mERROR: Failed to get dev token: {e}\033[0m")
        return

    print("--- Starting Load Test ---")
    print(f"Target: {BASE_URL}{ENDPOINT}")
    print(f"Total Requests: {NUM_REQUESTS}")
    print(f"Concurrent Users: {NUM_CONCURRENT_USERS}")
    print("--------------------------\n")

    start_time = time.time()

    requests_per_user = NUM_REQUESTS // NUM_CONCURRENT_USERS

    # Create threads for workers
    threads = []
    for i in range(NUM_CONCURRENT_USERS):
        thread = threading.Thread(
            target=worker, args=(requests_per_user, i, bearer_token)
        )
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    total_time = time.time() - start_time

    # --- Print Results ---
    print("\n--- Load Test Results ---")
    print(f"Total wall-clock time: {total_time:.2f} seconds")
    print(f"Successful requests: {successful_requests}")
    print(f"Failed requests: {failed_requests}")
    print(f"Total requests attempted: {successful_requests + failed_requests}")

    if response_times:
        # Threading-based calculations
        requests_per_second = successful_requests / total_time
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)

        print(f"Requests per second (RPS): {requests_per_second:.2f}")
        print(f"Average response time: {avg_response_time:.4f} seconds")
        print(f"Max response time: {max_response_time:.4f} seconds")
        print(f"Min response time: {min_response_time:.4f} seconds")

    print("-------------------------")


if __name__ == "__main__":
    asyncio.run(main())
