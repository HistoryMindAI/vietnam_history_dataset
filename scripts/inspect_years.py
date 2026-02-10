"""Inspect data for specific years - output to file."""
import json

with open("data/history_cleaned.jsonl", "r", encoding="utf-8") as f:
    data = [json.loads(line) for line in f]

with open("scripts/_year_report.txt", "w", encoding="utf-8") as out:
    for target_year in [1911, 1884]:
        docs = [d for d in data if d.get("year") == target_year]
        out.write(f"\n=== Year {target_year}: {len(docs)} events ===\n")
        for i, d in enumerate(docs):
            out.write(f"  [{i+1}] {d['id']}: {d['content'][:150]}\n")
    
    # Also check which years have > 5 events
    from collections import Counter
    year_counts = Counter(d.get("year") for d in data)
    heavy_years = {y: c for y, c in year_counts.items() if c > 5}
    out.write(f"\n=== Years with >5 events: {len(heavy_years)} ===\n")
    for y in sorted(heavy_years.keys()):
        out.write(f"  Year {y}: {heavy_years[y]} events\n")
    
    # Check max events per year
    out.write(f"\n=== Max events per year: {max(year_counts.values())} ===\n")
