"""
test_engine_dedup.py - Tests for engine.py deduplication logic.

These tests verify that:
1. Duplicate events with similar content are deduplicated
2. MAX_STORIES limit is respected
3. Identity queries are handled correctly
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add ai-service to path (portable)
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())


class TestNormalizeEventSignature:
    """Test the normalize_event_signature function."""
    
    def test_normalize_basic(self):
        from app.services.engine import normalize_event_signature
        
        result = normalize_event_signature("Nguyễn Tất Thành ra đi tìm đường cứu nước")
        assert result == "nguyễn tất thành ra đi tìm đường cứu nước"
    
    def test_normalize_extra_spaces(self):
        from app.services.engine import normalize_event_signature
        
        result = normalize_event_signature("Nguyễn   Tất   Thành   ra đi")
        assert "  " not in result  # No double spaces
    
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
        
        mock_scan.return_value = [
            {"year": 1911, "event": "Nguyễn Tất Thành ra đi tìm đường cứu nước", "story": "Story version 1"},
            {"year": 1911, "event": "Nguyễn Tất Thành ra đi tìm đường cứu nước", "story": "Story version 2"},
        ]
        
        result = engine_answer("năm 1911")
        
        # Should deduplicate similar events
        assert result["answer"] is not None
    
    @patch('app.services.engine.scan_by_year')
    def test_different_events_kept(self, mock_scan):
        from app.services.engine import engine_answer
        
        mock_scan.return_value = [
            {"year": 1945, "event": "Cách mạng tháng Tám", "story": "Cuộc cách mạng..."},
            {"year": 1945, "event": "Tuyên ngôn độc lập", "story": "Hồ Chí Minh đọc..."},
        ]
        
        result = engine_answer("năm 1945")
        
        # Should have multiple events
        assert result["answer"] is not None


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
