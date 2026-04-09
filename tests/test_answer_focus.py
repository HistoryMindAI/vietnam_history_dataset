"""
test_answer_focus.py — Tests for tighter answer focus in the structured pipeline.

Focus:
- where-questions should build location answers
- location answers should stay concise and grounded
"""

from app.core.query_schema import QueryInfo
from app.services.answer_builder import build_answer
from app.services.answer_formatter import format_answer


def _make_query_info(answer_type_required: str) -> QueryInfo:
    return QueryInfo(
        original_query="Trận Bạch Đằng ở đâu?",
        normalized_query="trận bạch đằng ở đâu",
        intent="event_query",
        question_type="where",
        answer_type_required=answer_type_required,
    )


def test_build_location_answer_uses_primary_place():
    query_info = _make_query_info("location")
    events = [{
        "year": 1288,
        "event": "Chiến thắng Bạch Đằng",
        "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông trên sông Bạch Đằng.",
        "places": ["Bạch Đằng", "Quảng Ninh"],
        "persons": ["Trần Hưng Đạo"],
        "_final_confidence": 0.91,
    }]

    structured = build_answer(query_info, events)

    assert structured is not None
    assert structured.answer_type == "location"
    assert structured.location == "Bạch Đằng"


def test_format_location_answer_is_concise_and_grounded():
    query_info = _make_query_info("location")
    events = [{
        "year": 1288,
        "event": "Chiến thắng Bạch Đằng",
        "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông trên sông Bạch Đằng.",
        "places": ["Bạch Đằng"],
        "persons": ["Trần Hưng Đạo"],
        "_final_confidence": 0.91,
    }]

    structured = build_answer(query_info, events)
    answer = format_answer(structured, query_info)

    assert answer is not None
    assert "diễn ra tại" in answer
    assert "Bạch Đằng" in answer
    assert "1288" in answer


def test_location_answer_without_place_returns_none():
    query_info = _make_query_info("location")
    structured = build_answer(query_info, [{
        "year": 1284,
        "event": "Hịch tướng sĩ",
        "story": "Trần Hưng Đạo soạn Hịch tướng sĩ khích lệ quân dân.",
        "persons": ["Trần Hưng Đạo"],
        "_final_confidence": 0.87,
    }])

    answer = format_answer(structured, query_info)
    assert answer is None
