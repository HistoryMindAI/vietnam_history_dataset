import pytest
from app.temporal.temporal_engine import TemporalEngine, TemporalDataSource, TemporalEvent, TimeRange, TemporalReasoner, TemporalConflictDetector
from app.temporal.temporal_intent import TemporalIntent

def test_time_range():
    tr1 = TimeRange(1000, 1050)
    tr2 = TimeRange(1020, 1080)
    tr3 = TimeRange(1060, 1100)
    tr4 = TimeRange(1010, 1040)

    assert tr1.overlaps(tr2)
    assert not tr1.overlaps(tr3)

    assert tr1.contains(1025)
    assert not tr1.contains(1060)

    assert tr1.contains_range(tr4)
    assert not tr1.contains_range(tr2)

    assert tr1.duration == 51
    assert TimeRange(1000, 1000).duration == 1

    assert tr1.before(tr3)
    assert tr3.after(tr1)

def test_temporal_reasoner():
    ev1 = TemporalEvent(name="Event A", time_range=TimeRange(1000, 1050))
    ev2 = TemporalEvent(name="Event B", time_range=TimeRange(1060, 1100))
    ev3 = TemporalEvent(name="Event C", time_range=TimeRange(1020, 1080))
    reasoner = TemporalReasoner([ev1, ev2, ev3])

    assert len(reasoner.events_after("Event A")) == 1
    assert len(reasoner.events_before("Event B")) == 1
    assert len(reasoner.events_overlapping("Event C")) == 2

    assert reasoner._find_event("Event A") == ev1

def test_temporal_engine_solve():
    docs = [
        {"id": "doc1", "year": 1000, "story": "Triều đại X bắt đầu.", "dynasty": "Triều đại X", "events": ["Thành lập Triều đại X"]},
        {"id": "doc2", "year": 1050, "story": "Triều đại X kết thúc.", "dynasty": "Triều đại X", "events": ["Sụp đổ Triều đại X"]},
        {"id": "doc3", "year": 1060, "story": "Triều đại Y bắt đầu.", "dynasty": "Triều đại Y"},
        {"id": "doc4", "year": 1200, "story": "Triều đại Y kết thúc.", "dynasty": "Triều đại Y"},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    query = {"intent": "duration_max", "entity_type": "dynasty"}
    result = engine.solve(query)

    assert result is not None

def test_temporal_engine_duration_min():
    docs = [
        {"id": "doc1", "year": 1000, "story": "Triều đại X bắt đầu.", "dynasty": "Triều đại X"},
        {"id": "doc2", "year": 1050, "story": "Triều đại X kết thúc.", "dynasty": "Triều đại X"},
        {"id": "doc3", "year": 1060, "story": "Triều đại Y bắt đầu.", "dynasty": "Triều đại Y"},
        {"id": "doc4", "year": 1200, "story": "Triều đại Y kết thúc.", "dynasty": "Triều đại Y"},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    query = {"intent": "duration_min", "entity_type": "dynasty"}
    result = engine.solve(query)

    assert result is not None

def test_temporal_engine_compare():
    docs = [
        {"id": "doc1", "year": 1000, "story": "Triều đại X bắt đầu.", "dynasty": "Triều đại X"},
        {"id": "doc2", "year": 1050, "story": "Triều đại X kết thúc.", "dynasty": "Triều đại X"},
        {"id": "doc3", "year": 1060, "story": "Triều đại Y bắt đầu.", "dynasty": "Triều đại Y"},
        {"id": "doc4", "year": 1200, "story": "Triều đại Y kết thúc.", "dynasty": "Triều đại Y"},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    query = {"intent": "compare", "entity_type": "dynasty", "entity_a": "Triều đại X", "entity_b": "Triều đại Y"}
    result = engine.solve(query)
    assert result is not None

def test_temporal_engine_before_after():
    docs = [
        {"id": "doc1", "year": 1000, "event": "Sự kiện A", "story": "Sự kiện A", "events": ["Sự kiện A"]},
        {"id": "doc2", "year": 1050, "story": "Sự kiện B", "events": ["Sự kiện B"]},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    query = {"intent": "before_after", "reference": "Sự kiện A", "direction": "after"}
    result = engine.solve(query)
    assert result is not None

def test_temporal_engine_overlap():
    docs = [
        {"id": "doc1", "year": 1000, "event": "Sự kiện A", "story": "Sự kiện A", "events": ["Sự kiện A"]},
        {"id": "doc2", "year": 1005, "story": "Sự kiện B", "events": ["Sự kiện B"]},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    query = {"intent": "overlap", "reference": "Sự kiện A"}
    result = engine.solve(query)
    assert result is not None

def test_temporal_engine_range_between():
    docs = [
        {"id": "doc1", "year": 1000, "event": "Sự kiện A", "story": "Sự kiện A", "events": ["Sự kiện A"]},
        {"id": "doc2", "year": 1050, "story": "Sự kiện B", "events": ["Sự kiện B"]},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    query = {"intent": "range_between", "event_a": "Sự kiện A", "event_b": "Sự kiện B"}
    result = engine.solve(query)
    assert result is not None

def test_temporal_engine_at_year():
    docs = [
        {"id": "doc1", "year": 1000, "event": "Sự kiện A", "story": "Sự kiện A", "events": ["Sự kiện A"]},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    query = {"intent": "at_year", "year": 1000}
    result = engine.solve(query)
    assert result is not None

def test_timeline_resolver():
    from app.temporal.timeline_resolver import TimelineResolver

    entities = [
        {"id": "doc1", "start_year": 1000, "end_year": 1050, "name": "Event A"},
        {"id": "doc2", "start_year": 1050, "end_year": 1100, "name": "Event B"},
    ]

    assert len(TimelineResolver.before(entities, 1020)) == 1
    assert len(TimelineResolver.after(entities, 1020)) == 1
    assert len(TimelineResolver.overlap(entities, 1000, 1060)) == 2
    assert len(TimelineResolver.at_year(entities, 1050)) == 2

def test_comparator():
    from app.temporal.comparator import Comparator

    entities = [
        {"id": "doc1", "duration": 50, "name": "Dynasty A"},
        {"id": "doc2", "duration": 100, "name": "Dynasty B"},
    ]

    assert Comparator.max_entity(entities, "duration")["name"] == "Dynasty B"
    assert Comparator.min_entity(entities, "duration")["name"] == "Dynasty A"
    assert Comparator.compare(entities[0], entities[1], "duration") == -1

def test_duration_calculator():
    from app.temporal.duration_calculator import DurationCalculator

    assert DurationCalculator.calculate(1000, 1050) == 50
    assert DurationCalculator.calculate_safe(1000, 1050) == 50
    assert DurationCalculator.calculate_safe(1000, None) == 0

    entities = [
        {"id": "doc1", "start_year": 1000, "end_year": 1050},
        {"id": "doc2", "start_year": 1060, "end_year": 1100},
    ]

    calc_entities = DurationCalculator.enrich_entities(entities)
    assert calc_entities[0]["duration"] == 50
    assert calc_entities[1]["duration"] == 40

def test_temporal_parser():
    from app.temporal.temporal_engine import TemporalParser

    assert TemporalParser.parse("đầu thế kỷ 20").start == 1900
    assert TemporalParser.parse("đầu thế kỷ 20").end == 1930
    assert TemporalParser.parse("giữa thế kỷ 20").start == 1930
    assert TemporalParser.parse("giữa thế kỷ 20").end == 1970
    assert TemporalParser.parse("cuối thế kỷ 20").start == 1970
    assert TemporalParser.parse("cuối thế kỷ 20").end == 1999

    assert TemporalParser.parse("thế kỷ 19").start == 1800
    assert TemporalParser.parse("thế kỷ 19").end == 1899

    assert TemporalParser.parse("thập niên 1930").start == 1930
    assert TemporalParser.parse("thập niên 1930").end == 1939

    assert TemporalParser.parse("1946-1954").start == 1946
    assert TemporalParser.parse("1946-1954").end == 1954
    parsed = TemporalParser.parse("1954-1946")
    assert parsed.start == 1954

    assert TemporalParser.parse("1954").start == 1954
    assert TemporalParser.parse("1954").end == 1954
    assert TemporalParser.parse("25") is None

    assert TemporalParser.parse("random text") is None
    assert TemporalParser.parse_all_years("random text") == []
    assert TemporalParser.parse_all_years("1954 and 1975") == [1954, 1975]

def test_temporal_engine_filter():
    docs = [
        {"id": "doc1", "year": 1954, "story": "Sự kiện 1954"},
        {"id": "doc2", "year": 1945, "story": "Sự kiện 1945"},
        {"id": "doc3", "metadata": {"year": 1975}, "story": "Sự kiện 1975"},
        {"id": "doc4", "story": "Sự kiện không năm"},
        {"id": "doc5", "year": "invalid", "story": "Sự kiện invalid"},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    filtered = engine.filter_by_temporal(docs, "sự kiện năm 1954")
    assert len(filtered) == 3
    assert filtered[0]["id"] == "doc1"

    filtered2 = engine.filter_by_temporal(docs, "không năm")
    assert len(filtered2) == 5

def test_temporal_intent():
    from app.temporal.temporal_intent import detect_temporal_intent, TemporalIntent
    assert detect_temporal_intent("Triều đại nào tồn tại lâu nhất?") == TemporalIntent.DURATION_MAX
    assert detect_temporal_intent("Sự kiện diễn ra cùng thời với A?") == TemporalIntent.OVERLAP
    assert detect_temporal_intent("Ai là người sáng lập?") is None

def test_temporal_conflicts_engine():
    docs = [
        {"id": "doc1", "year": 1000, "event": "Sự kiện A", "story": "Sự kiện A"},
        {"id": "doc2", "year": 1000, "event": "Sự kiện A", "story": "Sự kiện A"},
        {"id": "doc3", "year": 1010, "event": "Sự kiện A", "story": "Sự kiện A"},
    ]
    conflict = TemporalConflictDetector.detect_conflicts(docs, "Sự kiện A")
    assert conflict is not None
    assert conflict.majority_year == 1000

    docs2 = [
        {"id": "doc1", "year": 1000, "story": "Sự kiện B"},
    ]
    assert TemporalConflictDetector.detect_conflicts(docs2, "Sự kiện B") is None

    docs3 = [
        {"id": "doc1", "year": 1000, "story": "Sự kiện C"},
        {"id": "doc2", "year": 1000, "story": "Sự kiện C"},
    ]
    assert TemporalConflictDetector.detect_conflicts(docs3, "Sự kiện C") is None

    docs4 = [
        {"id": "doc1", "year": "invalid", "story": "Sự kiện D"},
        {"id": "doc2", "year": "invalid2", "story": "Sự kiện D"},
    ]
    assert TemporalConflictDetector.detect_conflicts(docs4, "Sự kiện D") is None

def test_temporal_engine_get_temporal_events():
    docs = [
        {"id": "doc1", "year": 1000, "start_year": 1000, "end_year": 1050, "event": "Sự kiện A", "event": "Sự kiện A", "story": "Sự kiện A", "event_type": "battle"},
        {"id": "doc2", "year": 1000, "event": "Sự kiện A", "story": "Sự kiện A"}, # Duplicate name, should be skipped
        {"id": "doc3", "story": "Sự kiện no year"}, # Missing year
        {"id": "doc4", "year": "invalid", "story": "Sự kiện invalid"}, # Invalid year
    ]
    source = TemporalDataSource(docs)
    events = source.get_temporal_events()
    assert len(events) == 1
    assert events[0].name == "Sự kiện A"
    assert events[0].event_type == "battle"
    assert events[0].time_range.duration == 51

def test_temporal_engine_solve_compare_equal():
    docs = [
        {"id": "doc1", "year": 1000, "start_year": 1000, "end_year": 1050, "event": "Triều đại A", "story": "Triều đại A", "dynasty": "Triều đại A", "name": "Triều đại A"},
        {"id": "doc3", "year": 1060, "start_year": 1060, "end_year": 1110, "event": "Triều đại B", "story": "Triều đại B", "dynasty": "Triều đại B", "name": "Triều đại B"},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)
    res = engine._solve_compare({"entity_type": "dynasty", "entity_a": "Triều đại A", "entity_b": "Triều đại B"})
    # duration is 51 vs 51. Should be equal.
    assert "đều tồn tại" in res["reasoning"]

def test_temporal_engine_solve_compare_less():
    docs = [
        {"id": "doc1", "year": 1000, "start_year": 1000, "end_year": 1040, "event": "Triều đại A", "story": "Triều đại A", "dynasty": "Triều đại A", "name": "Triều đại A"},
        {"id": "doc3", "year": 1060, "start_year": 1060, "end_year": 1110, "event": "Triều đại B", "story": "Triều đại B", "dynasty": "Triều đại B", "name": "Triều đại B"},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)
    res = engine._solve_compare({"entity_type": "dynasty", "entity_a": "Triều đại A", "entity_b": "Triều đại B"})
    assert res["result"]["name"] == "Triều đại B"

def test_temporal_engine_solve_at_year_parsed():
    docs = [
        {"id": "doc1", "year": 1950, "start_year": 1946, "end_year": 1954, "story": "Sự kiện 1", "event": "Sự kiện 1", "events": ["Sự kiện 1"]},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    # Range query
    res1 = engine._solve_at_year({"query": "Sự kiện giai đoạn 1946-1954"})
    assert len(res1["result"]) == 1
    assert "giai đoạn" in res1["reasoning"]

    # Exact year from parser, but end matches start (e.g., just "1954") -> falls back to "elif parsed_range"
    res2 = engine._solve_at_year({"query": "Sự kiện năm 1954"})
    assert len(res2["result"]) == 1
    assert "năm 1954" in res2["reasoning"]

    # No year, no parsed range
    res3 = engine._solve_at_year({"query": "Sự kiện không năm"})
    assert len(res3["result"]) == 0
    assert "Không xác định được" in res3["reasoning"]


def test_temporal_engine_edge_cases():
    docs = [
        {"id": "doc1", "year": 1000, "event": "Sự kiện A", "story": "Sự kiện A", "event_type": "missing"},
    ]
    source = TemporalDataSource(docs)
    engine = TemporalEngine(source)

    # max duration
    res1 = engine._solve_duration_max({"entity_type": "missing"})
    assert res1.get("result") is not None

    # min duration missing (if no data)
    docs_empty = []
    engine_empty = TemporalEngine(TemporalDataSource(docs_empty))
    res2 = engine_empty._solve_duration_min({"entity_type": "missing"})
    assert res2.get("result") is None

    # min duration
    res3 = engine._solve_duration_min({"entity_type": "missing"})
    assert res3.get('result') is None

    # compare
    res4 = engine._solve_compare({"entity_type": "dynasty", "entity_a": "Missing A", "entity_b": "Missing B"})
    assert res4.get("result") is None

    # compare with both equal
    docs3 = [
        {"id": "doc1", "year": 1000, "start_year": 1000, "end_year": 1050, "event": "Triều đại A", "dynasty": "Triều đại A"},
        {"id": "doc3", "year": 1060, "start_year": 1060, "end_year": 1110, "event": "Triều đại B", "dynasty": "Triều đại B"},
    ]
    source3 = TemporalDataSource(docs3)
    engine3 = TemporalEngine(source3)
    res5 = engine3._solve_compare({"entity_type": "dynasty", "entity_a": "Triều đại B", "entity_b": "Triều đại A"})
    assert "đều tồn tại" in res5["reasoning"]

    # compare with one missing
    res6 = engine3._solve_compare({"entity_type": "dynasty", "entity_a": "Triều đại A", "entity_b": "Missing B"})
    assert res6.get("result") is None

    # range between unknown
    res7 = engine3._solve_range_between({"event_a": "Unknown 1", "event_b": "Unknown 2"})
    assert res7.get("result") is not None

def test_comparator_edge_cases():
    from app.temporal.comparator import Comparator

    assert Comparator.max_entity([{}], "duration", default={"name": "def"})["name"] == "def"
    assert Comparator.min_entity([{}], "duration", default={"name": "def"})["name"] == "def"
    assert Comparator.compare({"duration": 100}, {"duration": 50}, "duration") == 1

    ranked = Comparator.rank([{"duration": 50}, {"duration": 100}, {}], "duration")
    assert len(ranked) == 2
    assert ranked[0]["duration"] == 100

def test_duration_calculator_edge_cases():
    from app.temporal.duration_calculator import DurationCalculator
    import pytest

    with pytest.raises(ValueError):
        DurationCalculator.calculate(None, 1000)
    with pytest.raises(ValueError):
        DurationCalculator.calculate(1000, None)

    assert DurationCalculator.calculate_safe("invalid", 1000, default=10) == 10

def test_timeline_resolver_edge_cases():
    from app.temporal.timeline_resolver import TimelineResolver

    entities = [
        {"id": "doc1", "start_year": 1000, "end_year": 1050},
        {"id": "doc2", "start_year": 1060}, # Missing end_year
    ]

    res = TimelineResolver.overlap(entities, 1000, 1060)
    assert len(res) == 1
