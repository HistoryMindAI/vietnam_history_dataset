import app.core.startup as startup
from app.core.config import TOP_K, SIM_THRESHOLD
from functools import lru_cache
from app.utils.normalize import normalize_query
import re

# NOTE: Moved heavy imports (faiss, numpy) to function scope to improve startup time.
# import faiss
import numpy as np

# ===================================================================
# DYNASTY / PERIOD DETECTION FROM QUERY
# ===================================================================

# Map query patterns to dynasty names for metadata filtering
DYNASTY_QUERY_PATTERNS = [
    (re.compile(r"(?:nhà|triều|triều đại|thời)\s+(Lý)\b", re.IGNORECASE), "Lý"),
    (re.compile(r"(?:nhà|triều|triều đại|thời)\s+(Trần)\b", re.IGNORECASE), "Trần"),
    (re.compile(r"(?:nhà|triều|triều đại|thời)\s+(Lê)\b", re.IGNORECASE), "Lê"),
    (re.compile(r"(?:nhà|triều|triều đại|thời)\s+(Nguyễn)\b", re.IGNORECASE), "Nguyễn"),
    (re.compile(r"(?:nhà|triều|triều đại|thời)\s+(Đinh)\b", re.IGNORECASE), "Đinh"),
    (re.compile(r"(?:nhà|triều|triều đại|thời)\s+(Hồ)\b", re.IGNORECASE), "Hồ"),
    (re.compile(r"(?:nhà|triều|triều đại|thời)\s+(Mạc)\b", re.IGNORECASE), "Mạc"),
    (re.compile(r"Tây Sơn", re.IGNORECASE), "Tây Sơn"),
    (re.compile(r"Tiền Lê", re.IGNORECASE), "Tiền Lê"),
    (re.compile(r"Lê sơ", re.IGNORECASE), "Lê sơ"),
    (re.compile(r"Lê trung hưng", re.IGNORECASE), "Lê trung hưng"),
    (re.compile(r"Bắc thuộc", re.IGNORECASE), "Bắc thuộc"),
    (re.compile(r"Hùng Vương", re.IGNORECASE), "Hùng Vương / An Dương Vương"),
    (re.compile(r"Pháp thuộc", re.IGNORECASE), "Pháp thuộc"),
]

# Multi-word historical phrases that should NOT be split
HISTORICAL_PHRASES = [
    "nguyên mông", "đại việt", "nhà trần", "nhà lý", "nhà lê",
    "nhà nguyễn", "nhà đinh", "nhà hồ", "nhà mạc",
    "bắc thuộc", "pháp thuộc", "tây sơn", "tiền lê",
    "lê sơ", "lê trung hưng", "hùng vương",
    "hồ chí minh", "nguyễn ái quốc", "nguyễn tất thành",
    "trần hưng đạo", "lý thường kiệt", "quang trung", "nguyễn huệ",
    "lê lợi", "lê thánh tông", "đinh bộ lĩnh",
    "bạch đằng", "chi lăng", "đống đa", "điện biên phủ",
    "sông như nguyệt", "khởi nghĩa", "chiến thắng", "chiến dịch",
    "cách mạng", "độc lập", "thống nhất", "giải phóng",
    "kháng chiến", "phong trào", "cần vương",
]


def detect_dynasty_from_query(query: str) -> str | None:
    """
    Detect if the query is asking about a specific dynasty.
    Returns dynasty name or None.
    """
    for pattern, dynasty in DYNASTY_QUERY_PATTERNS:
        if pattern.search(query):
            return dynasty
    return None


def detect_place_from_query(query: str) -> str | None:
    """
    Detect if the query mentions a historical place/state name.
    """
    q_low = query.lower()
    place_patterns = [
        ("đại việt", "Đại Việt"),
        ("đại cồ việt", "Đại Cồ Việt"),
        ("champa", "Champa"),
        ("thăng long", "Thăng Long"),
    ]
    for pattern, place in place_patterns:
        if pattern in q_low:
            return place
    return None


# ===================================================================
# KEYWORD EXTRACTION (improved for Vietnamese history)
# ===================================================================

def extract_important_keywords(text: str) -> set:
    """
    Extract important keywords from query for relevance filtering.
    Handles multi-word phrases and avoids filtering out historical terms.
    """
    if not text:
        return set()
    
    # Common words to ignore — ONLY truly generic words
    # DO NOT include historical terms like triều, đại, chiến, etc.
    stop_words = {
        "là", "gì", "như", "thế", "nào", "có", "của", "và", "trong", "được",
        "với", "cho", "tôi", "về", "hãy", "kể", "biết",  "hỏi",
        "những", "các", "một", "này", "đó", "từ", "đến", "hay", "hoặc",
        "bạn", "mình", "xin", "vui", "lòng", "giúp", "tìm",
        "hiểu", "muốn", "cần", "thêm",
    }
    
    q_low = text.lower()
    extracted = set()
    
    # Step 1: Extract multi-word phrases first
    for phrase in HISTORICAL_PHRASES:
        if phrase in q_low:
            # Add as underscore-joined keyword for matching
            extracted.add(phrase.replace(" ", "_"))
            # Also add individual significant words
            for word in phrase.split():
                if len(word) > 2 and word not in stop_words:
                    extracted.add(word)
    
    # Step 2: Extract remaining single words
    normalized = re.sub(r'[^\w\s]', ' ', q_low)
    words = normalized.split()
    for w in words:
        if len(w) > 2 and w not in stop_words:
            extracted.add(w)
    
    return extracted


def check_query_relevance(query: str, doc: dict, dynasty_filter: str = None) -> bool:
    """
    Check if a document is actually relevant to the query.
    Uses keyword matching AND dynasty filtering.
    """
    # If dynasty filter is active, check dynasty first
    if dynasty_filter:
        doc_dynasty = doc.get("dynasty", "")
        # Allow partial matches: "Lê" matches "Lê sơ", "Lê trung hưng"
        if dynasty_filter.lower() in doc_dynasty.lower():
            return True  # Dynasty match = always relevant
    
    query_keywords = extract_important_keywords(query)
    
    if not query_keywords:
        return True  # No specific keywords, accept all
    
    # Build document text for matching (include ALL metadata fields)
    doc_parts = [
        str(doc.get("title", "")),
        str(doc.get("event", "")),
        str(doc.get("story", "")),
        " ".join(doc.get("persons", [])),
        " ".join(doc.get("places", [])),
        " ".join(doc.get("keywords", [])),
        str(doc.get("dynasty", "")),
        str(doc.get("period", "")),
    ]
    doc_text = " ".join(doc_parts).lower()
    
    # Check keyword matching
    matching_keywords = sum(1 for kw in query_keywords if kw in doc_text)
    
    # Require at least 1 keyword match (relaxed from 30%)
    return matching_keywords >= 1


# ===================================================================
# EMBEDDING + SEARCH
# ===================================================================

@lru_cache(maxsize=1024)
def get_cached_embedding(query: str):
    """
    Encodes and normalizes a query, caching the result to speed up repeated searches.
    Uses ONNX Runtime + Transformers Tokenizer.
    """
    if startup.session is None or startup.tokenizer is None:
        raise RuntimeError("ONNX model is not loaded")

    # 1. Tokenize (return numpy arrays)
    inputs = startup.tokenizer(
        query, 
        return_tensors="np", 
        padding=True, 
        truncation=True, 
        max_length=512
    )
    
    # 2. Prepare Inputs (ONNX expects int64)
    model_inputs = {
        "input_ids": inputs["input_ids"].astype(np.int64),
        "attention_mask": inputs["attention_mask"].astype(np.int64)
    }
    
    # Check session inputs for token_type_ids
    input_names = [i.name for i in startup.session.get_inputs()]
    if "token_type_ids" in input_names and "token_type_ids" in inputs:
        model_inputs["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)

    # 3. Inference
    outputs = startup.session.run(None, model_inputs)
    
    # 4. Pooling (Mean Pooling)
    last_hidden_state = outputs[0]
    
    input_mask_expanded = model_inputs["attention_mask"][:, :, None].astype(last_hidden_state.dtype)
    sum_embeddings = np.sum(last_hidden_state * input_mask_expanded, axis=1)
    sum_mask = np.sum(input_mask_expanded, axis=1)
    sum_mask = np.maximum(sum_mask, 1e-9)
    embedding = sum_embeddings / sum_mask
    
    # 5. Normalize (L2)
    norm = np.linalg.norm(embedding, axis=1, keepdims=True)
    embedding = embedding / norm
    
    # Flatten to [dimension]
    return embedding[0].astype("float32")


def semantic_search(query: str):
    """
    Perform semantic search with improved relevance filtering.
    Supports dynasty-aware filtering for broader historical queries.
    """
    if startup.index is None:
        print("[WARN] Search called before index is ready")
        return []

    if startup.session is None:
        print("[WARN] Search called before ONNX session is ready")
        return []

    # Detect dynasty and place filters from query
    dynasty_filter = detect_dynasty_from_query(query)
    place_filter = detect_place_from_query(query)

    # Normalize query before searching/caching to increase hit rate
    try:
        norm_q = normalize_query(query)
        emb = get_cached_embedding(norm_q)

        # FAISS requires 2D input: (n_queries, dim)
        emb_2d = np.expand_dims(emb, axis=0)

        # Search wider for dynasty/place queries
        search_k = min(TOP_K * 3, 50) if (dynasty_filter or place_filter) else min(TOP_K * 2, 30)
        scores, ids = startup.index.search(emb_2d, search_k)

        # Use configured threshold — lowered to catch broader queries
        threshold = SIM_THRESHOLD

        results = []
        
        # If we have a dynasty filter, also scan ALL documents for dynasty matches
        # (FAISS may miss them due to low semantic similarity)
        if dynasty_filter:
            for doc in startup.DOCUMENTS:
                doc_dynasty = doc.get("dynasty", "")
                if dynasty_filter.lower() in doc_dynasty.lower():
                    if doc not in results:
                        results.append(doc)
        
        # If we have a place filter, scan for place matches
        if place_filter:
            place_low = place_filter.lower()
            for doc in startup.DOCUMENTS:
                doc_text = " ".join([
                    str(doc.get("story", "")),
                    str(doc.get("event", "")),
                    " ".join(doc.get("places", [])),
                ]).lower()
                if place_low in doc_text and doc not in results:
                    results.append(doc)

        # Then add FAISS semantic results
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            
            # Score must meet threshold
            if score < threshold:
                continue
            
            # Use startup.DOCUMENTS
            if idx < len(startup.DOCUMENTS):
                doc = startup.DOCUMENTS[idx]
                
                # Check keyword relevance
                if not check_query_relevance(query, doc, dynasty_filter):
                    continue
                
                if doc not in results:
                    results.append(doc)
            
            # Limit results
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


def scan_by_year_range(start_year: int, end_year: int):
    """
    Returns events for a year range using indexed lookup.
    Scans all years from start_year to end_year (inclusive).
    """
    if startup.DOCUMENTS_BY_YEAR is None:
        return []
    results = []
    for year in range(start_year, end_year + 1):
        events = startup.DOCUMENTS_BY_YEAR.get(year, [])
        results.extend(events)
    return results

