import urllib.request, json

base = "http://127.0.0.1:8000"

queries = [
    "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông",
    "Đại Việt đã được thành lập như thế nào và phát triển qua các thời kỳ ra sao",
]

for q in queries:
    print(f"=== QUERY: {q[:70]}... ===")
    url = f"{base}/api/chat"
    body = json.dumps({"query": q}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            print(f"  intent: {data.get('intent')}")
            print(f"  no_data: {data.get('no_data')}")
            events = data.get("events", [])
            print(f"  events: {len(events)}")
            if data.get("answer"):
                print(f"  answer: {data['answer'][:300]}...")
            else:
                print("  answer: NONE")
            for e in events[:3]:
                print(f"    - [{e.get('year')}] {e.get('dynasty','')} | {e.get('period','')} | {str(e.get('story',''))[:80]}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()
