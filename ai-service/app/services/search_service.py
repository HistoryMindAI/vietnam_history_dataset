from app.core.startup import embedder, index, DOCUMENTS
import faiss
import numpy as np
from app.core.config import TOP_K, SIM_THRESHOLD

def semantic_search(query: str):
    emb = embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(emb)

    scores, ids = index.search(emb, TOP_K)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1 or score < SIM_THRESHOLD:
            continue
        results.append(DOCUMENTS[idx])

    return results


def scan_by_year(year: int):
    return [d for d in DOCUMENTS if d["year"] == year]
