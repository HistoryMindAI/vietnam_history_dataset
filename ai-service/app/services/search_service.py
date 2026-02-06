from app.core.startup import embedder, index, DOCUMENTS, DOCUMENTS_BY_YEAR
import faiss
import numpy as np
from app.core.config import TOP_K, SIM_THRESHOLD
from functools import lru_cache
from app.utils.normalize import normalize_query

@lru_cache(maxsize=1024)
def get_cached_embedding(query: str):
    """
    Encodes and normalizes a query, caching the result to speed up repeated searches.
    """
    emb = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(emb)
    return emb

def semantic_search(query: str):
    # Normalize query before searching/caching to increase hit rate
    norm_q = normalize_query(query)
    emb = get_cached_embedding(norm_q)

    scores, ids = index.search(emb, TOP_K)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1 or score < SIM_THRESHOLD:
            continue
        results.append(DOCUMENTS[idx])

    return results


def scan_by_year(year: int):
    """
    Returns events for a specific year using an O(1) indexed lookup.
    """
    return DOCUMENTS_BY_YEAR.get(year, [])
