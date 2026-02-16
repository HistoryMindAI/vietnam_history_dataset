"""Trace query understanding for mixed-accent queries."""
import sys, io
sys.stdout = io.TextIOWrapper(open('trace_output.txt','wb'), encoding='utf-8')

from app.core import startup
startup.load_resources()

from app.services.query_understanding import understand_query, normalize_query
from app.services.search_service import resolve_query_entities

queries = ["Trận bạch den", "tran bach dan", "Tran bach den"]
for q in queries:
    print(f"\n{'='*60}")
    print(f"QUERY: {q}")
    norm = normalize_query(q)
    print(f"  normalized: {norm}")
    understood = understand_query(q)
    print(f"  understood: {understood}")
    resolved = resolve_query_entities(q)
    print(f"  resolved entities: {resolved}")
