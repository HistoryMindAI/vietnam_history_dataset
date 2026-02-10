import urllib.request, json

base = "http://127.0.0.1:8000"
query = "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"

url = f"{base}/api/chat"
body = json.dumps({"query": query}).encode("utf-8")
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read())

# Write full response to file
with open("scripts/_full_response.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"intent: {data['intent']}")
print(f"no_data: {data['no_data']}")
print(f"events: {len(data['events'])}")
print(f"\n=== ANSWER ===")
print(data.get("answer", "NONE"))
print(f"\n=== EVENTS ===")
for i, e in enumerate(data["events"]):
    print(f"\n--- Event {i+1} ---")
    print(f"  year: {e.get('year')}")
    print(f"  story: {(e.get('story') or '')[:200]}")
