import requests
import json
import sys

AI_URL = "https://vietnamhistorydataset-production.up.railway.app"
BE_URL = "https://behistorymindai-production.up.railway.app"
FE_URL = "https://fe-history-mind-ai.vercel.app"

def check_ai_service():
    print(f"Checking AI Service at {AI_URL}...")
    try:
        # Check health
        resp = requests.get(f"{AI_URL}/health", timeout=10)
        print(f"AI /health: {resp.status_code}")
        if resp.status_code != 200:
            print("AI Service Health Check Failed!")
            return False

        # Check chat with KNOWN EXISTING DATA
        # Based on meta.json inspection, "Hòa ước" exists.
        query_valid = "Hòa ước Patenôtre"
        payload = {"query": query_valid}
        resp = requests.post(f"{AI_URL}/api/chat", json=payload, timeout=30)
        print(f"AI /api/chat ('{query_valid}'): {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            if data.get("no_data") is False:
                print(f"AI Success: Found data for '{query_valid}'.")
            else:
                print(f"AI Warning: No data found for '{query_valid}' (Expected data). JSON: {json.dumps(data)}")
        else:
            print(f"AI Error: {resp.text}")
            return False

        # Check chat with MISSING DATA
        query_missing = "Ngô Quyền"
        payload = {"query": query_missing}
        resp = requests.post(f"{AI_URL}/api/chat", json=payload, timeout=30)
        print(f"AI /api/chat ('{query_missing}'): {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            if data.get("no_data") is True:
                print(f"AI Success: Correctly returned no data for '{query_missing}'.")
            else:
                print(f"AI Unexpected: Found data for '{query_missing}' (Expected none). JSON: {json.dumps(data)}")

        return True

    except Exception as e:
        print(f"AI Service failed: {e}")
        return False

def check_backend_service():
    print(f"\nChecking Backend Service at {BE_URL}...")
    try:
        # Check root
        resp = requests.get(f"{BE_URL}/", timeout=10)
        print(f"BE /: {resp.status_code}")

        # Check health (common Spring Boot endpoint)
        resp = requests.get(f"{BE_URL}/actuator/health", timeout=10)
        print(f"BE /actuator/health: {resp.status_code}")

        if resp.status_code != 200:
             resp = requests.get(f"{BE_URL}/health", timeout=10)
             print(f"BE /health: {resp.status_code}")

        if resp.status_code == 200:
            print("BE Service is UP.")
            return True
        else:
            print("BE Service seems DOWN or misconfigured (404/500).")
            return False

    except Exception as e:
        print(f"Backend Service failed: {e}")
        return False

def check_frontend():
    print(f"\nChecking Frontend at {FE_URL}...")
    try:
        resp = requests.get(FE_URL, timeout=10)
        print(f"FE Status: {resp.status_code}")
        if resp.status_code == 200:
            print("FE is reachable.")
            return True
        else:
            print("FE is unreachable.")
            return False
    except Exception as e:
        print(f"Frontend failed: {e}")
        return False

if __name__ == "__main__":
    print("=== INTEGRATION CHECK ===")
    ai_ok = check_ai_service()
    be_ok = check_backend_service()
    fe_ok = check_frontend()

    print("\n=== SUMMARY ===")
    print(f"AI Service: {'OK' if ai_ok else 'FAIL'}")
    print(f"Backend Service: {'OK' if be_ok else 'FAIL'}")
    print(f"Frontend Service: {'OK' if fe_ok else 'FAIL'}")

    if not be_ok:
        print("\nCRITICAL: Backend service is not responding correctly. This breaks the FE->BE connection.")

    if ai_ok and not be_ok:
        print("Integration FE->BE->AI is BROKEN at BE level.")
