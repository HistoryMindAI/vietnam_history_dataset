"""
implicit_context.py — Implicit Vietnamese Context Layer

Solves the core issue: 75% of documents don't contain "việt nam" but are
100% about Vietnamese history. This module treats "việt nam" as a scope
qualifier, not a discriminating keyword, and expands queries to match
specific historical entities instead.

Three capabilities:
1. Detect broad Vietnamese history queries (e.g. "các cuộc kháng chiến của Việt Nam")
2. Expand resistance/war terms to specific events & battles
3. Provide implicit context metadata for search scoring
"""

import re
import app.core.startup as startup


# ===================================================================
# 1. VIETNAM SCOPE DETECTION
# ===================================================================

# Terms that indicate the query is scoping to "Vietnamese history" in general
_VIETNAM_SCOPE_TERMS = {
    "việt nam", "viet nam", "nước ta", "đất nước ta", "dân tộc ta",
    "nước nhà", "tổ quốc", "đất việt", "nước việt",
}

# Broad historical query patterns — match when combined with Vietnam scope
_BROAD_QUERY_PATTERNS = [
    r"\blịch\s+sử\b",
    r"\bsự\s+kiện\b",
    r"\bcác\s+(?:cuộc|trận|chiến)\b",
    r"\btoàn\s+bộ\b",
    r"\bqua\s+các\s+(?:thời\s+kỳ|triều\s+đại|giai\s+đoạn)\b",
    r"\bnhững\s+(?:sự\s+kiện|mốc|cuộc)\b",
    r"\bdiễn\s+biến\b",
    r"\btóm\s+tắt\b",
]

# Resistance / war terms that need expansion
_RESISTANCE_TERMS = {
    "kháng chiến", "chiến tranh", "xâm lược", "ngoại xâm",
    "chống giặc", "đánh giặc", "chống ngoại xâm",
    "giữ nước", "bảo vệ tổ quốc", "bảo vệ đất nước",
}


def is_vietnam_scope_query(query: str) -> bool:
    """
    Check if the query uses "việt nam" (or equivalents) as a geographic
    scope qualifier rather than a specific keyword to search for.

    Examples that return True:
        "Các cuộc kháng chiến của Việt Nam"
        "Lịch sử Việt Nam qua các triều đại"
        "Sự kiện lịch sử nước ta"

    Examples that return False:
        "Trận Bạch Đằng năm 938"  (specific, no VN scope term)
        "Trần Hưng Đạo là ai?"     (specific entity)
    """
    q = query.lower().strip()
    return any(term in q for term in _VIETNAM_SCOPE_TERMS)


def is_broad_vietnam_query(query: str) -> bool:
    """
    Check if the query is a BROAD query scoped to Vietnam.
    These need maximum coverage — not filtering by specific entities.

    True for: "lịch sử việt nam", "các sự kiện lịch sử nước ta"
    False for: "trận bạch đằng ở việt nam" (specific entity present)
    """
    q = query.lower().strip()

    if not is_vietnam_scope_query(q):
        return False

    # Check for broad patterns
    for pattern in _BROAD_QUERY_PATTERNS:
        if re.search(pattern, q):
            return True

    return False


def has_resistance_terms(query: str) -> bool:
    """Check if query contains broad resistance/war terms that need expansion."""
    q = query.lower().strip()
    return any(term in q for term in _RESISTANCE_TERMS)


def expand_resistance_terms(query: str) -> list:
    """
    Expand broad resistance/war terms into specific historical events.
    Uses resistance_synonyms from knowledge_base.json.

    Example:
        "kháng chiến" → ["kháng chiến chống pháp", "kháng chiến chống mỹ",
                          "chống quân nguyên mông", "chống quân tống", ...]
    """
    q = query.lower().strip()
    expanded = []

    resistance_synonyms = getattr(startup, 'RESISTANCE_SYNONYMS', {})
    if not resistance_synonyms:
        # Fallback if startup hasn't loaded the KB section yet
        resistance_synonyms = _FALLBACK_RESISTANCE_SYNONYMS

    for term, expansions in resistance_synonyms.items():
        if term in q:
            if isinstance(expansions, list):
                expanded.extend(expansions)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for item in expanded:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    return unique


def expand_query_with_implicit_context(query: str, resolved_entities: dict) -> dict:
    """
    Core function: detect implicit Vietnamese context and return enriched
    search parameters.

    Returns:
        {
            "is_vietnam_scope": bool,
            "is_broad": bool,
            "has_resistance": bool,
            "expanded_terms": list[str],     # Specific terms to search
            "extra_search_queries": list[str], # Additional queries to run
            "skip_vietnam_keyword_filter": bool, # Don't filter by "việt nam"
        }
    """
    q = query.lower().strip()
    result = {
        "is_vietnam_scope": False,
        "is_broad": False,
        "has_resistance": False,
        "expanded_terms": [],
        "extra_search_queries": [],
        "skip_vietnam_keyword_filter": False,
    }

    # 1. Detect Vietnam scope
    result["is_vietnam_scope"] = is_vietnam_scope_query(q)
    result["is_broad"] = is_broad_vietnam_query(q)

    # 2. Always skip "việt nam" as keyword filter — it's never discriminating
    #    in a 100% Vietnamese history dataset
    result["skip_vietnam_keyword_filter"] = True

    # 3. Expand resistance terms
    result["has_resistance"] = has_resistance_terms(q)
    if result["has_resistance"]:
        expanded = expand_resistance_terms(q)
        result["expanded_terms"].extend(expanded)

        # Generate extra search queries from expansions
        for term in expanded[:8]:  # Limit to top 8 to avoid search overload
            result["extra_search_queries"].append(term)

    # 4. For broad Vietnam queries, add dynasty-based search queries
    if result["is_broad"]:
        # Pull all dynasties from index to ensure broad coverage
        dynasty_keys = list(getattr(startup, 'DYNASTY_INDEX', {}).keys())
        for dynasty in dynasty_keys[:10]:
            result["extra_search_queries"].append(f"{dynasty}")

    # 5. Check if resolved entities are empty + query has vietnam scope
    #    → likely needs implicit entity resolution
    has_entities = any(
        resolved_entities.get(k, [])
        for k in ("persons", "dynasties", "topics", "places")
    )

    if result["is_vietnam_scope"] and not has_entities and not result["has_resistance"]:
        # Generic Vietnam history query — add some broad search terms
        result["extra_search_queries"].extend([
            "khởi nghĩa", "chiến thắng", "độc lập", "thống nhất",
            "kháng chiến", "cách mạng", "triều đại",
        ])

    return result


# ===================================================================
# KEYWORD FILTER: Vietnam-context aware
# ===================================================================

# Words that should NEVER be used as discriminating keywords
# because they apply to ALL documents in this dataset
NON_DISCRIMINATING_KEYWORDS = {
    "việt nam", "viet nam", "lịch sử", "sự kiện",
    "nước ta", "đất nước", "tổ quốc", "dân tộc",
    "nước nhà", "đất việt", "nước việt",
    "việt", "nam", "history", "vietnam",
}


def filter_discriminating_keywords(keywords: set) -> set:
    """
    Remove non-discriminating keywords that would unfairly penalize
    documents in a Vietnamese-history-only dataset.
    """
    return {kw for kw in keywords if kw.lower() not in NON_DISCRIMINATING_KEYWORDS}


# ===================================================================
# FALLBACK DATA (used before startup loads knowledge_base.json)
# ===================================================================

_FALLBACK_RESISTANCE_SYNONYMS = {
    "kháng chiến": [
        "kháng chiến chống pháp", "kháng chiến chống mỹ",
        "chống quân nguyên mông", "chống quân tống", "chống quân thanh",
        "chống quân minh", "chống quân nam hán",
        "trận bạch đằng", "chiến thắng đống đa", "chiến thắng điện biên phủ",
        "khởi nghĩa lam sơn", "khởi nghĩa hai bà trưng",
    ],
    "chiến tranh": [
        "chiến tranh đông dương", "chiến tranh việt nam",
        "kháng chiến chống pháp", "kháng chiến chống mỹ",
    ],
    "xâm lược": [
        "nguyên mông xâm lược", "quân tống xâm lược",
        "pháp xâm lược", "quân minh xâm lược",
        "quân nam hán xâm lược", "quân thanh xâm lược",
    ],
    "ngoại xâm": [
        "nguyên mông", "quân tống", "thực dân pháp",
        "quân minh", "quân nam hán", "quân thanh", "quân hán",
    ],
    "chống ngoại xâm": [
        "kháng chiến", "chống giặc", "đánh giặc ngoại xâm",
        "nguyên mông", "quân tống", "thực dân pháp",
    ],
}
