"""
query_understanding.py - Natural Language Understanding Layer

Transforms diverse user phrasings into forms the engine can understand.
Three main capabilities:
1. Query Rewriting: abbreviations, typos, filler removal
2. Fuzzy Entity Matching: approximate name matching when exact fails
3. Query Expansion: add synonyms for better semantic search coverage
"""

import re
from unicodedata import normalize as unicode_normalize
from difflib import SequenceMatcher

# ===================================================================
# 1. ABBREVIATIONS & COMMON SHORTHANDS
# ===================================================================

ABBREVIATIONS = {
    # Country / geo
    "vn": "việt nam",
    "tq": "trung quốc",
    "lx": "liên xô",
    # Famous places / events
    "dbp": "điện biên phủ",
    "cmtt": "cách mạng tháng tám",
    "tnđl": "tuyên ngôn độc lập",
    "hcm": "hồ chí minh",
    # Common shortenings
    "ls": "lịch sử",
    "nv": "nhân vật",
    "sk": "sự kiện",
}

# ===================================================================
# 2. UNACCENTED → ACCENTED MAPPING (common Vietnamese names)
# ===================================================================

UNACCENTED_MAP = {
    # Persons
    "tran hung dao": "trần hưng đạo",
    "tran quoc tuan": "trần quốc tuấn",
    "nguyen hue": "nguyễn huệ",
    "quang trung": "quang trung",
    "ho chi minh": "hồ chí minh",
    "bac ho": "bác hồ",
    "nguyen tat thanh": "nguyễn tất thành",
    "nguyen ai quoc": "nguyễn ái quốc",
    "ngo quyen": "ngô quyền",
    "ly thuong kiet": "lý thường kiệt",
    "le loi": "lê lợi",
    "le thai to": "lê thái tổ",
    "dinh bo linh": "đinh bộ lĩnh",
    "dinh tien hoang": "đinh tiên hoàng",
    "vo nguyen giap": "võ nguyên giáp",
    "hai ba trung": "hai bà trưng",
    "trung trac": "trưng trắc",
    "trung nhi": "trưng nhị",
    "ba trieu": "bà triệu",
    "trieu thi trinh": "triệu thị trinh",
    "nguyen trai": "nguyễn trãi",
    "phan boi chau": "phan bội châu",
    "phan chau trinh": "phan châu trinh",
    "phan chu trinh": "phan chu trinh",
    "ly cong uan": "lý công uẩn",
    "ly thai to": "lý thái tổ",
    "nguyen anh": "nguyễn ánh",
    "le thanh tong": "lê thánh tông",
    "tran nhan tong": "trần nhân tông",
    "tran thai tong": "trần thái tông",
    "ho quy ly": "hồ quý ly",
    "le hoan": "lê hoàn",
    "le dai hanh": "lê đại hành",
    # Places
    "bach dang": "bạch đằng",
    "dong da": "đống đa",
    "dien bien phu": "điện biên phủ",
    "chi lang": "chi lăng",
    "dai viet": "đại việt",
    "dai co viet": "đại cồ việt",
    "nhu nguyet": "như nguyệt",
    "lam son": "lam sơn",
    "ba dinh": "ba đình",
    "thang long": "thăng long",
    "ha noi": "hà nội",
    "hue": "huế",
    "sai gon": "sài gòn",
    # Dynasties
    "nha tran": "nhà trần",
    "nha ly": "nhà lý",
    "nha le": "nhà lê",
    "nha nguyen": "nhà nguyễn",
    "nha dinh": "nhà đinh",
    "nha ho": "nhà hồ",
    "nha mac": "nhà mạc",
    "tay son": "tây sơn",
    # Topics
    "nguyen mong": "nguyên mông",
    "mong co": "mông cổ",
    "bac thuoc": "bắc thuộc",
    "phap thuoc": "pháp thuộc",
    "khoi nghia": "khởi nghĩa",
    "doc lap": "độc lập",
    "thong nhat": "thống nhất",
    "giai phong": "giải phóng",
    "cach mang": "cách mạng",
    "khang chien": "kháng chiến",
    "van mieu": "văn miếu",
    "quoc tu giam": "quốc tử giám",
}

# Sort by length (longest first) so multi-word phrases match before sub-phrases
_UNACCENTED_SORTED = sorted(UNACCENTED_MAP.keys(), key=len, reverse=True)

# ===================================================================
# 3. FILLER / NOISE WORDS
# ===================================================================

# Filler words/patterns to remove (won't affect meaning)
FILLER_PATTERNS = [
    r'\bê\b', r'\bơi\b', r'\bnhỉ\b', r'\bnha\b', r'\bnhé\b',
    r'\bvậy thì\b', r'\bthế thì\b', r'\bcho mình hỏi\b',
    r'\bmình muốn hỏi\b', r'\btôi muốn biết\b',
    r'\bcho tôi hỏi\b', r'\bxin hỏi\b', r'\blàm ơn\b',
    r'\bgiúp mình\b', r'\bgiúp tôi\b',
    r'\bđi\b(?=\s*$)',  # trailing "đi"
    r'\bvới\b(?=\s*$)',  # trailing "với"
]

# ===================================================================
# 4. TYPO / SPELLING CORRECTIONS
# ===================================================================

TYPO_FIXES = {
    "nguyen huye": "nguyễn huệ",
    "nguyen huee": "nguyễn huệ",
    "nguyen huej": "nguyễn huệ",
    "quangtrung": "quang trung",
    "tran hung đao": "trần hưng đạo",
    "tranhungdao": "trần hưng đạo",
    "hochiminhh": "hồ chí minh",
    "hochiminh": "hồ chí minh",
    "bachđang": "bạch đằng",
    "bachdang": "bạch đằng",
    "dienbienphu": "điện biên phủ",
    "dongda": "đống đa",
}


def _strip_accents(text: str) -> str:
    """Remove Vietnamese diacritics for comparison."""
    import unicodedata as _ud
    nfkd = unicode_normalize("NFD", text)
    return "".join(c for c in nfkd if not _ud.category(c).startswith("M"))


def _normalize_text(text: str) -> str:
    """Basic normalization: lowercase, NFC, collapse spaces."""
    text = unicode_normalize("NFC", text.lower().strip())
    text = re.sub(r"\s+", " ", text)
    return text


# ===================================================================
# 5. CORE FUNCTIONS
# ===================================================================

def rewrite_query(query: str) -> str:
    """
    Rewrite query for better understanding:
    1. Normalize unicode
    2. Fix typos
    3. Expand abbreviations
    4. Restore accents for unaccented input
    5. Remove filler words
    
    Returns the rewritten query (still human readable).
    """
    if not query or not query.strip():
        return query
    
    result = _normalize_text(query)
    
    # Step 1: Fix known typos
    for typo, fix in TYPO_FIXES.items():
        if typo in result:
            result = result.replace(typo, fix)
    
    # Step 2: Expand abbreviations (word-boundary aware)
    for abbr, expansion in ABBREVIATIONS.items():
        # Match as whole word to avoid partial replacements
        pattern = r'\b' + re.escape(abbr) + r'\b'
        result = re.sub(pattern, expansion, result)
    
    # Step 3: Restore accents for unaccented Vietnamese input
    # Check if query looks unaccented (no Vietnamese-specific chars)
    if _looks_unaccented(result):
        result = _restore_accents(result)
    
    # Step 4: Remove filler words
    for pattern in FILLER_PATTERNS:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    
    # Clean up whitespace
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result


def _looks_unaccented(text: str) -> bool:
    """
    Heuristic: check if text is mostly unaccented Vietnamese.
    If text has very few Vietnamese diacritics relative to its length,
    it's likely typed without accents.
    """
    # Vietnamese-specific chars (beyond basic ASCII + common accents)
    vietnamese_chars = set("àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ")
    
    text_lower = text.lower()
    vn_count = sum(1 for c in text_lower if c in vietnamese_chars)
    alpha_count = sum(1 for c in text_lower if c.isalpha())
    
    if alpha_count == 0:
        return False
    
    # If less than 5% of alphabetic chars are Vietnamese diacritics, likely unaccented
    return (vn_count / alpha_count) < 0.05


def _restore_accents(text: str) -> str:
    """
    Attempt to restore Vietnamese accents by matching against known terms.
    Uses longest-match-first strategy.
    """
    result = text
    for unaccented in _UNACCENTED_SORTED:
        if unaccented in result:
            result = result.replace(unaccented, UNACCENTED_MAP[unaccented])
    return result


def fuzzy_match_entity(query: str, entity_dict: dict, threshold: float = 0.75) -> list:
    """
    Find entities that fuzzy-match the query when exact match fails.
    
    Args:
        query: The normalized query text
        entity_dict: Dict of {alias: canonical_name} or {name: [doc_indices]}
        threshold: Minimum similarity ratio (0-1)
    
    Returns:
        List of (matched_key, similarity_score) tuples, sorted by score desc
    """
    if not query or not entity_dict:
        return []
    
    q_words = query.lower().split()
    matches = []
    
    for key in entity_dict:
        key_words = key.split()
        key_len = len(key_words)
        
        # Try matching each n-gram of the query against the key
        for i in range(len(q_words) - key_len + 1):
            candidate = " ".join(q_words[i:i + key_len])
            
            # Exact match — skip (already handled by normal resolution)
            if candidate == key:
                continue
            
            # Compare with and without accents
            sim = SequenceMatcher(None, candidate, key).ratio()
            
            # Also try unaccented comparison
            candidate_stripped = _strip_accents(candidate)
            key_stripped = _strip_accents(key)
            sim_stripped = SequenceMatcher(None, candidate_stripped, key_stripped).ratio()
            
            best_sim = max(sim, sim_stripped)
            
            if best_sim >= threshold:
                matches.append((key, best_sim))
    
    # Sort by similarity descending, deduplicate
    matches.sort(key=lambda x: x[1], reverse=True)
    seen = set()
    unique_matches = []
    for m in matches:
        if m[0] not in seen:
            seen.add(m[0])
            unique_matches.append(m)
    
    return unique_matches


def generate_search_variations(query: str, resolved_entities: dict) -> list:
    """
    Generate search query variations for better semantic search coverage.
    Used when primary search yields few results.
    
    Args:
        query: Original query
        resolved_entities: Dict from resolve_query_entities
    
    Returns:
        List of alternative query strings to try
    """
    variations = []
    q_low = query.lower()
    
    # Variation 1: Entity-focused query
    # If we found persons, create a query focused on them
    persons = resolved_entities.get("persons", [])
    topics = resolved_entities.get("topics", [])
    dynasties = resolved_entities.get("dynasties", [])
    places = resolved_entities.get("places", [])
    
    if persons:
        # Create a concise person-centric query
        person_str = " ".join(persons)
        variations.append(person_str)
        # Add person + topic if both exist
        if topics:
            variations.append(f"{person_str} {' '.join(topics)}")
    
    if topics and not persons:
        variations.append(" ".join(topics))
    
    if places:
        place_str = " ".join(places)
        if persons:
            variations.append(f"{' '.join(persons)} {place_str}")
        else:
            variations.append(place_str)
    
    if dynasties and not persons:
        variations.append(" ".join(dynasties))
    
    return variations


def extract_question_intent(query: str) -> str | None:
    """
    Detect high-level question patterns for better intent routing.
    Returns intent hint or None if no pattern matched.
    
    Patterns:
    - "ai đã..." / "vị tướng nào..." → person_search
    - "chuyện gì xảy ra..." / "có sự kiện gì..." → event_search
    - "khi nào..." / "năm nào..." → time_search
    - "ở đâu..." / "tại đâu..." → place_search  
    - "tại sao..." / "vì sao..." → reason_search
    - "so sánh..." / "khác nhau..." → comparison
    """
    q = query.lower().strip()
    
    # Person search patterns
    person_patterns = [
        r'\bai\s+(?:đã|là|đã\s+từng)\b',
        r'\bvị\s+(?:tướng|vua|anh\s+hùng|lãnh\s+đạo)\s+nào\b',
        r'\bnhân\s+vật\s+nào\b',
        r'\bngười\s+(?:nào|nào\s+đã)\b',
    ]
    for p in person_patterns:
        if re.search(p, q):
            return "person_search"
    
    # Event search patterns
    event_patterns = [
        r'\bchuyện\s+gì\s+(?:xảy\s+ra|đã\s+xảy\s+ra|diễn\s+ra)\b',
        r'\bcó\s+(?:sự\s+kiện|chuyện)\s+gì\b',
        r'\bđiều\s+gì\s+(?:đã\s+)?xảy\s+ra\b',
        r'\bchuyện\s+gì\s+(?:đã\s+)?(?:xảy|diễn)\b',
    ]
    for p in event_patterns:
        if re.search(p, q):
            return "event_search"
    
    # Time search patterns
    time_patterns = [
        r'\b(?:khi|lúc|bao\s+giờ)\s+nào\b',
        r'\bnăm\s+nào\b',
        r'\bthời\s+(?:gian|điểm|kỳ)\s+nào\b',
    ]
    for p in time_patterns:
        if re.search(p, q):
            return "time_search"
    
    # Place search patterns
    place_patterns = [
        r'\b(?:ở|tại)\s+đâu\b',
        r'\bnơi\s+nào\b',
        r'\bđịa\s+(?:điểm|danh)\s+nào\b',
    ]
    for p in place_patterns:
        if re.search(p, q):
            return "place_search"
    
    # Comparison patterns
    comparison_patterns = [
        r'\bso\s+sánh\b',
        r'\bkhác\s+(?:nhau|biệt|gì)\b',
        r'\bgiống\s+(?:nhau|gì)\b',
    ]
    for p in comparison_patterns:
        if re.search(p, q):
            return "comparison"
    
    return None
