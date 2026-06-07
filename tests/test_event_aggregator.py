import pytest
from app.services.event_aggregator import aggregate_events, normalize_for_dedup

def test_aggregate_events_basic():
    docs = [
        {"story": "Trận Bạch Đằng năm 938 đánh bại quân Nam Hán", "year": 938, "persons": ["Ngô Quyền"], "places": ["Bạch Đằng"]},
        {"story": "Năm 938 diễn ra trận Bạch Đằng", "year": 938, "persons": [], "places": []},
        {"story": "Chiến thắng Điện Biên Phủ", "year": 1954, "persons": ["Võ Nguyên Giáp"], "places": ["Điện Biên Phủ"]}
    ]

    result = aggregate_events(docs)

    assert len(result) == 2
    # Check if the longest story is kept for Bach Dang
    bach_dang_event = next(e for e in result if e["year"] == 938)
    assert bach_dang_event["story"] == "Trận Bạch Đằng năm 938 đánh bại quân Nam Hán"
    assert "Ngô Quyền" in bach_dang_event["persons"]

def test_aggregate_events_token_reorder():
    docs = [
        {"story": "Ngô Quyền đánh bại quân Nam Hán trên sông Bạch Đằng", "year": 938, "persons": ["Ngô Quyền"]},
        {"story": "Trên sông Bạch Đằng, Ngô Quyền đánh bại quân Nam Hán", "year": 938, "persons": []}
    ]

    result = aggregate_events(docs)
    assert len(result) == 1
    assert "Ngô Quyền" in result[0]["persons"]

def test_aggregate_events_merges_metadata():
    docs = [
        {"story": "Chiến thắng vĩ đại", "year": 1975, "persons": ["Lê Duẩn"], "places": []},
        {"story": "Chiến thắng vĩ đại", "year": 1975, "persons": ["Võ Nguyên Giáp"], "places": ["Sài Gòn"]}
    ]

    result = aggregate_events(docs)
    assert len(result) == 1
    assert "Lê Duẩn" in result[0]["persons"]
    assert "Võ Nguyên Giáp" in result[0]["persons"]
    assert "Sài Gòn" in result[0]["places"]

def test_normalize_for_dedup_strips_markdown():
    assert normalize_for_dedup("**Năm 2010:** Đại lễ") == "đại lễ"
    assert normalize_for_dedup("### Đại lễ") == "đại lễ"
    assert normalize_for_dedup("- Sự kiện") == "sự kiện"
