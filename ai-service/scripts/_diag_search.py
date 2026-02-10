"""
Diagnostic script: traces the entire search flow step by step
to find exactly where results are being lost.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load startup resources
import app.core.startup as startup
startup.load_resources()

print(f"\n=== STARTUP STATE ===")
print(f"  Documents loaded: {len(startup.DOCUMENTS)}")
print(f"  Index loaded: {startup.index is not None}")
print(f"  Index vectors: {startup.index.ntotal if startup.index else 0}")
print(f"  Session loaded: {startup.session is not None}")
print(f"  Tokenizer loaded: {startup.tokenizer is not None}")

# Check if documents have dynasty/period fields
dynasties_in_data = set()
periods_in_data = set()
for d in startup.DOCUMENTS:
    dynasties_in_data.add(d.get("dynasty", ""))
    periods_in_data.add(d.get("period", ""))
print(f"  Dynasties in data: {dynasties_in_data}")
print(f"  Periods in data: {periods_in_data}")

# Now test the queries
from app.services.search_service import (
    detect_dynasty_from_query,
    detect_place_from_query,
    extract_important_keywords,
    semantic_search,
    get_cached_embedding,
    check_query_relevance,
)
from app.core.config import TOP_K, SIM_THRESHOLD
from app.utils.normalize import normalize_query
import numpy as np

queries = [
    "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông",
    "Đại Việt đã được thành lập như thế nào và phát triển qua các thời kỳ ra sao",
]

for query in queries:
    print(f"\n{'='*80}")
    print(f"QUERY: {query}")
    print(f"{'='*80}")
    
    # Step 1: Dynasty/Place detection
    dynasty = detect_dynasty_from_query(query)
    place = detect_place_from_query(query)
    print(f"\n[1] Dynasty detected: {dynasty}")
    print(f"[1] Place detected: {place}")
    
    # Step 2: Keyword extraction
    keywords = extract_important_keywords(query)
    print(f"\n[2] Keywords extracted: {keywords}")
    
    # Step 3: Dynasty scan
    if dynasty:
        dynasty_matches = []
        for doc in startup.DOCUMENTS:
            doc_dynasty = doc.get("dynasty", "")
            if dynasty.lower() in doc_dynasty.lower():
                dynasty_matches.append(doc)
        print(f"\n[3] Dynasty scan matches: {len(dynasty_matches)}")
        for d in dynasty_matches[:3]:
            print(f"    - [{d.get('year')}] {d.get('dynasty')} | {d.get('title', '')[:60]}")
    
    # Step 4: Place scan
    if place:
        place_matches = []
        place_low = place.lower()
        for doc in startup.DOCUMENTS:
            doc_text = " ".join([
                str(doc.get("story", "")),
                str(doc.get("event", "")),
                " ".join(doc.get("places", [])),
            ]).lower()
            if place_low in doc_text:
                place_matches.append(doc)
        print(f"\n[4] Place scan matches: {len(place_matches)}")
        for d in place_matches[:3]:
            print(f"    - [{d.get('year')}] {d.get('dynasty')} | {d.get('title', '')[:60]}")
    
    # Step 5: FAISS search
    print(f"\n[5] FAISS Search (threshold={SIM_THRESHOLD}, TOP_K={TOP_K})")
    norm_q = normalize_query(query)
    print(f"    Normalized query: {norm_q[:80]}")
    emb = get_cached_embedding(norm_q)
    emb_2d = np.expand_dims(emb, axis=0)
    
    search_k = min(TOP_K * 3, 50) if (dynasty or place) else min(TOP_K * 2, 30)
    scores, ids = startup.index.search(emb_2d, search_k)
    
    print(f"    search_k: {search_k}")
    print(f"    All scores: {scores[0][:10]}")
    print(f"    All IDs: {ids[0][:10]}")
    
    above_threshold = [(s, i) for s, i in zip(scores[0], ids[0]) if s >= SIM_THRESHOLD and i >= 0]
    print(f"    Above threshold ({SIM_THRESHOLD}): {len(above_threshold)}")
    
    for score, idx in above_threshold[:5]:
        if idx < len(startup.DOCUMENTS):
            doc = startup.DOCUMENTS[idx]
            relevant = check_query_relevance(query, doc, dynasty)
            print(f"    - score={score:.4f} idx={idx} relevant={relevant} | [{doc.get('year')}] {doc.get('dynasty')} | {doc.get('title', '')[:50]}")
    
    # Step 6: Full semantic_search result
    print(f"\n[6] semantic_search() result:")
    results = semantic_search(query)
    print(f"    Found: {len(results)} results")
    for r in results[:5]:
        print(f"    - [{r.get('year')}] {r.get('dynasty')} | {r.get('title', '')[:60]}")
    
    # Step 7: Full engine_answer result
    from app.services.engine import engine_answer
    print(f"\n[7] engine_answer() result:")
    response = engine_answer(query)
    print(f"    intent: {response.get('intent')}")
    print(f"    no_data: {response.get('no_data')}")
    print(f"    events: {len(response.get('events', []))}")
    if response.get("answer"):
        print(f"    answer: {response['answer'][:200]}")
    else:
        print(f"    answer: NONE")
