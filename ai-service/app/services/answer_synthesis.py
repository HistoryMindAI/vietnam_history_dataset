"""
answer_synthesis.py — Template-Based Answer Synthesis V2

Generates focused, semantic answers instead of data dumps.
Uses question_type from QueryAnalysis to control verbosity.

Principles:
- When-question → year + brief context (no data dump)
- Who-question → person bio + key events
- What-question → event description, focused
- List-question → chronological with period grouping
- Scope-question → dynamic min/max from data
"""
import app.core.startup as startup
from app.services.intent_classifier import QueryAnalysis


# ===================================================================
# PERIOD GROUPING (Principle 4)
# ===================================================================

HISTORICAL_PERIODS = [
    ("Thời Bắc thuộc", 40, 938),
    ("Thời Ngô – Đinh – Tiền Lê", 939, 1009),
    ("Thời Lý", 1009, 1225),
    ("Thời Trần", 1225, 1400),
    ("Thời Hồ", 1400, 1407),
    ("Thời Lê sơ", 1428, 1527),
    ("Thời Mạc – Lê Trung Hưng", 1527, 1789),
    ("Thời Tây Sơn", 1789, 1802),
    ("Thời Nguyễn", 1802, 1945),
    ("Pháp thuộc", 1858, 1945),
    ("Cách mạng tháng Tám & Kháng chiến chống Pháp", 1945, 1954),
    ("Kháng chiến chống Mỹ", 1954, 1975),
    ("Thống nhất – Đổi mới – Hiện đại", 1975, 2025),
]


def _get_period_for_year(year: int) -> str:
    """Map a year to its historical period name."""
    for name, start, end in HISTORICAL_PERIODS:
        if start <= year <= end:
            return name
    return "Khác"


# ===================================================================
# DATA SCOPE HANDLER (Principle 5)
# ===================================================================

def _handle_data_scope() -> str:
    """
    Generate dynamic answer about data coverage.
    Uses actual min/max years from loaded documents.
    """
    docs = getattr(startup, "DOCUMENTS", [])
    if not docs:
        return (
            "Tôi có dữ kiện lịch sử Việt Nam từ năm 40 "
            "(khởi nghĩa Hai Bà Trưng) đến năm 2025, "
            "bao gồm các giai đoạn cổ đại, trung đại, cận đại và hiện đại."
        )

    years = [d.get("year", 0) for d in docs if d.get("year")]
    if not years:
        return (
            "Tôi có dữ kiện lịch sử Việt Nam bao gồm các giai đoạn "
            "cổ đại, trung đại, cận đại và hiện đại."
        )

    min_year = min(years)
    max_year = max(years)
    total_docs = len(docs)

    return (
        f"Tôi có dữ kiện lịch sử Việt Nam từ năm **{min_year}** "
        f"(khởi nghĩa Hai Bà Trưng) đến năm **{max_year}**, "
        f"với **{total_docs}** sự kiện được lưu trữ.\n\n"
        f"Dữ liệu bao gồm các giai đoạn:\n"
        f"- Cổ đại: Bắc thuộc, Ngô – Đinh – Tiền Lê\n"
        f"- Trung đại: Lý – Trần – Lê\n"
        f"- Cận đại: Nguyễn, Pháp thuộc\n"
        f"- Hiện đại: Cách mạng, Kháng chiến, Đổi mới\n\n"
        f"Bạn có thể hỏi về bất kỳ sự kiện, nhân vật, hoặc triều đại nào!"
    )


# ===================================================================
# ANSWER BUILDERS BY QUESTION TYPE
# ===================================================================

def _build_when_answer(events: list, analysis: QueryAnalysis) -> str | None:
    """
    Build focused answer for 'when' questions.
    Returns ONLY the year + brief context. No data dump.

    Example: "Bác Hồ ra đi tìm đường cứu nước năm nào?"
    → "Năm 1911, Nguyễn Tất Thành rời Bến Nhà Rồng ra đi tìm đường cứu nước."
    """
    if not events:
        return None

    # For 'when' questions, pick the best matching event
    best = events[0]
    year = best.get("year")
    story = (best.get("story") or best.get("event") or "").strip()
    title = (best.get("title") or "").strip()

    if year and story:
        # Clean up story to be a complete sentence
        text = story if len(story) > len(title) else title + ": " + story
        return f"Năm **{year}**, {text}"
    elif year:
        return f"Năm **{year}**."
    elif story:
        return story
    return None


def _build_who_answer(events: list, analysis: QueryAnalysis) -> str | None:
    """
    Build answer for 'who' questions about a person.
    Focuses on the person's identity and key achievements.
    """
    if not events:
        return None

    parts = []
    seen_texts = set()

    for e in events[:5]:  # Limit to 5 most relevant
        story = (e.get("story") or "").strip()
        if not story or story.lower() in seen_texts:
            continue
        seen_texts.add(story.lower())

        year = e.get("year")
        if year:
            parts.append(f"**Năm {year}:** {story}")
        else:
            parts.append(story)

    return "\n\n".join(parts) if parts else None


def _build_list_answer(events: list, analysis: QueryAnalysis) -> str | None:
    """
    Build chronological list answer with period grouping.
    Used for range queries, broad queries, and 'list' questions.

    Groups events by historical period for readability.
    """
    if not events:
        return None

    # Check if range covers a large span (use period grouping)
    years = [e.get("year", 0) for e in events if e.get("year")]
    if not years:
        # No years → just list events
        return _build_simple_list(events)

    min_yr, max_yr = min(years), max(years)
    span = max_yr - min_yr

    if span > 200:
        return _build_period_grouped_list(events)
    else:
        return _build_simple_list(events)


def _build_period_grouped_list(events: list) -> str:
    """Group events by historical period (Principle 4)."""
    grouped: dict[str, list] = {}
    for e in events:
        year = e.get("year", 0)
        if year:
            period = _get_period_for_year(year)
        else:
            period = "Khác"
        grouped.setdefault(period, []).append(e)

    parts = []
    for period_name, start, end in HISTORICAL_PERIODS:
        if period_name in grouped:
            items = grouped[period_name]
            items.sort(key=lambda x: x.get("year", 0))
            part_lines = [f"### {period_name} ({start}–{end})"]
            seen = set()
            for e in items:
                year = e.get("year", 0)
                story = (e.get("story") or e.get("event") or "").strip()
                if not story or story.lower() in seen:
                    continue
                seen.add(story.lower())
                if year:
                    part_lines.append(f"- **Năm {year}:** {story}")
                else:
                    part_lines.append(f"- {story}")
            parts.append("\n".join(part_lines))

    # Add "Khác" if any
    if "Khác" in grouped:
        other_lines = ["### Khác"]
        for e in grouped["Khác"]:
            story = (e.get("story") or e.get("event") or "").strip()
            if story:
                other_lines.append(f"- {story}")
        parts.append("\n".join(other_lines))

    return "\n\n".join(parts) if parts else None


def _build_simple_list(events: list) -> str:
    """Simple chronological list without period grouping."""
    parts = []
    seen = set()
    for e in events:
        story = (e.get("story") or e.get("event") or "").strip()
        if not story or story.lower() in seen:
            continue
        seen.add(story.lower())
        year = e.get("year", 0)
        if year:
            parts.append(f"**Năm {year}:** {story}")
        else:
            parts.append(story)

    return "\n\n".join(parts) if parts else None


def _build_what_answer(events: list, analysis: QueryAnalysis) -> str | None:
    """
    Build focused answer for 'what' questions about events.
    Includes the event description with context.
    """
    if not events:
        return None

    parts = []
    seen = set()
    for e in events[:7]:
        story = (e.get("story") or "").strip()
        title = (e.get("title") or "").strip()
        if not story or story.lower() in seen:
            continue
        seen.add(story.lower())

        year = e.get("year", 0)
        if year:
            parts.append(f"**Năm {year}:** {story}")
        elif title:
            parts.append(f"**{title}:** {story}")
        else:
            parts.append(story)

    return "\n\n".join(parts) if parts else None


# ===================================================================
# CORE SYNTHESIS FUNCTION
# ===================================================================

def synthesize_answer(analysis: QueryAnalysis, events: list) -> str | None:
    """
    Main answer synthesis entry point.

    Internal logic (Principle 7 — NOT printed):
    1. Check for data_scope intent → direct meta-answer
    2. Route by question_type → focused builder
    3. Apply duration guard warnings
    """
    # Data scope → no events needed
    if analysis.intent == "data_scope":
        return _handle_data_scope()

    if not events:
        return None

    # Route by question type
    qtype = analysis.question_type

    if qtype == "when":
        answer = _build_when_answer(events, analysis)
    elif qtype == "who":
        answer = _build_who_answer(events, analysis)
    elif qtype == "list":
        answer = _build_list_answer(events, analysis)
    elif qtype == "scope":
        answer = _handle_data_scope()
    else:
        answer = _build_what_answer(events, analysis)

    return answer
