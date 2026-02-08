"""
test_normalize.py - Unit tests for text normalization utilities

Tests query normalization and accent handling.
"""
import sys
from pathlib import Path
import pytest

# Ensure ai-service is in path
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from app.utils.normalize import normalize_query, normalize


def test_normalize_query_preserves_accents():
    """Test that normalize_query keeps Vietnamese accents."""
    raw = "Hòa ước Patenôtre"
    expected = "hòa ước patenôtre"
    assert normalize_query(raw) == expected


def test_normalize_query_lowercases():
    """Test that normalize_query lowercases text."""
    raw = "NGÔ QUYỀN"
    expected = "ngô quyền"
    assert normalize_query(raw) == expected


def test_normalize_query_strips_whitespace():
    """Test that normalize_query strips extra whitespace."""
    raw = "  Hòa   ước  "
    expected = "hòa ước"
    assert normalize_query(raw) == expected


def test_normalize_strips_accents():
    """Test that normalize removes accents."""
    raw = "Hòa ước Patenôtre"
    expected = "hoa uoc patenotre"
    assert normalize(raw) == expected


def test_normalize_handles_complex_accents():
    """Test normalize with complex Vietnamese accents."""
    raw = "Tiếng Việt"
    expected = "tieng viet"
    assert normalize(raw) == expected
