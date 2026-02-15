"""
answer_builder.py — Structured Answer Builder (Phase 1 / Giai đoạn 11)

PURPOSE:
    Builds StructuredAnswer (JSON) from validated events — KHÔNG viết text.
    Tách DATA khỏi presentation để dễ maintain + chuẩn bị cho LLM rewrite.

CONTEXT:
    - TRƯỚC ĐÂY: answer_synthesis.py vừa chọn data vừa format text trong cùng 1 hàm
    - BÂY GIỜ: Tách thành 2 bước: AnswerBuilder (JSON) → AnswerFormatter (text)

RELATED OLD FILES:
    - answer_synthesis.py → _build_when_answer(), _build_who_answer(),
      _build_what_answer(), _build_list_answer(), _build_fact_check_answer()
      (vẫn giữ làm fallback — module này ưu tiên trước)

PIPELINE POSITION:
    Hard Filter → Confidence Score → **Answer Build** → Answer Format → Final

USAGE:
    structured = build_answer(query_info, validated_events)
    text = answer_formatter.format_answer(structured, query_info)
"""

from typing import List, Dict, Any, Optional

from app.core.query_schema import QueryInfo, StructuredAnswer


def build_answer(
    query_info: QueryInfo,
    events: List[Dict[str, Any]],
) -> Optional[StructuredAnswer]:
    """
    Main entry point: build StructuredAnswer from validated events.

    Routing:
        fact_check → _build_fact_check()
        who        → _build_person_answer()
        when       → _build_year_answer()
        list       → _build_list()
        what/event → _build_event_answer()

    Returns:
        StructuredAnswer hoặc None nếu không đủ data.
    """
    if not events:
        return None

    # Best candidate (highest confidence after scoring)
    best = events[0]

    # Route by answer_type_required hoặc intent
    if query_info.is_fact_check:
        return _build_fact_check(query_info, best, events)

    answer_type = query_info.answer_type_required or "event"

    if answer_type == "person":
        return _build_person_answer(query_info, best, events)

    elif answer_type == "year":
        return _build_year_answer(query_info, best, events)

    elif answer_type == "list":
        return _build_list(query_info, events)

    elif answer_type == "dynasty":
        return _build_dynasty_answer(query_info, events)

    else:
        # Default: event answer
        return _build_event_answer(query_info, best, events)


# ===================================================================
# BUILDERS BY TYPE
# ===================================================================

def _build_fact_check(
    query_info: QueryInfo,
    best: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> StructuredAnswer:
    """Fact-check: compare claimed_year vs actual_year."""
    actual_year = best.get("year")
    claimed_year = query_info.claimed_year
    story = (best.get("story") or best.get("event") or "").strip()

    # Coerce year
    if actual_year is not None:
        try:
            actual_year = int(actual_year)
        except (ValueError, TypeError):
            actual_year = None

    if claimed_year is not None and actual_year is not None:
        if actual_year == claimed_year:
            result = "confirmed"
            detail = f"Năm {actual_year} — đúng"
        else:
            result = "corrected"
            detail = f"User nêu: {claimed_year}, thực tế: {actual_year}"
    else:
        result = None
        detail = None

    return StructuredAnswer(
        answer_type="fact_check",
        title=best.get("event") or best.get("title"),
        year=actual_year,
        people=best.get("persons", []) or [],
        dynasty=best.get("dynasty"),
        description=story,
        confidence=best.get("_final_confidence", 0.0),
        fact_check_result=result,
        fact_check_detail=detail,
    )


def _build_person_answer(
    query_info: QueryInfo,
    best: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> StructuredAnswer:
    """Build answer focused on a person."""
    # Collect unique people from all events
    all_people = []
    for e in events[:5]:
        for p in (e.get("persons", []) or []):
            if p not in all_people:
                all_people.append(p)

    story = (best.get("story") or best.get("event") or "").strip()

    return StructuredAnswer(
        answer_type="person",
        title=best.get("event") or best.get("title"),
        year=best.get("year"),
        people=all_people[:5],
        dynasty=best.get("dynasty"),
        description=story,
        confidence=best.get("_final_confidence", 0.0),
    )


def _build_year_answer(
    query_info: QueryInfo,
    best: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> StructuredAnswer:
    """Build answer focused on year (when question)."""
    story = (best.get("story") or best.get("event") or "").strip()

    return StructuredAnswer(
        answer_type="year",
        title=best.get("event") or best.get("title"),
        year=best.get("year"),
        people=best.get("persons", []) or [],
        dynasty=best.get("dynasty"),
        description=story,
        confidence=best.get("_final_confidence", 0.0),
    )


def _build_event_answer(
    query_info: QueryInfo,
    best: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> StructuredAnswer:
    """Build generic event answer."""
    story = (best.get("story") or best.get("event") or "").strip()

    # Build items from top events (if multiple)
    items = []
    if len(events) > 1:
        for e in events[:8]:
            items.append({
                "title": e.get("event") or e.get("title", ""),
                "year": e.get("year"),
                "story": (e.get("story") or "").strip()[:200],
                "persons": e.get("persons", []) or [],
            })

    return StructuredAnswer(
        answer_type="event",
        title=best.get("event") or best.get("title"),
        year=best.get("year"),
        people=best.get("persons", []) or [],
        location=best.get("location"),
        dynasty=best.get("dynasty"),
        description=story,
        items=items,
        confidence=best.get("_final_confidence", 0.0),
    )


def _build_list(
    query_info: QueryInfo,
    events: List[Dict[str, Any]],
) -> StructuredAnswer:
    """Build list answer (multiple events)."""
    items = []
    for e in events[:15]:
        items.append({
            "title": e.get("event") or e.get("title", ""),
            "year": e.get("year"),
            "story": (e.get("story") or "").strip()[:200],
            "persons": e.get("persons", []) or [],
            "dynasty": e.get("dynasty", ""),
        })

    return StructuredAnswer(
        answer_type="list",
        title=None,
        year_range=query_info.required_year_range,
        items=items,
        confidence=events[0].get("_final_confidence", 0.0) if events else 0.0,
    )


def _build_dynasty_answer(
    query_info: QueryInfo,
    events: List[Dict[str, Any]],
) -> StructuredAnswer:
    """Build dynasty-focused answer."""
    best = events[0] if events else {}
    items = []
    for e in events[:10]:
        items.append({
            "title": e.get("event") or e.get("title", ""),
            "year": e.get("year"),
            "story": (e.get("story") or "").strip()[:200],
            "persons": e.get("persons", []) or [],
        })

    return StructuredAnswer(
        answer_type="dynasty",
        title=best.get("event") or best.get("title"),
        year=best.get("year"),
        dynasty=best.get("dynasty"),
        description=(best.get("story") or "").strip(),
        items=items,
        confidence=best.get("_final_confidence", 0.0),
    )
