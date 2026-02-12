"""Manual test - forces startup initialization."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai-service"))

# Force startup to load FAISS + knowledge base
from app.core import startup
startup.load_all()

from app.services.engine import engine_answer

queries = [
    "Quang Trung và Nguyễn Huệ là ai",
    "Quang Trung và Nguyễn Huệ là gì của nhau",
    "Lý Thái Tổ dời đô về Thăng Long có ý nghĩa gì đối với lịch sử Việt Nam",
]

for q in queries:
    r = engine_answer(q)
    print("=" * 60)
    print("Q:", q)
    print("Intent:", r["intent"])
    years = [e.get("year") for e in r.get("events", [])]
    print("Years:", years)
    has_post_1802 = any(y >= 1802 for y in years if y and y != 2010)
    print("Has 1802+ events (bad):", has_post_1802)
    has_year_1000 = any(y == 1000 for y in years if y)
    print("Has year 1000 (bad):", has_year_1000)
    answer = r.get("answer", "")
    # Print answer truncated
    lines = answer.split("\n")
    for line in lines[:10]:
        print(" ", line)
    if len(lines) > 10:
        print("  ...")
    print()
