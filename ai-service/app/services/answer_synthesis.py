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
from rapidfuzz import fuzz
from app.services.intent_classifier import QueryAnalysis
from app.services.event_aggregator import normalize_for_dedup
from app.services.answer_postprocessor import _extract_year_from_text
from app.core.utils.date_utils import safe_year


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
    Adapts verbosity based on analysis.detail_level:
    - brief: year only
    - standard: year + brief context
    - detailed: year + date + location + full context

    Example: "Bác Hồ ra đi tìm đường cứu nước năm nào?"
    → brief:    "Năm 1911."
    → standard: "Năm 1911, Nguyễn Tất Thành rời Bến Nhà Rồng ra đi tìm đường cứu nước."
    → detailed: "Ngày 5/6/1911, Nguyễn Tất Thành rời Bến Nhà Rồng (Sài Gòn) trên tàu
                  Latouche-Tréville, bắt đầu hành trình tìm đường cứu nước."
    """
    if not events:
        return None

    detail = getattr(analysis, "detail_level", "standard")

    # For 'when' questions, pick the best matching event
    best = events[0]
    year = best.get("year")
    story = (best.get("story") or best.get("event") or "").strip()
    title = (best.get("title") or "").strip()
    places = best.get("places", [])
    persons = best.get("persons", [])

    if detail == "brief":
        # Minimal: just the year
        if year:
            return f"Năm **{year}**."
        elif story:
            return story
        return None

    if detail == "detailed" and year and story:
        # Rich: include location and persons metadata if available
        text = story if len(story) > len(title) else title + ": " + story
        parts = [f"Năm **{year}**"]
        if places:
            parts.append(f" (tại {', '.join(places[:2])})")
        parts.append(f", {text}")
        return "".join(parts)

    # Standard: year + brief context
    if year and story:
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
    Validates each event mentions the target person (grounding).
    """
    if not events:
        return None

    # Extract target persons for grounding validation
    target_persons = [p.lower() for p in analysis.entities.get("persons", [])]

    parts = []
    seen_norm: list[str] = []  # Fuzzy dedup via normalize_for_dedup

    for e in events[:5]:  # Limit to 5 most relevant
        story = (e.get("story") or "").strip()
        if not story:
            continue

        # Fuzzy dedup check (replaces exact story.lower() match)
        normalized = normalize_for_dedup(story)
        if any(
            normalized == prev or normalized in prev or prev in normalized
            or fuzz.token_set_ratio(normalized, prev) >= 80.0
            for prev in seen_norm
        ):
            continue

        # GROUNDING CHECK: Skip events that don't mention target person
        if target_persons:
            event_persons = [p.lower() for p in (e.get("persons") or [])]
            story_lower = story.lower()

            # Check if event mentions any target person
            mentions_target = any(
                person in event_persons or person in story_lower
                for person in target_persons
            )

            if not mentions_target:
                continue  # Skip unrelated events

        seen_norm.append(normalized)

        year = e.get("year")
        if not year:
            year = _extract_year_from_text(story)
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
    """Group events by historical period (Principle 4).
    Uses GLOBAL cross-period dedup to catch same event across periods."""
    grouped: dict[str, list] = {}
    for e in events:
        year = e.get("year", 0)
        if year:
            period = _get_period_for_year(year)
        else:
            period = "Khác"
        grouped.setdefault(period, []).append(e)

    parts = []
    # GLOBAL seen set across ALL periods (Gap #2 fix)
    global_seen: list[str] = []
    for period_name, start, end in HISTORICAL_PERIODS:
        if period_name in grouped:
            items = grouped[period_name]
            items.sort(key=lambda x: safe_year(x.get("year"), default=0))
            part_lines = [f"### {period_name} ({start}–{end})"]
            for e in items:
                year = e.get("year", 0)
                story = (e.get("story") or e.get("event") or "").strip()
                if not story:
                    continue
                normalized = normalize_for_dedup(story)
                # Cross-period fuzzy dedup
                if any(
                    normalized == prev or normalized in prev or prev in normalized
                    or fuzz.token_set_ratio(normalized, prev) >= 80.0
                    for prev in global_seen
                ):
                    continue
                global_seen.append(normalized)
                if not year:
                    year = _extract_year_from_text(story)
                if year:
                    part_lines.append(f"- **Năm {year}:** {story}")
                else:
                    part_lines.append(f"- {story}")
            if len(part_lines) > 1:  # Only add period if it has events
                parts.append("\n".join(part_lines))

    # Add "Khác" if any
    if "Khác" in grouped:
        other_lines = ["### Khác"]
        for e in grouped["Khác"]:
            story = (e.get("story") or e.get("event") or "").strip()
            if story:
                normalized = normalize_for_dedup(story)
                if not any(
                    normalized == prev or normalized in prev or prev in normalized
                    or fuzz.token_set_ratio(normalized, prev) >= 80.0
                    for prev in global_seen
                ):
                    global_seen.append(normalized)
                    other_lines.append(f"- {story}")
        if len(other_lines) > 1:
            parts.append("\n".join(other_lines))

    return "\n\n".join(parts) if parts else None


def _build_simple_list(events: list) -> str:
    """Simple chronological list without period grouping."""
    parts = []
    seen = set()
    for e in events:
        story = (e.get("story") or e.get("event") or "").strip()
        if not story:
            continue
        normalized = normalize_for_dedup(story)
        if normalized in seen:
            continue
        seen.add(normalized)
        year = e.get("year", 0)
        if not year:
            year = _extract_year_from_text(story)
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
        if not story:
            continue
        normalized = normalize_for_dedup(story)
        if normalized in seen:
            continue
        seen.add(normalized)

        year = e.get("year", 0)
        if not year:
            year = _extract_year_from_text(story)
        if year:
            parts.append(f"**Năm {year}:** {story}")
        elif title:
            parts.append(f"**{title}:** {story}")
        else:
            parts.append(story)

    return "\n\n".join(parts) if parts else None


# ===================================================================
# FACT-CHECK ANSWER BUILDER
# ===================================================================

def _build_fact_check_answer(events: list, analysis: QueryAnalysis) -> str | None:
    """
    Build fact-check response: confirm or correct user's factual claim.

    Logic:
    1. User claims an event happened in year X
    2. We find the actual event → get actual year
    3. If X == actual → confirm ("Đúng rồi!")
    4. If X != actual → correct ("Không, sự kiện này diễn ra năm Y, không phải X")

    Examples:
        "Bác Hồ ra đi năm 1991 phải không?" → "Không phải, ... năm 1911 ..."
        "Bác Hồ đọc tuyên ngôn năm 1945 đúng không?" → "Đúng rồi! ..."
    """
    if not events:
        return None

    best = events[0]
    actual_year = best.get("year")
    claimed_year = analysis.fact_check_year
    story = (best.get("story") or best.get("event") or "").strip()

    # Coerce actual_year to int for comparison (may be stored as str in some events)
    if actual_year is not None:
        try:
            actual_year = int(actual_year)
        except (ValueError, TypeError):
            actual_year = None

    if not actual_year or not story:
        return None

    if claimed_year is None:
        # User asked for confirmation but didn't specify a year → just answer
        return f"Theo dữ liệu lịch sử, sự kiện này diễn ra vào năm **{actual_year}**.\n\n{story}"

    if actual_year == claimed_year:
        # User's claim is CORRECT → confirm enthusiastically
        return (
            f"✅ **Đúng rồi!** Sự kiện này diễn ra vào năm **{actual_year}**.\n\n"
            f"{story}"
        )
    else:
        # User's claim is WRONG → correct politely with actual year
        return (
            f"❌ **Không phải năm {claimed_year}**, sự kiện này thực tế diễn ra "
            f"vào năm **{actual_year}**.\n\n"
            f"{story}"
        )


# ===================================================================
# CORE SYNTHESIS FUNCTION
# ===================================================================

def synthesize_answer(analysis: QueryAnalysis, events: list) -> str | None:
    """
    Main answer synthesis entry point.

    Internal logic (Principle 7 — NOT printed):
    1. Check for data_scope intent → direct meta-answer
    2. Check for fact_check intent → confirm/correct user's claim
    3. Route by question_type → focused builder
    4. Apply duration guard warnings
    5. GROUNDING CHECK: Validate events are relevant to query entities
    """
    # Data scope → no events needed
    if analysis.intent == "data_scope":
        return _handle_data_scope()

    # Fact-check → confirm or correct user's factual claim
    if analysis.intent == "fact_check" or analysis.is_fact_check:
        return _build_fact_check_answer(events, analysis)

    if not events:
        return None

    # GROUNDING VALIDATION: Check if events are actually relevant
    # For entity-specific queries (person/dynasty), validate that returned events mention the target entity
    target_persons = analysis.entities.get("persons", [])
    target_dynasties = analysis.entities.get("dynasties", [])

    if target_persons or target_dynasties:
        # Check if at least the first event mentions the target entity
        first_event = events[0]
        event_persons = [p.lower() for p in (first_event.get("persons") or [])]
        event_dynasties = [d.lower() for d in (first_event.get("dynasties") or [])]
        event_text = (first_event.get("story") or first_event.get("event") or "").lower()

        # Validate grounding: does the event mention any target entity?
        entity_found = False

        for person in target_persons:
            if person.lower() in event_persons or person.lower() in event_text:
                entity_found = True
                break

        if not entity_found:
            for dynasty in target_dynasties:
                if dynasty.lower() in event_dynasties or dynasty.lower() in event_text:
                    entity_found = True
                    break

        # If no entity found in first event, likely weak semantic match → return None to force "no data"
        if not entity_found:
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
