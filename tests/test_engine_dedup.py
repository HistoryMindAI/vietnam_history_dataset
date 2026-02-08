"""
Tests for engine.py deduplication logic.

These tests verify that:
1. Duplicate events with similar content are deduplicated
2. MAX_STORIES limit is respected
3. Identity queries are handled correctly
"""
import pytest
from unittest.mock import patch, MagicMock

# Mock the imports first
import sys
sys.path.insert(0, 'd:/HistoryMindAI/vietnam_history_dataset/ai-service')


class TestNormalizeEventSignature:
    """Test the normalize_event_signature function."""
    
    def test_normalize_basic(self):
        from app.services.engine import normalize_event_signature
        
        result = normalize_event_signature("Nguyễn Tất Thành ra đi tìm đường cứu nước")
        assert result == "nguyễn tất thành ra đi tìm đường cứu nước"
    
    def test_normalize_extra_spaces(self):
        from app.services.engine import normalize_event_signature
        
        result = normalize_event_signature("Nguyễn   Tất   Thành   ra đi")
        assert " " not in result or result.count("  ") == 0  # No double spaces
    
    def test_normalize_truncates_to_50(self):
        from app.services.engine import normalize_event_signature
        
        long_text = "A" * 100
        result = normalize_event_signature(long_text)
        assert len(result) == 50
    
    def test_normalize_empty_string(self):
        from app.services.engine import normalize_event_signature
        
        result = normalize_event_signature("")
        assert result == ""
    
    def test_normalize_none(self):
        from app.services.engine import normalize_event_signature
        
        result = normalize_event_signature(None)
        assert result == ""


class TestEngineAnswerIdentity:
    """Test identity query handling."""
    
    @patch('app.services.engine.semantic_search')
    @patch('app.services.engine.scan_by_year')
    def test_identity_query_vietnamese(self, mock_scan, mock_search):
        from app.services.engine import engine_answer
        
        result = engine_answer("bạn là ai?")
        
        assert result["intent"] == "identity"
        assert "History Mind AI" in result["answer"]
        assert result["no_data"] == False
        # Should NOT call search services
        mock_search.assert_not_called()
        mock_scan.assert_not_called()
    
    @patch('app.services.engine.semantic_search')
    @patch('app.services.engine.scan_by_year')
    def test_identity_query_english(self, mock_scan, mock_search):
        from app.services.engine import engine_answer
        
        result = engine_answer("Who are you?")
        
        assert result["intent"] == "identity"
        assert "History Mind AI" in result["answer"]


class TestEngineAnswerDeduplication:
    """Test that duplicate events are properly deduplicated."""
    
    @patch('app.services.engine.scan_by_year')
    def test_dedup_similar_events(self, mock_scan):
        from app.services.engine import engine_answer
        
        # Simulate duplicate events with slightly different stories
        mock_scan.return_value = [
            {"year": 1911, "event": "Nguyễn Tất Thành ra đi tìm đường cứu nước", "story": "Story version 1"},
            {"year": 1911, "event": "Nguyễn Tất Thành ra đi tìm đường cứu nước", "story": "Story version 2"},
            {"year": 1911, "event": "Nguyễn Tất Thành ra đi tìm đường cứu nước", "story": "Story version 3"},
        ]
        
        result = engine_answer("năm 1911")
        
        # Should only have 1 unique answer (same event signature)
        assert result["answer"].count("\n") == 0  # Only 1 story, no newlines
    
    @patch('app.services.engine.scan_by_year')
    def test_max_stories_limit(self, mock_scan):
        from app.services.engine import engine_answer, MAX_STORIES
        
        # Simulate many different events
        mock_scan.return_value = [
            {"year": 1945, "event": f"Event {i} different content here", "story": f"Story {i}"}
            for i in range(10)
        ]
        
        result = engine_answer("năm 1945")
        
        # Should be limited to MAX_STORIES
        story_count = result["answer"].count("\n") + 1 if result["answer"] else 0
        assert story_count <= MAX_STORIES
    
    @patch('app.services.engine.scan_by_year')
    def test_different_events_kept(self, mock_scan):
        from app.services.engine import engine_answer
        
        # Simulate different events in same year
        mock_scan.return_value = [
            {"year": 1945, "event": "Cách mạng tháng Tám", "story": "Cuộc cách mạng..."},
            {"year": 1945, "event": "Tuyên ngôn độc lập", "story": "Hồ Chí Minh đọc..."},
        ]
        
        result = engine_answer("năm 1945")
        
        # Should have 2 different answers
        assert result["answer"].count("\n") == 1  # 2 stories = 1 newline


class TestEngineAnswerIntents:
    """Test intent detection."""
    
    @patch('app.services.engine.scan_by_year')
    def test_year_intent(self, mock_scan):
        from app.services.engine import engine_answer
        
        mock_scan.return_value = []
        result = engine_answer("năm 1945 có sự kiện gì?")
        
        assert result["intent"] == "year"
        mock_scan.assert_called_once_with(1945)
    
    @patch('app.services.engine.semantic_search')
    def test_definition_intent(self, mock_search):
        from app.services.engine import engine_answer
        
        mock_search.return_value = []
        result = engine_answer("Trần Hưng Đạo là ai?")
        
        assert result["intent"] == "definition"
    
    @patch('app.services.engine.semantic_search')
    def test_semantic_intent(self, mock_search):
        from app.services.engine import engine_answer
        
        mock_search.return_value = []
        result = engine_answer("chiến thắng Điện Biên Phủ")
        
        assert result["intent"] == "semantic"
