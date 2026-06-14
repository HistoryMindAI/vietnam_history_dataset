import pytest
from app.utils.entity import extract_entities

def test_extract_entities():
    # Test lowercase match
    assert extract_entities("quang trung") == {"quang_trung"}

    # Test uppercase/mixed match (should be normalized to match)
    assert extract_entities("Hồ Chí Minh") == {"ho_chi_minh"}

    # Test multiple matches
    assert extract_entities("nguyễn huệ và nguyễn tất thành") == {"quang_trung", "ho_chi_minh"}

    # Test no match
    assert extract_entities("lê lợi") == set()
