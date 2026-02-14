"""
semantic_intent.py — Semantic Intent Classification Layer

Classifies queries into semantic intents based on linguistic analysis,
NOT keyword matching.  Distinguishes:

  1. "Việt Nam" as nation-state  vs. territory  vs. ethnic identity
  2. Structural requests: dynasty-timeline vs. event-list vs. thematic
  3. Conflict types: national resistance vs. civil war vs. colonial aggression

Architecture overview:
  classify_semantic_intent(query, resolved) → SemanticIntent
  ├─ detect_vietnam_entity_type(query)      → nation / territory / ethnic / None
  ├─ detect_structure_request(query)        → dynasty_timeline / chronological / thematic / None
  └─ match intent                           → resistance_national / dynasty_timeline / territorial_event / ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ===================================================================
# SEMANTIC INTENT DATA CLASS
# ===================================================================

@dataclass
class SemanticIntent:
    """Result of semantic intent classification."""
    intent: str                       # Primary intent label
    vietnam_scope: str | None = None  # "nation" | "territory" | "ethnic" | None
    structure: str | None = None      # "dynasty_timeline" | "chronological" | "thematic" | None
    temporal_bounds: tuple | None = None  # (start_year, end_year) or None
    confidence: float = 0.0           # 0.0–1.0 classification confidence
    retrieval_strategy: str = "semantic"  # Which retrieval path to use
    explanation: str = ""             # Human-readable explanation of classification


# ===================================================================
# 1. VIETNAM ENTITY TYPE DETECTION
# ===================================================================

# Possessive markers → "Việt Nam" as a NATION-STATE (political entity)
_NATION_POSSESSIVE_PATTERNS = [
    re.compile(r"\bcủa\s+(?:việt\s*nam|nước\s+ta|dân\s+tộc|tổ\s+quốc)\b", re.I),
    re.compile(r"\b(?:việt\s*nam|nước\s+ta|dân\s+tộc)\s+(?:ta|mình)\b", re.I),
    re.compile(r"\blịch\s+sử\s+(?:việt\s*nam|nước\s+ta|dân\s+tộc)\b", re.I),
    re.compile(r"\b(?:cuộc|các\s+cuộc)\s+(?:kháng\s+chiến|chiến\s+tranh|khởi\s+nghĩa)\s+(?:của\s+)?(?:việt\s*nam|dân\s+tộc)\b", re.I),
]

# Locative markers → "Việt Nam" as a TERRITORY (geographic location)
_TERRITORY_LOCATIVE_PATTERNS = [
    re.compile(r"\b(?:ở|tại|trên\s+đất|trên\s+lãnh\s+thổ)\s+(?:việt\s*nam|nước\s+ta)\b", re.I),
    re.compile(r"\bchiến\s+tranh\s+(?:ở|tại)\s+(?:việt\s*nam|nước\s+ta)\b", re.I),
    re.compile(r"\bxảy\s+ra\s+(?:ở|tại)\s+(?:việt\s*nam|nước\s+ta)\b", re.I),
]

# Ethnic identity markers
_ETHNIC_PATTERNS = [
    re.compile(r"\bdân\s+tộc\s+(?:việt|kinh)\b", re.I),
    re.compile(r"\bngười\s+(?:việt|kinh)\b", re.I),
    re.compile(r"\bvăn\s+hóa\s+(?:việt\s*nam|việt|dân\s+tộc)\b", re.I),
]


def detect_vietnam_entity_type(query: str) -> str | None:
    """
    Distinguish how "Việt Nam" is used in the query.

    Returns:
        "nation"    — VN as a political nation-state (e.g., "kháng chiến CỦA Việt Nam")
        "territory" — VN as a geographic location (e.g., "chiến tranh Ở Việt Nam")
        "ethnic"    — VN as ethnic identity (e.g., "người Việt", "dân tộc Việt")
        None        — VN not mentioned or no clear semantic role
    """
    for pat in _NATION_POSSESSIVE_PATTERNS:
        if pat.search(query):
            return "nation"

    for pat in _TERRITORY_LOCATIVE_PATTERNS:
        if pat.search(query):
            return "territory"

    for pat in _ETHNIC_PATTERNS:
        if pat.search(query):
            return "ethnic"

    # Default: if "việt nam" is mentioned but without clear markers → nation
    q_low = query.lower()
    if "việt nam" in q_low or "nước ta" in q_low or "tổ quốc" in q_low:
        return "nation"

    return None


# ===================================================================
# 2. STRUCTURAL REQUEST DETECTION
# ===================================================================

_DYNASTY_TIMELINE_PATTERNS = [
    re.compile(r"\bqua\s+các\s+triều\s+đại\b", re.I),
    re.compile(r"\btheo\s+(?:từng\s+)?triều\s+đại\b", re.I),
    re.compile(r"\bcác\s+triều\s+đại\b", re.I),
    re.compile(r"\btriều\s+đại\s+(?:việt\s*nam|nước\s+ta)\b", re.I),
    re.compile(r"\btừ\s+(?:thời\s+)?(?:ngô|đinh|tiền\s+lê|lý)\s+(?:đến|tới)\b", re.I),
    re.compile(r"\bcác\s+thời\s+kỳ\s+(?:lịch\s+sử|phong\s+kiến)\b", re.I),
]

_CHRONOLOGICAL_PATTERNS = [
    re.compile(r"\btheo\s+(?:thứ\s+tự\s+)?thời\s+gian\b", re.I),
    re.compile(r"\btừ\s+(?:đầu|xưa)\s+(?:đến|tới)\s+(?:nay|giờ)\b", re.I),
    re.compile(r"\bdiễn\s+biến\s+(?:qua|theo)\b", re.I),
]

_THEMATIC_PATTERNS = [
    re.compile(r"\bcác\s+(?:cuộc|mặt|lĩnh\s+vực|khía\s+cạnh)\b", re.I),
    re.compile(r"\bphân\s+(?:loại|nhóm)\b", re.I),
]


def detect_structure_request(query: str) -> str | None:
    """
    Detect if the user is requesting a specific answer structure.

    Returns:
        "dynasty_timeline" — Organize by dynasty chronological order
        "chronological"    — Organize by time (but not dynasty-specific)
        "thematic"         — Organize by theme/category
        None               — No specific structural request
    """
    for pat in _DYNASTY_TIMELINE_PATTERNS:
        if pat.search(query):
            return "dynasty_timeline"

    for pat in _CHRONOLOGICAL_PATTERNS:
        if pat.search(query):
            return "chronological"

    for pat in _THEMATIC_PATTERNS:
        if pat.search(query):
            return "thematic"

    return None


# ===================================================================
# 3. RESISTANCE / WAR INTENT DETECTION
# ===================================================================

_NATIONAL_RESISTANCE_PATTERNS = [
    # "Các cuộc kháng chiến (của VN)"
    re.compile(r"\bcác\s+cuộc\s+(?:kháng\s+chiến|chiến\s+tranh\s+(?:bảo\s+vệ|chống\s+ngoại\s+xâm))\b", re.I),
    # "kháng chiến chống ngoại xâm"
    re.compile(r"\bkháng\s+chiến\s+chống\s+(?:ngoại\s+xâm|giặc\s+ngoại|xâm\s+lược)\b", re.I),
    # "đánh đuổi giặc ngoại xâm"
    re.compile(r"\bđánh\s+đuổi\s+(?:giặc|quân)\s+(?:ngoại|xâm\s+lược)\b", re.I),
    # "bảo vệ độc lập dân tộc"
    re.compile(r"\bbảo\s+vệ\s+(?:độc\s+lập|chủ\s+quyền|tổ\s+quốc)\b", re.I),
    # "cuộc chiến giữ nước"
    re.compile(r"\b(?:cuộc\s+chiến|chiến\s+đấu)\s+giữ\s+nước\b", re.I),
    # "chống ngoại xâm"
    re.compile(r"\bchống\s+ngoại\s+xâm\b", re.I),
]

_TERRITORIAL_WAR_PATTERNS = [
    re.compile(r"\bchiến\s+tranh\s+(?:ở|tại|trên)\b", re.I),
    re.compile(r"\bxung\s+đột\s+(?:vũ\s+trang\s+)?(?:ở|tại|trên)\b", re.I),
    re.compile(r"\btrận\s+(?:chiến|đánh)\s+(?:ở|tại)\b", re.I),
]

_CIVIL_WAR_PATTERNS = [
    re.compile(r"\bnội\s+chiến\b", re.I),
    re.compile(r"\bphân\s+tranh\b", re.I),
    re.compile(r"\bchia\s+cắt\b", re.I),
    re.compile(r"\btranh\s+giành\s+(?:quyền\s+lực|ngôi\s+vua)\b", re.I),
]


# ===================================================================
# 4. CORE CLASSIFIER
# ===================================================================

def classify_semantic_intent(
    query: str,
    resolved_entities: dict | None = None
) -> SemanticIntent:
    """
    Core semantic intent classifier.

    Analyzes the query's linguistic structure (not just keywords) to determine:
    - What type of information the user wants
    - How "Việt Nam" is being used (nation vs territory)
    - What structure the answer should have

    Args:
        query: The rewritten query (with accents restored)
        resolved_entities: Dict from resolve_query_entities (optional)

    Returns:
        SemanticIntent with classified intent and retrieval strategy
    """
    resolved = resolved_entities or {}
    q_low = query.lower()

    # Detect dimensions
    vn_type = detect_vietnam_entity_type(query)
    structure = detect_structure_request(query)

    has_persons = bool(resolved.get("persons"))
    has_dynasties = bool(resolved.get("dynasties"))
    has_topics = bool(resolved.get("topics"))
    has_specific_entity = has_persons or has_topics

    # ---------------------------------------------------------------
    # INTENT 1: dynasty_timeline
    # "Lịch sử VN qua các triều đại" → structured by dynasty
    # ---------------------------------------------------------------
    if structure == "dynasty_timeline":
        return SemanticIntent(
            intent="dynasty_timeline",
            vietnam_scope=vn_type or "nation",
            structure="dynasty_timeline",
            confidence=0.95,
            retrieval_strategy="dynasty_scan_all",
            explanation="Yêu cầu trình bày theo cấu trúc triều đại"
        )

    # ---------------------------------------------------------------
    # INTENT 2: resistance_national
    # "Các cuộc kháng chiến của Việt Nam" → only external resistance
    # Must NOT have specific entity (otherwise it's a specific query)
    # ---------------------------------------------------------------
    if not has_specific_entity:
        for pat in _NATIONAL_RESISTANCE_PATTERNS:
            if pat.search(q_low):
                # Check for VN as nation (possessive) or default
                if vn_type in ("nation", None):
                    return SemanticIntent(
                        intent="resistance_national",
                        vietnam_scope="nation",
                        structure="chronological",
                        confidence=0.90,
                        retrieval_strategy="scan_national_resistance",
                        explanation="Các cuộc kháng chiến chống ngoại xâm (quốc gia–dân tộc)"
                    )

    # ---------------------------------------------------------------
    # INTENT 3: territorial_event
    # "Chiến tranh ở Việt Nam" → wars on VN soil (broader)
    # ---------------------------------------------------------------
    if vn_type == "territory":
        for pat in _TERRITORIAL_WAR_PATTERNS:
            if pat.search(q_low):
                return SemanticIntent(
                    intent="territorial_event",
                    vietnam_scope="territory",
                    structure="chronological",
                    confidence=0.85,
                    retrieval_strategy="scan_territorial_conflicts",
                    explanation="Các cuộc chiến tranh trên lãnh thổ Việt Nam"
                )

    # ---------------------------------------------------------------
    # INTENT 4: civil_war
    # "Nội chiến Việt Nam" / "Trịnh–Nguyễn phân tranh"
    # ---------------------------------------------------------------
    for pat in _CIVIL_WAR_PATTERNS:
        if pat.search(q_low):
            return SemanticIntent(
                intent="civil_war",
                vietnam_scope=vn_type,
                structure="chronological",
                confidence=0.85,
                retrieval_strategy="scan_civil_wars",
                explanation="Các cuộc nội chiến / phân tranh nội bộ"
            )

    # ---------------------------------------------------------------
    # INTENT 5: broad_history
    # "Lịch sử Việt Nam" (without structure request) → broad overview
    # ---------------------------------------------------------------
    if vn_type and not has_specific_entity:
        broad_patterns = [
            re.compile(r"\blịch\s+sử\s+(?:việt\s*nam|nước\s+ta|dân\s+tộc)\b", re.I),
            re.compile(r"\btoàn\s+bộ\s+lịch\s+sử\b", re.I),
            re.compile(r"\bsự\s+kiện\s+(?:lịch\s+sử\s+)?(?:nổi\s+bật|quan\s+trọng)\b", re.I),
        ]
        for pat in broad_patterns:
            if pat.search(q_low):
                return SemanticIntent(
                    intent="broad_history",
                    vietnam_scope=vn_type,
                    structure=structure or "chronological",
                    confidence=0.80,
                    retrieval_strategy="scan_broad_history",
                    explanation="Tổng quan lịch sử Việt Nam"
                )

    # ---------------------------------------------------------------
    # FALLBACK: No strong semantic signal → let engine use heuristics
    # ---------------------------------------------------------------
    return SemanticIntent(
        intent="generic",
        vietnam_scope=vn_type,
        structure=structure,
        confidence=0.3,
        retrieval_strategy="default",
        explanation="Không nhận dạng intent ngữ nghĩa cụ thể — dùng logic mặc định"
    )
