import pytest
from app.utils.normalize import normalize_query, normalize, remove_accents

def test_remove_accents():
    assert remove_accents("Hồ Chí Minh") == "Ho Chi Minh"
    assert remove_accents("Nguyễn Huệ") == "Nguyen Hue"

def test_normalize_query():
    assert normalize_query("  Hồ Chí   Minh  ") == "hồ chí minh"

def test_normalize():
    assert normalize("Hồ Chí Minh") == "ho chi minh"
