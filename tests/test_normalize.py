import pytest
from app.utils.normalize import normalize_query, normalize

def test_normalize_query_preserves_accents():
    raw = "Hòa ước Patenôtre"
    expected = "hòa ước patenôtre"
    assert normalize_query(raw) == expected

def test_normalize_query_lowercases():
    raw = "NGÔ QUYỀN"
    expected = "ngô quyền"
    assert normalize_query(raw) == expected

def test_normalize_query_strips_whitespace():
    raw = "  Hòa   ước  "
    expected = "hòa ước"
    assert normalize_query(raw) == expected

def test_normalize_strips_accents():
    raw = "Hòa ước Patenôtre"
    expected = "hoa uoc patenotre"
    assert normalize(raw) == expected

def test_normalize_handles_complex_accents():
    raw = "Tiếng Việt"
    expected = "tieng viet"
    assert normalize(raw) == expected
