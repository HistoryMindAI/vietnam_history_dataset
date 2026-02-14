"""
query_understanding.py - Natural Language Understanding Layer

Transforms diverse user phrasings into forms the engine can understand.
Four main capabilities:
1. Query Rewriting: abbreviations, typos, filler removal
2. Fuzzy Entity Matching: approximate name matching when exact fails
3. Query Expansion: add synonyms for better semantic search coverage
4. Phonetic Normalization: handle common Vietnamese spelling errors
"""

import re
from unicodedata import normalize as unicode_normalize
from difflib import SequenceMatcher
import logging
import app.core.startup as startup

logger = logging.getLogger(__name__)

# ===================================================================
# 1. ABBREVIATIONS & COMMON SHORTHANDS
# ===================================================================
# NOTE: Loaded dynamically from knowledge_base.json via startup.ABBREVIATIONS.
# Fallback dict only used if startup hasn't loaded yet.
_FALLBACK_ABBREVIATIONS = {
    "vn": "việt nam", "tq": "trung quốc", "lx": "liên xô",
    "dbp": "điện biên phủ", "cmtt": "cách mạng tháng tám",
    "hcm": "hồ chí minh", "ls": "lịch sử", "nv": "nhân vật", "sk": "sự kiện",
}

# ===================================================================
# 2. UNACCENTED → ACCENTED MAPPING (common Vietnamese names)
# ===================================================================

# Static fallback map (always available before startup completes)
_STATIC_UNACCENTED_MAP = {
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

# Dynamic map — starts as copy of static, enriched at startup from knowledge_base.json
UNACCENTED_MAP = dict(_STATIC_UNACCENTED_MAP)

# Sort by length (longest first) so multi-word phrases match before sub-phrases
_UNACCENTED_SORTED = sorted(UNACCENTED_MAP.keys(), key=len, reverse=True)


def _rebuild_unaccented_sorted():
    """Rebuild sorted key list after UNACCENTED_MAP is modified."""
    global _UNACCENTED_SORTED
    _UNACCENTED_SORTED = sorted(UNACCENTED_MAP.keys(), key=len, reverse=True)


def build_unaccented_map_from_knowledge_base():
    """
    Auto-generate unaccented→accented mappings from knowledge_base.json data.
    Called by startup.py after loading knowledge base.
    Ensures UNACCENTED_MAP stays in sync with knowledge_base.json automatically.
    """
    import app.core.startup as startup
    added = 0

    # Helper: add entry if stripped version differs from accented
    def _add_entry(accented_text: str):
        nonlocal added
        if not accented_text or not isinstance(accented_text, str):
            return
        accented_lower = accented_text.strip().lower()
        stripped = _strip_accents(accented_lower)
        if stripped != accented_lower and stripped not in UNACCENTED_MAP:
            UNACCENTED_MAP[stripped] = accented_lower
            added += 1

    # Process all person aliases (both canonical names and their aliases)
    for alias, canonical in startup.PERSON_ALIASES.items():
        _add_entry(alias)
        _add_entry(canonical)

    # Process all dynasty aliases
    for alias, canonical in startup.DYNASTY_ALIASES.items():
        _add_entry(alias)
        _add_entry(canonical)

    # Process all topic synonyms
    for synonym, canonical in startup.TOPIC_SYNONYMS.items():
        _add_entry(synonym)
        _add_entry(canonical)

    # Process all place names from inverted index
    for place_name in startup.PLACES_INDEX.keys():
        _add_entry(place_name)

    # Process all person names from inverted index
    for person_name in startup.PERSONS_INDEX.keys():
        _add_entry(person_name)

    # Rebuild sorted list for _restore_accents
    _rebuild_unaccented_sorted()

    logger.info(f"[NLU] Auto-generated {added} new unaccented mappings (total: {len(UNACCENTED_MAP)})")
    print(f"[NLU] UNACCENTED_MAP enriched: {len(_STATIC_UNACCENTED_MAP)} static + {added} auto-generated = {len(UNACCENTED_MAP)} total", flush=True)

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
# NOTE: Loaded dynamically from knowledge_base.json via startup.TYPO_FIXES.
# Fallback dict only used if startup hasn't loaded yet.
_FALLBACK_TYPO_FIXES = {
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

# ===================================================================
# 4b. VIETNAMESE PHONETIC NORMALIZATION
# Common spelling mistakes based on Vietnamese pronunciation confusion.
# These rules generate alternative spellings when exact match fails.
# ===================================================================

# Consonant pairs commonly confused in Vietnamese
PHONETIC_CONSONANT_PAIRS = [
    ("tr", "ch"),   # trần ↔ chần
    ("s", "x"),     # sử ↔ xử
    ("gi", "d"),    # giải ↔ dải (Southern dialect)
    ("r", "g"),     # ra ↔ ga (some dialects)
    ("v", "d"),     # về ↔ dề (some dialects)
    ("n", "l"),     # nào ↔ lào (some dialects)
]

# Vowel groups commonly confused
PHONETIC_VOWEL_PAIRS = [
    ("ươ", "uô"),
    ("iê", "yê"),
    ("ưu", "iu"),
]


def generate_phonetic_variants(text: str) -> list:
    """
    Generate phonetically similar Vietnamese words/phrases.
    Used as last resort when exact + fuzzy match both fail.
    
    Only applies consonant-initial swaps to avoid excessive false positives.
    Returns list of unique variant strings (excluding original).
    """
    if not text or len(text) < 2:
        return []
    
    variants = set()
    words = text.lower().split()
    
    for word_idx, word in enumerate(words):
        for original, replacement in PHONETIC_CONSONANT_PAIRS:
            # Forward swap: original → replacement
            if word.startswith(original):
                new_word = replacement + word[len(original):]
                new_words = words[:word_idx] + [new_word] + words[word_idx + 1:]
                variants.add(" ".join(new_words))
            # Reverse swap: replacement → original
            if word.startswith(replacement):
                new_word = original + word[len(replacement):]
                new_words = words[:word_idx] + [new_word] + words[word_idx + 1:]
                variants.add(" ".join(new_words))
    
    # Remove original text from variants
    variants.discard(text.lower())
    return list(variants)


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
    
    # Step 1: Fix known typos (dynamic from knowledge_base.json)
    typo_fixes = startup.TYPO_FIXES if startup.TYPO_FIXES else _FALLBACK_TYPO_FIXES
    for typo, fix in typo_fixes.items():
        if typo in result:
            result = result.replace(typo, fix)
    
    # Step 2: Expand abbreviations (dynamic from knowledge_base.json)
    abbreviations = startup.ABBREVIATIONS if startup.ABBREVIATIONS else _FALLBACK_ABBREVIATIONS
    for abbr, expansion in abbreviations.items():
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
    Strategy:
    1. If text looks fully unaccented, try fuzzy match FIRST (catches misspellings
       like 'nguyen hyue' → 'nguyễn huệ' as a whole phrase)
    2. Then do exact longest-match-first replacement for remaining fragments
    Both stages chain: fuzzy output feeds into exact matching.
    """
    result = text

    # Step 1: If text is unaccented, try fuzzy match first for multi-word phrases
    # This must run BEFORE exact match to prevent partial word-by-word restoration
    # (e.g., 'nguyen' → 'nguyễn' alone would block fuzzy matching of 'nguyen hyue')
    if _looks_unaccented(result):
        result = _fuzzy_restore_accents(result)

    # Step 2: Exact longest-match-first replacement on remaining unaccented parts
    for unaccented in _UNACCENTED_SORTED:
        if unaccented in result:
            result = result.replace(unaccented, UNACCENTED_MAP[unaccented])

    return result


def _fuzzy_restore_accents(text: str) -> str:
    """
    Fuzzy accent restoration for misspelled unaccented Vietnamese.
    Slides n-gram windows (2→1 words) over the text and matches against
    UNACCENTED_MAP keys using SequenceMatcher. Dynamic — auto-scales
    with any entries added to knowledge_base.json at startup.
    """
    words = text.split()
    if not words:
        return text

    best_replacement = None
    best_score = 0.0
    best_span = (0, 0)  # (start_word_idx, end_word_idx)
    FUZZY_THRESHOLD = 0.80

    # Try multi-word n-grams first (longer matches are more precise)
    for n in range(min(5, len(words)), 0, -1):
        for i in range(len(words) - n + 1):
            candidate = " ".join(words[i:i + n])
            # Skip if candidate is already accented
            if not _looks_unaccented(candidate):
                continue

            for map_key, map_val in UNACCENTED_MAP.items():
                # Only compare against keys of same word count
                if len(map_key.split()) != n:
                    continue
                sim = SequenceMatcher(None, candidate, map_key).ratio()
                if sim >= FUZZY_THRESHOLD and sim > best_score:
                    best_score = sim
                    best_replacement = map_val
                    best_span = (i, i + n)

        # If we found a good multi-word match at this n-gram size, apply it
        if best_replacement:
            before = " ".join(words[:best_span[0]])
            after = " ".join(words[best_span[1]:])
            parts = [p for p in (before, best_replacement, after) if p]
            return " ".join(parts)

    return text


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
    
    Strategies:
    1. Entity-focused queries (existing)
    2. Alias-based variations (NEW: swap person names with aliases)
    3. Topic synonym expansion (NEW: use all synonyms for matched topics)
    4. Phonetic variants (NEW: handle spelling errors)
    
    Args:
        query: Original query
        resolved_entities: Dict from resolve_query_entities
    
    Returns:
        List of alternative query strings to try
    """
    import app.core.startup as startup
    variations = []
    q_low = query.lower()
    
    persons = resolved_entities.get("persons", [])
    topics = resolved_entities.get("topics", [])
    dynasties = resolved_entities.get("dynasties", [])
    places = resolved_entities.get("places", [])
    
    # --- Strategy 1: Entity-focused query (existing) ---
    if persons:
        person_str = " ".join(persons)
        variations.append(person_str)
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
    
    # --- Strategy 2: Alias-based variations (NEW) ---
    # Replace each person name with their aliases for broader search
    for person in persons:
        all_aliases = [person]
        for alias, canonical in startup.PERSON_ALIASES.items():
            if canonical == person and alias != person:
                all_aliases.append(alias)
        # Create query variants with each alias
        for alt_name in all_aliases[1:]:  # Skip the canonical name itself
            variant = q_low.replace(person, alt_name)
            if variant != q_low and variant not in variations:
                variations.append(variant)
    
    # --- Strategy 3: Topic synonym expansion (NEW) ---
    for topic in topics:
        for syn, canonical in startup.TOPIC_SYNONYMS.items():
            if canonical == topic and syn != topic and syn not in variations:
                # Add both bare synonym and synonym in context
                variations.append(syn)
    
    # --- Strategy 4: Phonetic variants (NEW) ---
    # Only if we haven't found entities (likely typo in the query)
    if not any([persons, topics, dynasties, places]):
        phonetic_vars = generate_phonetic_variants(q_low)
        for pv in phonetic_vars[:3]:  # Limit to 3 phonetic variants
            if pv not in variations:
                variations.append(pv)
    
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
    
    # --- Fallback: check plain-text patterns from knowledge_base.json ---
    if startup.QUESTION_PATTERNS:
        for intent, patterns in startup.QUESTION_PATTERNS.items():
            if intent.startswith("_"):  # Skip metadata keys like "_description"
                continue
            if isinstance(patterns, list):
                for pattern in patterns:
                    if pattern in q:
                        return intent
    
    return None
