"""
answer_formatter.py — Rule-Based Answer Formatter (Phase 1 / Giai đoạn 11)

PURPOSE:
    Convert StructuredAnswer (JSON) → formatted Vietnamese text.
    KHÔNG chứa logic chọn data — chỉ format.

CONTEXT:
    - TRƯỚC ĐÂY: answer_synthesis.py vừa chọn data vừa format text
    - BÂY GIỜ: AnswerBuilder chọn data, AnswerFormatter chỉ format text
    - TƯƠNG LAI: Khi enable LLM rewrite, text này sẽ là base để LLM cải thiện

RELATED OLD FILES:
    - answer_synthesis.py → _build_when_answer() / _build_who_answer() / etc.
      (vẫn giữ làm fallback — module này ưu tiên trước)
    - engine.py → format_complete_answer() (legacy formatter — vẫn giữ)

PIPELINE POSITION:
    Answer Build → **Answer Format** → (Rewrite Layer) → Final Answer
"""

from typing import Optional

from app.core.query_schema import QueryInfo, StructuredAnswer


# Historical period names for context
_PERIODS = [
    ("Hùng Vương – Thời kỳ dựng nước", -2879, 111),
    ("Bắc thuộc", 111, 938),
    ("Thời kỳ phong kiến độc lập", 938, 1858),
    ("Pháp thuộc", 1858, 1945),
    ("Cách mạng tháng Tám & Kháng chiến chống Pháp", 1945, 1954),
    ("Kháng chiến chống Mỹ", 1954, 1975),
    ("Thống nhất – Đổi mới – Hiện đại", 1975, 2025),
]


def format_answer(
    structured: StructuredAnswer,
    query_info: QueryInfo,
) -> Optional[str]:
    """
    Main entry point: convert StructuredAnswer → formatted Vietnamese text.

    Routes by answer_type:
        fact_check → format_fact_check()
        person → format_person()
        year → format_year()
        event → format_event()
        list → format_list()
        dynasty → format_dynasty()

    Returns:
        Formatted text or None if insufficient data.
    """
    if not structured:
        return None

    if structured.answer_type == "fact_check":
        return _format_fact_check(structured)
    elif structured.answer_type == "person":
        return _format_person(structured)
    elif structured.answer_type == "year":
        return _format_year(structured)
    elif structured.answer_type == "list":
        return _format_list(structured)
    elif structured.answer_type == "dynasty":
        return _format_dynasty(structured)
    else:
        return _format_event(structured)


# ===================================================================
# FORMATTERS BY TYPE
# ===================================================================

def _format_fact_check(s: StructuredAnswer) -> Optional[str]:
    """
    Format fact-check answer: ✅ Đúng rồi! hoặc ❌ Không phải.

    Reuses logic from old answer_synthesis._build_fact_check_answer()
    but operates on StructuredAnswer instead of raw events.
    """
    if not s.description:
        return None

    if s.fact_check_result == "confirmed":
        return (
            f"✅ **Đúng rồi!** Sự kiện này diễn ra vào năm **{s.year}**.\n\n"
            f"{s.description}"
        )
    elif s.fact_check_result == "corrected":
        # Extract claimed year from detail
        parts = (s.fact_check_detail or "").split(", thực tế: ")
        claimed = parts[0].replace("User nêu: ", "") if parts else "?"
        return (
            f"❌ **Không phải năm {claimed}**, sự kiện này thực tế diễn ra "
            f"vào năm **{s.year}**.\n\n"
            f"{s.description}"
        )
    else:
        # No fact-check result — just provide info
        return (
            f"Theo dữ liệu lịch sử, sự kiện này diễn ra vào năm **{s.year}**.\n\n"
            f"{s.description}"
        )


def _format_person(s: StructuredAnswer) -> Optional[str]:
    """Format person-focused answer."""
    if not s.description:
        return None

    parts = []

    # Person name + year context
    if s.people and s.year:
        parts.append(f"**{s.people[0]}** — năm **{s.year}**:")
    elif s.people:
        parts.append(f"**{s.people[0]}**:")
    elif s.year:
        parts.append(f"Năm **{s.year}**:")

    parts.append(s.description)

    return "\n\n".join(parts)


def _format_year(s: StructuredAnswer) -> Optional[str]:
    """Format year-focused answer (when question) — concise."""
    if not s.year or not s.description:
        return None

    period = _get_period(s.year)
    period_note = f" ({period})" if period else ""

    return (
        f"Năm **{s.year}**{period_note}, "
        f"{s.description}"
    )


def _format_event(s: StructuredAnswer) -> Optional[str]:
    """Format generic event answer."""
    if not s.description:
        return None

    parts = []

    # Title + year header
    if s.title and s.year:
        parts.append(f"**{s.title}** (năm {s.year}):")
    elif s.title:
        parts.append(f"**{s.title}**:")
    elif s.year:
        parts.append(f"Năm **{s.year}**:")

    parts.append(s.description)

    # Additional items (if multiple events)
    if s.items and len(s.items) > 1:
        parts.append("")
        for item in s.items[1:5]:  # Skip first (already shown in main description)
            item_year = item.get("year", "")
            item_title = item.get("title", "")
            item_story = item.get("story", "")
            if item_year and item_title:
                parts.append(f"- **Năm {item_year}**: {item_title}")
            elif item_title:
                parts.append(f"- {item_title}")

    return "\n".join(parts)


def _format_list(s: StructuredAnswer) -> Optional[str]:
    """Format list answer with period grouping."""
    if not s.items:
        return None

    parts = []

    # Group by period if year range
    if s.year_range:
        start, end = s.year_range
        parts.append(f"**Các sự kiện từ năm {start} đến {end}:**\n")

    for item in s.items:
        year = item.get("year", "")
        title = item.get("title", "")
        story = item.get("story", "")

        if year and title:
            parts.append(f"- **Năm {year}**: {title}")
        elif title:
            parts.append(f"- {title}")

    return "\n".join(parts)


def _format_dynasty(s: StructuredAnswer) -> Optional[str]:
    """Format dynasty-focused answer."""
    if not s.items and not s.description:
        return None

    parts = []

    if s.dynasty:
        parts.append(f"**{s.dynasty}**:\n")

    if s.description:
        parts.append(s.description)

    if s.items:
        parts.append("")
        for item in s.items:
            year = item.get("year", "")
            title = item.get("title", "")
            if year and title:
                parts.append(f"- **Năm {year}**: {title}")
            elif title:
                parts.append(f"- {title}")

    return "\n".join(parts)


# ===================================================================
# HELPERS
# ===================================================================

def _get_period(year: int) -> Optional[str]:
    """Map year to historical period name."""
    for name, start, end in _PERIODS:
        if start <= year <= end:
            return name
    return None
