"""
test_answer_focus.py — Tests for tighter answer focus in the structured pipeline.

Focus:
- where-questions should build location answers
- location answers should stay concise and grounded
"""

from unittest.mock import patch

from app.core.query_schema import QueryInfo
from app.services.answer_builder import build_answer
from app.services.answer_formatter import format_answer
from tests.test_engine import (
    MOCK_HICH_TUONG_SI,
    MOCK_NGO_QUYEN,
    MOCK_TRAN_HUNG_DAO,
    _setup_full_mocks,
)


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
    assert "đánh tan quân Nguyên Mông" not in answer


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


@patch("app.services.engine.semantic_search")
@patch("app.services.engine.scan_by_entities")
def test_engine_where_answer_stays_location_focused(mock_scan, mock_search):
    _setup_full_mocks()
    mock_scan.return_value = [MOCK_NGO_QUYEN, MOCK_TRAN_HUNG_DAO]
    mock_search.return_value = []

    from app.services.engine import engine_answer

    result = engine_answer("Trận Bạch Đằng ở đâu?")

    assert not result["no_data"]
    assert "Bạch Đằng" in result["answer"]
    assert "diễn ra tại" in result["answer"]
    assert "Ngô Quyền dùng cọc gỗ" not in result["answer"]
    assert "đánh tan quân Nguyên Mông" not in result["answer"]


@patch("app.services.engine.semantic_search")
@patch("app.services.engine.scan_by_entities")
def test_engine_who_answer_filters_unrelated_candidates(mock_scan, mock_search):
    _setup_full_mocks()
    mock_scan.return_value = [MOCK_TRAN_HUNG_DAO, MOCK_HICH_TUONG_SI]
    mock_search.return_value = []

    from app.services.engine import engine_answer

    result = engine_answer("Trần Hưng Đạo là ai?")

    assert not result["no_data"]
    assert "Trần Hưng Đạo" in result["answer"]
    assert "Hịch tướng sĩ" in result["answer"]
    assert "Ngô Quyền" not in result["answer"]
