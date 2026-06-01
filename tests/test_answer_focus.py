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


def test_format_location_answer_extracts_clean_title_from_raw_event_sentence():
    query_info = _make_query_info("location")
    events = [{
        "year": 938,
        "event": "Năm 938, Trận Bạch Đằng (Ngô Quyền). Ông dùng cọc gỗ đặt ngầm trên sông Bạch Đằng, đánh bại thủy quân Nam Hán.",
        "story": "Năm 938, Trận Bạch Đằng (Ngô Quyền). Ông dùng cọc gỗ đặt ngầm trên sông Bạch Đằng, đánh bại thủy quân Nam Hán.",
        "places": ["Bạch Đằng"],
        "persons": ["Ngô Quyền"],
        "_final_confidence": 0.93,
    }]

    structured = build_answer(query_info, events)
    answer = format_answer(structured, query_info)

    assert answer == "**Trận Bạch Đằng (Ngô Quyền)** (năm 938) diễn ra tại **Bạch Đằng**."


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
def test_engine_where_answer_handles_live_like_event_payload(mock_scan, mock_search):
    _setup_full_mocks()
    mock_scan.return_value = [{
        "id": "hf_000281",
        "year": 938,
        "event": "Năm 938, Trận Bạch Đằng (Ngô Quyền). Ông dùng cọc gỗ đặt ngầm trên sông Bạch Đằng, đánh bại thủy quân Nam Hán.",
        "story": "Năm 938, Trận Bạch Đằng (Ngô Quyền). Ông dùng cọc gỗ đặt ngầm trên sông Bạch Đằng, đánh bại thủy quân Nam Hán, chấm dứt hơn một thiên niên kỷ Bắc thuộc.",
        "persons": ["Ngô Quyền"],
        "places": ["Bạch Đằng"],
        "keywords": ["bạch_đằng", "ngô_quyền"],
    }]
    mock_search.return_value = []

    from app.services.engine import engine_answer

    result = engine_answer("Trận Bạch Đằng ở đâu?")

    assert not result["no_data"]
    assert result["answer"] == "**Trận Bạch Đằng (Ngô Quyền)** (năm 938) diễn ra tại **Bạch Đằng**."


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


def test_format_event_excludes_additional_items_for_specific_questions():
    from app.core.query_schema import QueryInfo, StructuredAnswer
    from app.services.answer_formatter import format_answer

    # 1. Setup a specific "what" question
    query_info = QueryInfo(
        original_query="Chiến dịch Điện Biên Phủ diễn ra thế nào?",
        normalized_query="chiến dịch điện biên phủ diễn ra thế nào",
        intent="event_query",
        question_type="what",
        answer_type_required="event",
    )

    structured = StructuredAnswer(
        answer_type="event",
        title="Chiến dịch Điện Biên Phủ",
        year=1954,
        description="Chiến dịch kết thúc bằng thắng lợi hoàn toàn của quân dân Việt Nam.",
        items=[
            {"title": "Chiến dịch Điện Biên Phủ", "year": 1954, "story": "Chiến dịch Điện Biên Phủ kết thúc thắng lợi."},
            {"title": "Ký Hiệp định Genève", "year": 1954, "story": "Ký kết Hiệp định Genève chấm dứt chiến tranh."},
        ]
    )

    answer = format_answer(structured, query_info)
    assert answer is not None
    # Description should be present
    assert "Chiến dịch kết thúc" in answer
    # Additional items (Hiệp định Genève) should be OMITTED
    assert "Hiệp định Genève" not in answer


def test_format_event_includes_additional_items_for_general_queries():
    from app.core.query_schema import QueryInfo, StructuredAnswer
    from app.services.answer_formatter import format_answer

    # 2. Setup a general/empty question type query
    query_info = QueryInfo(
        original_query="Điện Biên Phủ",
        normalized_query="điện biên phủ",
        intent="event_query",
        question_type=None,
        answer_type_required="event",
    )

    structured = StructuredAnswer(
        answer_type="event",
        title="Chiến dịch Điện Biên Phủ",
        year=1954,
        description="Chiến dịch kết thúc bằng thắng lợi hoàn toàn của quân dân Việt Nam.",
        items=[
            {"title": "Chiến dịch Điện Biên Phủ", "year": 1954, "story": "Chiến dịch Điện Biên Phủ kết thúc thắng lợi."},
            {"title": "Ký Hiệp định Genève", "year": 1954, "story": "Ký kết Hiệp định Genève chấm dứt chiến tranh."},
        ]
    )

    answer = format_answer(structured, query_info)
    assert answer is not None
    # Description should be present
    assert "Chiến dịch kết thúc" in answer
    # Additional items (Hiệp định Genève) should be INCLUDED
    assert "Hiệp định Genève" in answer

