from unittest.mock import patch, MagicMock
import pytest
from app.services.engine import engine_answer

# Mock data
MOCK_EVENTS = [
    {
        "year": 1288,
        "event": "Chiến thắng Bạch Đằng",
        "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông.",
        "tone": "heroic"
    }
]

@patch("app.services.engine.semantic_search")
def test_engine_definition_intent(mock_search):
    # Setup
    mock_search.return_value = MOCK_EVENTS

    # Act
    query = "Chiến thắng Bạch Đằng là gì?"
    result = engine_answer(query)

    # Assert
    assert result["intent"] == "definition"
    assert result["events"] == MOCK_EVENTS
    assert result["answer"] is not None
    assert "Trần Hưng Đạo" in result["answer"]
    mock_search.assert_called_once_with(query)

@patch("app.services.engine.scan_by_year")
def test_engine_year_intent(mock_scan):
    # Setup
    mock_scan.return_value = MOCK_EVENTS

    # Act
    query = "Sự kiện năm 1288"
    result = engine_answer(query)

    # Assert
    assert result["intent"] == "year"
    assert result["events"] == MOCK_EVENTS
    mock_scan.assert_called_once_with(1288)

@patch("app.services.engine.semantic_search")
def test_engine_semantic_fallback(mock_search):
    # Setup
    mock_search.return_value = MOCK_EVENTS

    # Act
    query = "Quân Nguyên Mông thất bại ở đâu?"
    result = engine_answer(query)

    # Assert
    assert result["intent"] == "semantic"
    assert result["events"] == MOCK_EVENTS
    mock_search.assert_called_once_with(query)

@patch("app.services.engine.semantic_search")
def test_engine_no_data(mock_search):
    # Setup
    mock_search.return_value = []

    # Act
    query = "Sự kiện không tồn tại"
    result = engine_answer(query)

    # Assert
    assert result["no_data"] is True
    assert result["events"] == []
    assert result["answer"] is None
