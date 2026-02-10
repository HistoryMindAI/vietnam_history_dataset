import requests
import sys
import time

# Config URLs
BE_URL = "https://behistorymindai-production.up.railway.app"
AI_URL = "https://vietnamhistorydataset-production.up.railway.app"
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

def check_health(url):
    print(f"Checking health at {url}/actuator/health...")
    try:
        response = requests.get(f"{url}/actuator/health", timeout=10) # Spring Boot Actuator
        if response.status_code == 200:
            print(f"{GREEN}✅ BE Health OK{RESET}")
            return True
        else:
            print(f"{RED}❌ BE Health FAILED: {response.status_code} - {response.text}{RESET}")
            return False
    except Exception as e:
        print(f"{RED}❌ BE Health ERROR: {e}{RESET}")
        return False
        # sys.exit(1)

def check_be_chat():
    print(f"\nTesting BE Chat API at {BE_URL}/api/v1/chat/ask...")
    # ChatRequest definition in Java: expect "message" or "query"?
    # Java Code: public class ChatRequest { private String query; }
    # So payload is {"query": "..."}
    payload = {"query": "Sự kiện năm 1945"}
    try:
        start = time.time()
        resp = requests.post(f"{BE_URL}/api/v1/chat/ask", json=payload, timeout=30)
        dur = time.time() - start
        
        if resp.status_code == 200:
            print(f"{GREEN}✅ BE Chat PASSED in {dur:.2f}s{RESET}")
            data = resp.json()
            print(f"   Response: {str(data)[:200]}...")
            return True
        else:
            print(f"{RED}❌ BE Chat FAILED: {resp.status_code} - {resp.text}{RESET}")
            return False
    except Exception as e:
        print(f"{RED}❌ BE Chat ERROR: {e}{RESET}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Full Chain Test\n")
    
    if not check_health(BE_URL):
        print("\n⚠️  BE seems down or unreachable.")
        # Try checking AI directly just in case
    
    check_be_chat()
    
    # Check AI directly if BE failed
    print(f"\nTesting AI Service directly at {AI_URL}/api/chat...")
    payload = {"query": "Sự kiện năm 1945"}
    try:
        resp = requests.post(f"{AI_URL}/api/chat", json=payload, timeout=30)
        if resp.status_code == 200:
            print(f"{GREEN}✅ AI Chat PASSED{RESET}")
            print(f"   Response: {resp.text[:500]}...") # Show more
        else:
            print(f"{RED}❌ AI Chat FAILED: {resp.status_code} - {resp.text}{RESET}")
    except Exception as e:
        print(f"{RED}❌ AI Chat ERROR: {e}{RESET}")

