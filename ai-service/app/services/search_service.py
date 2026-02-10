import app.core.startup as startup
import faiss
import numpy as np
from app.core.config import TOP_K, SIM_THRESHOLD
from functools import lru_cache
from app.utils.normalize import normalize_query
import re

# Keywords to extract from queries for relevance filtering
def extract_important_keywords(text: str) -> set:
    """
    Extract important keywords from query for relevance filtering.
    These are proper nouns, historical terms, and significant words.
    """
    if not text:
        return set()
    
    # Common words to ignore
    stop_words = {
        "là", "gì", "như", "thế", "nào", "có", "của", "và", "trong", "được",
        "với", "các", "những", "cho", "tôi", "về", "hãy", "kể", "cho", "biết",
        "năm", "triều", "đại", "thời", "kỳ", "lịch", "sử", "việt", "nam",
        "sự", "kiện", "chiến", "tranh", "cuộc", "ý", "nghĩa", "quan", "trọng"
    }
    
    # Normalize and extract words
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    words = normalized.split()
    
    # Filter significant words (>2 chars, not stop words)
    keywords = {w for w in words if len(w) > 2 and w not in stop_words}
    
    return keywords


def check_query_relevance(query: str, doc: dict) -> bool:
    """
    Check if a document is actually relevant to the query.
    Uses keyword matching to filter out false positives from semantic search.
    """
    query_keywords = extract_important_keywords(query)
    
    if not query_keywords:
        return True  # No specific keywords, accept all
    
    # Build document text for matching
    doc_text = " ".join([
        str(doc.get("title", "")),
        str(doc.get("event", "")),
        str(doc.get("story", "")),
        " ".join(doc.get("persons", [])),
        " ".join(doc.get("places", [])),
        " ".join(doc.get("keywords", []))
    ]).lower()
    
    # Check if at least one important query keyword appears in the document
    matching_keywords = sum(1 for kw in query_keywords if kw in doc_text)
    
    # Require at least 30% of query keywords to match
    min_matches = max(1, len(query_keywords) * 0.3)
    
    return matching_keywords >= min_matches


@lru_cache(maxsize=1024)
def get_cached_embedding(query: str):
    """
    Encodes and normalizes a query, caching the result to speed up repeated searches.
    """
    if startup.embedder is None:
        raise RuntimeError("Embedding model is not loaded")
        
    emb = startup.embedder.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(emb)
    return emb


def semantic_search(query: str):
    """
    Perform semantic search with improved relevance filtering.
    """
    if startup.index is None:
        # If called before ready, return empty or raise error
        print("[WARN] Search called before index is ready")
        return []

    if startup.embedder is None:
        print("[WARN] Search called before embedder is ready")
        return []

    # Normalize query before searching/caching to increase hit rate
    try:
        norm_q = normalize_query(query)
        emb = get_cached_embedding(norm_q)

        # Increase TOP_K to allow for filtering
        search_k = min(TOP_K * 2, 30)
        scores, ids = startup.index.search(emb, search_k)

        # Use a higher threshold for better relevance
        higher_threshold = max(SIM_THRESHOLD, 0.55)

        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            
            # Score must meet higher threshold
            if score < higher_threshold:
                continue
            
            # Use startup.DOCUMENTS
            if idx < len(startup.DOCUMENTS):
                doc = startup.DOCUMENTS[idx]
                
                # Additionally check keyword relevance
                if not check_query_relevance(query, doc):
                    continue
                
                results.append(doc)
            
            # Limit results to prevent verbose responses
            if len(results) >= TOP_K:
                break

        return results
    except Exception as e:
        print(f"[ERROR] Semantic search failed: {e}")
        return []


def scan_by_year(year: int):
    """
    Returns events for a specific year using an O(1) indexed lookup.
    """
    if startup.DOCUMENTS_BY_YEAR is None:
        return []
    return startup.DOCUMENTS_BY_YEAR.get(year, [])
