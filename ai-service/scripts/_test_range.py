# -*- coding: utf-8 -*-
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.engine import extract_year_range, extract_multiple_years

results = {"range": [], "multi": []}

# Test year range
range_tests = [
    "Từ năm 1225 đến năm 1400 có sự kiện gì",
    "Giai đoạn 1225-1400 có những gì",
    "Từ 938 đến 1288",
    "từ năm 1858 đến 1945 có sự kiện tiêu biểu nào",
    "từ 1000 tới 1500",
    "giai đoạn 1858 – 1945",
]

for t in range_tests:
    r = extract_year_range(t)
    results["range"].append({"input": t, "output": str(r)})

# Test multi year
multi_tests = [
    "Năm 938 và năm 1288 có gì nổi bật",
    "Sự kiện năm 1225, 1285 và 1288",
    "Năm 1945 có gì",
    "Trận Bạch Đằng 938 và Khởi nghĩa Lam Sơn 1418",
]

for t in multi_tests:
    r = extract_multiple_years(t)
    results["multi"].append({"input": t, "output": str(r)})

with open("scripts/_range_result.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("DONE")
