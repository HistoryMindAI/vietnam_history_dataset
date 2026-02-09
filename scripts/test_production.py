import requests
import sys
import time

BASE_URL = "https://vietnamhistorydataset-production.up.railway.app"
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

def check_health():
    print(f"Checking health at {BASE_URL}/health...")
    try:
        start = time.time()
        resp = requests.get(f"{BASE_URL}/health", timeout=10)
        dur = time.time() - start
        if resp.status_code == 200:
            print(f"{GREEN}✅ Health Check PASSED in {dur:.2f}s{RESET}")
            return True
        else:
            print(f"{RED}❌ Health Check FAILED: {resp.status_code} - {resp.text}{RESET}")
            return False
    except Exception as e:
        print(f"{RED}❌ Health Check ERROR: {e}{RESET}")
        return False

def check_chat():
    print(f"\nTesting Chat API at {BASE_URL}/api/chat...")
    payload = {"query": "Sự kiện năm 1945"}
    try:
        start = time.time()
        resp = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=30)
        dur = time.time() - start
        if resp.status_code == 200:
            data = resp.json()
            events = data.get("events", [])
            print(f"{GREEN}✅ Chat API PASSED in {dur:.2f}s{RESET}")
            print(f"   Answer: {data.get('answer', '')[:100]}...")
            print(f"   Events found: {len(events)}")
            if events:
                print(f"   Sample Event: {events[0].get('event', '')[:100]}...")
            return True
        else:
            print(f"{RED}❌ Chat API FAILED: {resp.status_code} - {resp.text}{RESET}")
            return False
    except Exception as e:
        print(f"{RED}❌ Chat API ERROR: {e}{RESET}")
        return False

if __name__ == "__main__":
    print(f"🚀 Starting Production Test for {BASE_URL}\n")
    
    # Retry health check loop
    max_retries = 5
    for i in range(max_retries):
        if check_health():
            break
        print(f"   Waiting 10s before retry ({i+1}/{max_retries})...")
        time.sleep(10)
    else:
        print(f"\n{RED}❌ Service is not healthy after {max_retries} retries.{RESET}")
        sys.exit(1)

    # If health passes, check chat
    if not check_chat():
        sys.exit(1)
        
    print(f"\n{GREEN}🎉 ALL PRODUCTION TESTS PASSED!{RESET}")
