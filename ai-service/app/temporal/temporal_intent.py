"""
temporal_intent.py — Temporal query intent classification.

Extends the existing intent_classifier.py with temporal-specific intents.
These intents trigger the TemporalEngine instead of RAG retrieval.

Design principle:
    Temporal queries should SKIP semantic search entirely —
    they are solved by pure deterministic logic on metadata indexes.
"""

from enum import Enum
from typing import Optional


class TemporalIntent(str, Enum):
    """Temporal-specific query intents."""

    DURATION_MAX = "duration_max"       # "Triều đại nào lâu nhất?"
    DURATION_MIN = "duration_min"       # "Triều đại nào ngắn nhất?"
    COMPARE = "compare"                 # "Ai trị vì lâu hơn, A hay B?"
    BEFORE_AFTER = "before_after"       # "Sự kiện nào trước khởi nghĩa Lam Sơn?"
    OVERLAP = "overlap"                 # "Sự kiện nào diễn ra cùng thời?"
    REIGN_DURATION = "reign_duration"   # "Ông trị vì bao lâu?"


# Temporal intent keywords for detection
TEMPORAL_KEYWORDS = {
    "lâu nhất": TemporalIntent.DURATION_MAX,
    "dài nhất": TemporalIntent.DURATION_MAX,
    "ngắn nhất": TemporalIntent.DURATION_MIN,
    "nhanh nhất": TemporalIntent.DURATION_MIN,
    "trước": TemporalIntent.BEFORE_AFTER,
    "sau": TemporalIntent.BEFORE_AFTER,
    "cùng thời": TemporalIntent.OVERLAP,
    "song song": TemporalIntent.OVERLAP,
    "so sánh": TemporalIntent.COMPARE,
    "lâu hơn": TemporalIntent.COMPARE,
    "ngắn hơn": TemporalIntent.COMPARE,
    "trị vì bao lâu": TemporalIntent.REIGN_DURATION,
    "tồn tại bao lâu": TemporalIntent.REIGN_DURATION,
}


def detect_temporal_intent(query: str) -> Optional[TemporalIntent]:
    """
    Detect if query has a temporal reasoning intent.

    Args:
        query: User query string (lowercase recommended).

    Returns:
        TemporalIntent if detected, None otherwise.
    """
    query_lower = query.lower()
    for keyword, intent in TEMPORAL_KEYWORDS.items():
        if keyword in query_lower:
            return intent
    return None
