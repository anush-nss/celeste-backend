import requests
import threading
import time
from get_dev_token import get_dev_token, get_base_url

# --- Test Configuration ---
BASE_URL = get_base_url()
ENDPOINT = "/products/"

# IMPORTANT: Replace with a valid JWT token for your test user
BEARER_TOKEN = get_dev_token()

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
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    
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
            print(f"Request {request_num}: Failed with status {response.status_code} - {response.text[:100]}")
            
    except requests.exceptions.RequestException as e:
        end_time = time.time()
        with lock:
            response_times.append(end_time - start_time)
            failed_requests += 1
        print(f"Request {request_num}: Failed with exception: {e}")

def worker(requests_per_worker, worker_id, bearer_token):
    """A worker thread that sends a batch of requests."""
    print(f"Worker {worker_id}: Starting...")
    for i in range(requests_per_worker):
        request_num = worker_id * requests_per_worker + i
        send_request(request_num, bearer_token) # Pass token to send_request
    print(f"Worker {worker_id}: Finished.")

def main():
    """Main function to run the load test."""
    # Get the bearer token from environment variable
    bearer_token = BEARER_TOKEN # Use the hardcoded token
    if bearer_token == "YOUR_BEARER_TOKEN_HERE":
        print("\033[91mERROR: Please replace 'YOUR_BEARER_TOKEN_HERE' with a valid JWT token in the script.\033[0m")
        return

    print("--- Starting Load Test ---")
    print(f"Target: {BASE_URL}{ENDPOINT}")
    
    # Removed token generation part
    
    print(f"Total Requests: {NUM_REQUESTS}")
    print(f"Concurrent Users: {NUM_CONCURRENT_USERS}")
    print("--------------------------\n")

    start_time = time.time()
    
    threads = []
    requests_per_user = NUM_REQUESTS // NUM_CONCURRENT_USERS
    
    for i in range(NUM_CONCURRENT_USERS):
        thread = threading.Thread(target=worker, args=(requests_per_user, i, bearer_token)) # Pass token to worker
        threads.append(thread)
        thread.start()
        
    for thread in threads:
        thread.join()
        
    total_time = time.time() - start_time
    
    # --- Print Results ---
    print("\n--- Load Test Results ---")
    print(f"Total time taken: {total_time:.2f} seconds")
    print(f"Successful requests: {successful_requests}")
    print(f"Failed requests: {failed_requests}")
    
    if response_times:
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
    main()