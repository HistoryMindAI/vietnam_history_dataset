"""Test with full startup simulation."""
import sys, io
sys.stdout = io.TextIOWrapper(open('test_output.txt','wb'), encoding='utf-8')

# Simulate FastAPI startup
from app.core import startup
print("=== LOADING RESOURCES ===")
try:
    startup.load_resources()
    print(f"DOCUMENTS loaded: {len(startup.DOCUMENTS)}")
    print(f"Index loaded: {startup.index is not None}")
    print(f"Session loaded: {startup.session is not None}")
    print(f"PERSONS_INDEX: {len(startup.PERSONS_INDEX)}")
    print(f"DYNASTY_INDEX: {len(startup.DYNASTY_INDEX)}")
except Exception as e:
    print(f"STARTUP FAILED: {e}")
    sys.exit(1)

from app.services.engine import engine_answer

tests = [
    # Bug 1: fact-check wrong year
    "năm 1911 Bác Hồ ra đi tìm đường cứu nước đúng không",
    # Bug 2: narrative dynasty + topic
    "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông",
    # Bug 3: dynamic spelling
    "Nguyen Hyue",
    "tran bach dan",
    # Previous bugs (regression check)
    "Bác Hồ và Trần Hưng Đạo có chung giai đoạn không",
    "Trận bạch den",
    "Trận Bạch Đằng",
    "nhà Trần",
    "Nguyễn Huệ",
]

for q in tests:
    print(f"\n{'='*60}")
    print(f"QUERY: {q}")
    print(f"{'='*60}")
    r = engine_answer(q)
    print(f"  intent:  {r.get('intent')}")
    print(f"  no_data: {r.get('no_data')}")
    evts = r.get('events', [])
    print(f"  events:  {len(evts)}")
    ans = r.get('answer', '') or ''
    print(f"  answer:  {ans[:500]}")
    if r.get('conflict'):
        print(f"  conflict: {r.get('conflict_reasons')}")
    for i, e in enumerate(evts[:5]):
        yr = e.get('year','?')
        ev = str(e.get('event',''))[:100]
        print(f"  event[{i}]: year={yr}, {ev}")
