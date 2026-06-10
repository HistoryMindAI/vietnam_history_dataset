import pytest
from app.services.answer_formatter import format_answer, _format_fact_check, _format_person, _format_year, _format_location, _format_event, _format_list, _format_dynasty
from app.core.query_schema import StructuredAnswer, QueryInfo

def test_format_answer_empty():
    assert format_answer(None, QueryInfo("", "", "event_query")) is None

def test_format_answer_types():
    query_info = QueryInfo("", "", "event_query")
    assert _format_fact_check(StructuredAnswer("fact_check")) is None

    # Fact check
    ans = StructuredAnswer("fact_check", description="Test", fact_check_result="confirmed", year=1911)
    res = format_answer(ans, query_info)
    assert "Đúng rồi" in res

    ans = StructuredAnswer("fact_check", description="Test", fact_check_result="corrected", fact_check_detail="1991")
    res = format_answer(ans, query_info)
    assert "Không phải" in res
    assert "1991" in res

    ans = StructuredAnswer("fact_check", description="Test", year=1911)
    res = format_answer(ans, query_info)
    assert "Theo dữ liệu lịch sử" in res

def test_format_person():
    ans = StructuredAnswer("person")
    assert _format_person(ans) is None

    ans = StructuredAnswer("person", description="Desc")
    assert _format_person(ans) is not None

    ans = StructuredAnswer("person", description="Desc", title="Bác Hồ")
    res = _format_person(ans)

    ans = StructuredAnswer("person", description="Desc", people=["Bác Hồ"])
    res = _format_person(ans)

    ans = StructuredAnswer("person", description="Desc", year=1911)
    res = _format_person(ans)
    assert "Năm **1911**" in res

    res = _format_person(ans)

def test_format_year():
    ans = StructuredAnswer("year")
    assert _format_year(ans) is None

    ans = StructuredAnswer("year", year=1911, description="Desc")
    assert "Năm **1911**" in _format_year(ans)

    ans = StructuredAnswer("year", description="Desc")
    assert _format_year(ans) is None

    ans = StructuredAnswer("year", year=1911, description="Desc", location="Hanoi", title="Title")
    assert "Hanoi" not in _format_year(ans)

    ans = StructuredAnswer("year", year=1911, description="Desc")
    assert "Năm **1911**" in _format_year(ans)

    ans = StructuredAnswer("year", year=1911)
    assert _format_year(ans) is None

    ans = StructuredAnswer("year", description="Desc")
    assert _format_year(ans) is None

def test_format_location():
    ans = StructuredAnswer("location")
    assert _format_location(ans) is None

    ans = StructuredAnswer("location", description="Desc", title="Title", location="Loc")
    res = _format_location(ans)
    assert "Loc" in res
    assert "Title" in res



def test_format_event():
    ans = StructuredAnswer("event")
    assert _format_event(ans) is None

    ans = StructuredAnswer("event", description="Desc", year=1911)
    res = _format_event(ans)
    assert "1911" in res

    ans = StructuredAnswer("event", description="Desc", title="Title")
    res = _format_event(ans)
    assert "Title" in res

def test_format_list():
    ans = StructuredAnswer("list")
    assert _format_list(ans) is None

    ans = StructuredAnswer("list", items=[{"year": 1911, "story": "Event 1"}, {"year": 1285, "story": "Event 2"}])
    res = _format_list(ans)
    assert "Thời Bắc thuộc" not in res

def test_format_dynasty():
    ans = StructuredAnswer("dynasty")
    assert _format_dynasty(ans) is None

    ans = StructuredAnswer("dynasty", dynasty="Nhà Lý", description="Desc")
    res = _format_dynasty(ans)
    assert "Nhà Lý" in res
    assert "Desc" in res

    ans = StructuredAnswer("dynasty", items=[{"year": 1009, "story": "Story"}])
    res = _format_dynasty(ans)



def test_format_list_items():
    ans = StructuredAnswer("list", items=[{"year": 1911, "story": "Event 1", "title": "C"}, {"year": 1285, "story": "Event 2", "title": "D"}])
    ans.year_range = (1000, 2000)
    res = _format_list(ans)
    assert "1911" in res
    assert "C" in res

def test_format_person_full():
    ans = StructuredAnswer("person", description="Desc", people=["Bác Hồ"], year=1911)
    res = _format_person(ans)
    assert "**Bác Hồ** — năm **1911**:" in res

def test_format_location_full():
    ans = StructuredAnswer("location", description="Desc", title="Title", location="Loc", year=1911)
    res = _format_location(ans)
    assert "**Title** (năm 1911) diễn ra tại **Loc**." in res

def test_format_location_loc_only():
    ans = StructuredAnswer("location", description="Desc", location="Loc")
    res = _format_location(ans)
    assert "Sự kiện này diễn ra tại **Loc**." in res


def test_format_answer_all_types():
    query_info = QueryInfo("", "", "event_query")

    ans = StructuredAnswer("person", description="A")
    assert format_answer(ans, query_info) == _format_person(ans)

    ans = StructuredAnswer("year", description="A", year=1911)
    assert format_answer(ans, query_info) == _format_year(ans)

    ans = StructuredAnswer("location", description="A", location="B")
    assert format_answer(ans, query_info) == _format_location(ans)

    ans = StructuredAnswer("list", items=[{"year": 1911, "title": "B"}])
    assert format_answer(ans, query_info) == _format_list(ans)

    ans = StructuredAnswer("dynasty", description="A", dynasty="B")
    assert format_answer(ans, query_info) == _format_dynasty(ans)

    ans = StructuredAnswer("event", description="A", title="B", year=1911)
    assert format_answer(ans, query_info) == _format_event(ans, query_info)

def test_format_event_items():
    query_info = QueryInfo("", "", "event_query")
    ans = StructuredAnswer("event", description="Desc", title="Title", year=1911, items=[
        {}, # Skip first
        {"year": 1912, "title": "Title 2", "story": "Story 2"},
        {"title": "Title 3"}
    ])
    res = _format_event(ans, query_info)
    assert "**Năm 1912**: Title 2" in res
    assert "- Title 3" in res

def test_format_event_hide_items():
    query_info = QueryInfo("", "", "event_query", question_type="what")
    ans = StructuredAnswer("event", description="Desc", title="Title", year=1911, items=[
        {}, # Skip first
        {"year": 1912, "title": "Title 2", "story": "Story 2"},
        {"title": "Title 3"}
    ])
    res = _format_event(ans, query_info)
    assert "Title 2" not in res

def test_format_list_no_year():
    ans = StructuredAnswer("list", items=[{"title": "Title 1"}])
    res = _format_list(ans)
    assert "- Title 1" in res

def test_format_dynasty_items():
    ans = StructuredAnswer("dynasty", items=[{"year": 1911, "title": "Title 1"}, {"title": "Title 2"}])
    res = _format_dynasty(ans)
    assert "**Năm 1911**: Title 1" in res
    assert "- Title 2" in res

def test_get_period_none():
    from app.services.answer_formatter import _get_period
    assert _get_period(3000) is None
