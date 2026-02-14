"""
intent_classifier.py — Intent Classification V2

Structured query analysis with 10 intent types, duration guard,
and question-type detection.

Replaces semantic_intent.py with more granular classification.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


# ===================================================================
# QUERY ANALYSIS RESULT
# ===================================================================

@dataclass
class QueryAnalysis:
    """Result of intent classification."""
    intent: str                          # One of 10 intents
    focus: str = "event"                 # "year" | "event" | "person" | "scope" | "composite"
    entities: dict = field(default_factory=dict)  # Resolved entities
    duration_guard: bool = False         # True if "X năm" is duration, NOT year
    year: Optional[int] = None           # Extracted single year
    year_range: Optional[tuple] = None   # (start, end) if range query
    question_type: str = "what"          # "when" | "what" | "who" | "list" | "scope"
    confidence: float = 0.0
    explanation: str = ""


# ===================================================================
# 1. DURATION / ANNIVERSARY GUARD  (Principle 2)
# ===================================================================
# Patterns where a number followed by "năm" is a DURATION, not a year.

_DURATION_PATTERNS = [
    # "hơn 150 năm", "gần 100 năm", "khoảng 200 năm"
    re.compile(r"\b(?:hơn|gần|khoảng|suốt|trải qua|qua)\s+(\d+)\s*năm\b", re.I),
    # "kỷ niệm 1000 năm", "kỉ niệm 1000 năm"
    re.compile(r"\bk[ỷỉ]\s*ni[ệe]m\s+(\d+)\s*năm\b", re.I),
    # "tròn 100 năm"
    re.compile(r"\btròn\s+(\d+)\s*năm\b", re.I),
    # "150 năm chia cắt", "1000 năm Thăng Long"
    re.compile(r"\b(\d+)\s*năm\s+(?:chia\s*cắt|tồn\s*tại|thống\s*trị|đô\s*hộ|"
               r"thăng\s*long|lịch\s*sử|xây\s*dựng|phát\s*triển|đấu\s*tranh)", re.I),
    # "X năm kể từ", "X năm sau"
    re.compile(r"\b(\d+)\s*năm\s+(?:kể\s*từ|sau|trước)\b", re.I),
]


def detect_duration_guard(query: str) -> bool:
    """
    Check if query contains patterns where a number + "năm" means
    a duration/anniversary, NOT a historical year.

    Examples:
        "kỷ niệm 1000 năm Thăng Long" → True (1000 is duration)
        "hơn 150 năm chia cắt" → True (150 is duration)
        "năm 1000" → False (explicit year marker)
        "năm 1945 có gì" → False (standard year query)
    """
    q = query.strip()
    for pattern in _DURATION_PATTERNS:
        if pattern.search(q):
            return True
    return False


# ===================================================================
# 2. QUESTION TYPE DETECTION  (Principle 3)
# ===================================================================

_WHEN_PATTERNS = [
    re.compile(r"\bnăm\s+(?:bao\s*nhiêu|nào|mấy)\b", re.I),
    re.compile(r"\bkhi\s+nào\b", re.I),
    re.compile(r"\bxảy\s+ra\s+(?:vào\s+)?(?:năm|khi|lúc)\b", re.I),
    re.compile(r"\bnăm\s+(?:mấy|nào)\s+(?:xảy\s+ra|diễn\s+ra)\b", re.I),
    re.compile(r"\bvào\s+(?:thời\s+)?(?:gian|điểm)\s+nào\b", re.I),
    re.compile(r"\bwhen\b", re.I),
    re.compile(r"\bnam\s+(?:bao\s*nhieu|nao|may)\b", re.I),  # unaccented
]

_WHO_PATTERNS = [
    re.compile(r"\blà\s+ai\b", re.I),
    re.compile(r"\bai\s+là\b", re.I),
    re.compile(r"\bla\s+ai\b", re.I),  # unaccented
    re.compile(r"\bwho\s+(?:is|was)\b", re.I),
    re.compile(r"\bnhân\s+vật\s+nào\b", re.I),
]

_LIST_PATTERNS = [
    re.compile(r"\bcác\s+(?:sự\s+kiện|cuộc|trận|triều\s+đại|nhân\s+vật)\b", re.I),
    re.compile(r"\bnhững\s+(?:sự\s+kiện|gì|ai)\b", re.I),
    re.compile(r"\bkể\s+(?:tên|về|ra)\b", re.I),
    re.compile(r"\bliệt\s+kê\b", re.I),
    re.compile(r"\bcó\s+(?:những\s+)?(?:gì|sự\s+kiện\s+gì)\b", re.I),
    re.compile(r"\btóm\s+tắt\b", re.I),
    re.compile(r"\blịch\s+sử\b", re.I),
]

_SCOPE_PATTERNS = [
    re.compile(r"\bcó\s+dữ\s*(?:liệu|kiện)\b", re.I),
    re.compile(r"\bdataset\b", re.I),
    re.compile(r"\bbao\s+phủ\b", re.I),
    re.compile(r"\bphạm\s+vi\b", re.I),
    re.compile(r"\btừ\s+năm\s+(?:bao\s*nhiêu|nào)\s+đến\b", re.I),
    re.compile(r"\bbiết\s+(?:về\s+)?(?:từ|đến)\s+năm\s+nào\b", re.I),
    re.compile(r"\bcó\s+lịch\s+sử\s+(?:đến|từ)\b", re.I),
]


def detect_question_type(query: str) -> str:
    """
    Classify question type to control answer verbosity.

    Returns: "when" | "who" | "what" | "list" | "scope"
    """
    q = query.strip()

    # Check scope FIRST (most specific)
    for p in _SCOPE_PATTERNS:
        if p.search(q):
            return "scope"

    # Check when
    for p in _WHEN_PATTERNS:
        if p.search(q):
            return "when"

    # Check who
    for p in _WHO_PATTERNS:
        if p.search(q):
            return "who"

    # Check list
    for p in _LIST_PATTERNS:
        if p.search(q):
            return "list"

    # Default
    return "what"


# ===================================================================
# 3. DATA SCOPE DETECTION  (Principle 5)
# ===================================================================

_DATA_SCOPE_PATTERNS = [
    re.compile(r"\bcó\s+dữ\s*(?:liệu|kiện)\s+(?:từ|gì|về|nào)\b", re.I),
    re.compile(r"\bdữ\s*(?:liệu|kiện)\s+(?:của\s+)?bạn\b", re.I),
    re.compile(r"\bbạn\s+(?:có\s+)?(?:biết|có)\s+(?:dữ|lịch\s+sử)\b", re.I),
    re.compile(r"\bdataset\s+(?:của|bạn)\b", re.I),
    re.compile(r"\bphạm\s+vi\s+(?:dữ\s*liệu|kiến\s+thức)\b", re.I),
    re.compile(r"\bcó\s+lịch\s+sử\s+đến\s+năm\b", re.I),
    re.compile(r"\bbiết\s+(?:từ|đến)\s+năm\s+nào\b", re.I),
]


def is_data_scope_query(query: str) -> bool:
    """Check if user is asking about the AI's data coverage."""
    q = query.strip()
    for p in _DATA_SCOPE_PATTERNS:
        if p.search(q):
            return True
    return False


# ===================================================================
# 4. RELATIONSHIP DETECTION
# ===================================================================

_RELATIONSHIP_PATTERNS_RE = [
    re.compile(r"\blà\s+gì\s+của\s+nhau\b", re.I),
    re.compile(r"\bcó\s+quan\s+hệ\s+gì\b", re.I),
    re.compile(r"\bliên\s+quan\s+gì\b", re.I),
    re.compile(r"\blà\s+ai\s+của\b", re.I),
    # unaccented
    re.compile(r"\bla\s+gi\s+cua\s+nhau\b", re.I),
    re.compile(r"\bco\s+quan\s+he\s+gi\b", re.I),
]

_DEFINITION_PATTERNS_RE = [
    re.compile(r"\blà\s+(?:gì|ai)\b", re.I),
    re.compile(r"\bla\s+(?:gi|ai)\b", re.I),
]


# ===================================================================
# 5. CORE CLASSIFIER
# ===================================================================

def classify_intent(
    query: str,
    resolved_entities: dict | None = None,
    year: int | None = None,
    year_range: tuple | None = None,
    multi_years: list | None = None,
) -> QueryAnalysis:
    """
    Core intent classifier — determines what the user is asking.

    Args:
        query: Rewritten (normalized) query
        resolved_entities: Output from resolve_query_entities()
        year: Extracted single year (from engine)
        year_range: Extracted year range (from engine)
        multi_years: Extracted multiple years (from engine)

    Returns:
        QueryAnalysis with intent, focus, question_type, guards
    """
    resolved = resolved_entities or {}
    q = query.lower().strip()

    has_persons = bool(resolved.get("persons"))
    has_topics = bool(resolved.get("topics"))
    has_dynasties = bool(resolved.get("dynasties"))
    has_places = bool(resolved.get("places"))
    has_entities = has_persons or has_topics or has_dynasties or has_places

    # --- Guard layers ---
    duration = detect_duration_guard(query)
    qtype = detect_question_type(query)

    # Base analysis
    analysis = QueryAnalysis(
        intent="semantic",
        entities=resolved,
        duration_guard=duration,
        question_type=qtype,
        year=year if not duration else None,       # Guard: don't use year if duration
        year_range=year_range,
    )

    # --- Intent classification (priority order) ---

    # 1. Data scope query (Principle 5)
    if is_data_scope_query(query):
        analysis.intent = "data_scope"
        analysis.focus = "scope"
        analysis.question_type = "scope"
        analysis.confidence = 0.95
        analysis.explanation = "User asking about data coverage"
        return analysis

    # 2. Year range
    if year_range:
        analysis.intent = "year_range"
        analysis.focus = "composite"
        analysis.question_type = "list"
        analysis.confidence = 0.9
        analysis.explanation = f"Year range: {year_range[0]}–{year_range[1]}"
        return analysis

    # 3. Multiple years
    if multi_years:
        analysis.intent = "year_range"
        analysis.focus = "composite"
        analysis.question_type = "list"
        analysis.year_range = (min(multi_years), max(multi_years))
        analysis.confidence = 0.85
        analysis.explanation = f"Multiple years: {multi_years}"
        return analysis

    # 4. Relationship query (must check BEFORE definition)
    is_relationship = any(p.search(q) for p in _RELATIONSHIP_PATTERNS_RE)
    is_definition = any(p.search(q) for p in _DEFINITION_PATTERNS_RE)

    if is_relationship and (has_persons or has_topics):
        analysis.intent = "relationship"
        analysis.focus = "person"
        analysis.confidence = 0.9
        analysis.explanation = "Relationship/same-entity query"
        return analysis

    # 5. Definition query ("X là ai?", "X là gì?")
    if is_definition and has_persons:
        analysis.intent = "definition"
        analysis.focus = "person"
        analysis.question_type = "who"
        analysis.confidence = 0.85
        analysis.explanation = "Who/what definition query"
        return analysis

    # 6. Person-focused query (when question asks about a specific person)
    if has_persons and not has_dynasties and not has_topics:
        analysis.intent = "person_query"
        analysis.focus = "person"
        analysis.confidence = 0.85
        # Detect if asking "when" about a person
        if qtype == "when":
            analysis.explanation = "Person + when → year-focused person query"
        else:
            analysis.explanation = f"Person query: {resolved.get('persons', [])}"
        return analysis

    # 7. Dynasty query
    if has_dynasties and not has_persons:
        # Check for dynasty timeline / broad
        _dynasty_timeline_patterns = [
            re.compile(r"\bcác\s+triều\s+đại\b", re.I),
            re.compile(r"\bqua\s+các\s+(?:thời\s+kỳ|triều\s+đại|giai\s+đoạn)\b", re.I),
            re.compile(r"\bdiễn\s+biến\s+(?:qua|theo)\b", re.I),
            re.compile(r"\btheo\s+(?:thứ\s+tự\s+)?triều\s+đại\b", re.I),
        ]
        is_timeline = any(p.search(q) for p in _dynasty_timeline_patterns)

        if is_timeline:
            analysis.intent = "dynasty_timeline"
            analysis.focus = "composite"
            analysis.question_type = "list"
            analysis.confidence = 0.9
            analysis.explanation = "Dynasty timeline request"
        else:
            analysis.intent = "dynasty_query"
            analysis.focus = "event"
            analysis.question_type = qtype
            analysis.confidence = 0.85
            analysis.explanation = f"Dynasty query: {resolved.get('dynasties', [])}"
        return analysis

    # 8. Event/topic query
    if has_topics:
        analysis.intent = "event_query"
        analysis.focus = "event"
        analysis.confidence = 0.8
        analysis.explanation = f"Event/topic query: {resolved.get('topics', [])}"
        return analysis

    # 9. Broad history / resistance patterns
    _broad_patterns = [
        re.compile(r"\blịch\s+sử\s+(?:việt\s*nam|nước\s+ta|dân\s+tộc)\b", re.I),
        re.compile(r"\bcác\s+(?:cuộc|trận)\s+(?:kháng\s+chiến|chiến\s+tranh)\b", re.I),
        re.compile(r"\btoàn\s+bộ\s+lịch\s+sử\b", re.I),
    ]
    _resistance_patterns = [
        re.compile(r"\bkháng\s+chiến\b", re.I),
        re.compile(r"\bchống\s+(?:ngoại\s+xâm|giặc)\b", re.I),
        re.compile(r"\bgiữ\s+nước\b", re.I),
        re.compile(r"\bbảo\s+vệ\s+(?:tổ\s+quốc|đất\s+nước)\b", re.I),
    ]

    is_broad = any(p.search(q) for p in _broad_patterns)
    is_resistance = any(p.search(q) for p in _resistance_patterns)

    if is_broad:
        analysis.intent = "broad_history"
        analysis.focus = "composite"
        analysis.question_type = "list"
        analysis.confidence = 0.85
        analysis.explanation = "Broad Vietnamese history query"
        return analysis

    if is_resistance:
        analysis.intent = "event_query"
        analysis.focus = "event"
        analysis.question_type = "list"
        analysis.confidence = 0.8
        analysis.explanation = "Resistance/war query"
        return analysis

    # 10. Single year query (with duration guard)
    if year and not duration:
        analysis.intent = "year_specific"
        analysis.focus = "year"
        analysis.confidence = 0.85
        analysis.explanation = f"Year query: {year}"
        return analysis

    # 11. Fallback: semantic search
    analysis.intent = "semantic"
    analysis.focus = "event"
    analysis.confidence = 0.5
    analysis.explanation = "Fallback to semantic search"
    return analysis
