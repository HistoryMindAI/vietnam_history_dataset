"""
test_engine.py - Unit tests for engine answer generation

Tests intent detection, semantic search, and response formatting.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Ensure ai-service is in path
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies before import
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())

from app.services.engine import engine_answer

# Mock data matching the actual structure in engine.py
MOCK_EVENTS = [
    {
        "year": 1288,
        "event": "Chiến thắng Bạch Đằng",
        "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông.",
        "tone": "heroic",
        "persons": ["Trần Hưng Đạo"],
        "places": ["Bạch Đằng"],
        "dynasty": "",
        "keywords": [],
        "title": ""
    }
]


@patch("app.services.engine.semantic_search")
def test_engine_definition_intent(mock_search):
    """Test definition intent detection."""
    mock_search.return_value = MOCK_EVENTS

    query = "Chiến thắng Bạch Đằng là gì?"
    result = engine_answer(query)

    assert result["intent"] == "definition"
    assert result["events"] == MOCK_EVENTS
    assert result["answer"] is not None


@patch("app.services.engine.scan_by_year")
def test_engine_year_intent(mock_scan):
    """Test year-based query intent."""
    mock_scan.return_value = MOCK_EVENTS

    query = "Sự kiện năm 1288"
    result = engine_answer(query)

    assert result["intent"] == "year"
    assert result["events"] == MOCK_EVENTS
    mock_scan.assert_called_once_with(1288)


@patch("app.services.engine.semantic_search")
def test_engine_semantic_fallback(mock_search):
    """Test semantic search fallback."""
    mock_search.return_value = MOCK_EVENTS

    query = "Quân Nguyên Mông thất bại ở đâu?"
    result = engine_answer(query)

    assert result["intent"] == "semantic"
    assert result["events"] == MOCK_EVENTS


@patch("app.services.engine.semantic_search")
def test_engine_no_data(mock_search):
    """Test response when no data found."""
    mock_search.return_value = []

    query = "Sự kiện không tồn tại"
    result = engine_answer(query)

    assert result["no_data"] is True
    assert result["events"] == []
    assert result["answer"] is None
