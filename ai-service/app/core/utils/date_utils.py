# date_utils.py — Centralized date-safe utilities
#
# Prevents sort crashes when year field is corrupted (None, "", [], True, "invalid").
# Used across search_service.py, engine.py, answer_synthesis.py.

from typing import Any, Optional


def safe_year(
    value: Any,
    default: int = 9999,
    allow_negative: bool = True,
    max_year: Optional[int] = None,
) -> int:
    """
    Safely convert a raw year value to int.

    Handles corrupted data: None, "", bool, list, dict, "invalid", etc.
    Python's int(True)==1 and int(False)==0 — both are guarded here.

    Parameters:
        value: raw year from document (may be int, str, None, bool, etc.)
        default: fallback value when conversion fails
        allow_negative: whether to permit BCE years (negative ints)
        max_year: optional upper bound; values above are replaced with default

    Returns:
        int year suitable for sorting and comparison
    """
    # Guard: bool is a subclass of int in Python — True→1, False→0
    # This is almost never a valid year, so reject it explicitly
    if isinstance(value, bool):
        return default

    try:
        year = int(value)
    except (TypeError, ValueError):
        return default

    if not allow_negative and year < 0:
        return default

    if max_year is not None and year > max_year:
        return default

    return year
