"""
test_engine_dedup.py - Tests for engine.py deduplication and utility logic.

These tests verify that:
1. Text cleaning works correctly
2. Keyword extraction works correctly
3. Deduplication logic handles duplicates and merges info
4. Identity queries are handled correctly
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


class TestCleanStoryText:
    """Test the clean_story_text function."""
    
    def test_clean_basic_prefix(self):
        from app.services.engine import clean_story_text
        result = clean_story_text("Năm 1945, Cách mạng tháng Tám thành công.")
        assert result == "Cách mạng tháng Tám thành công."

    def test_clean_technical_prefix(self):
        from app.services.engine import clean_story_text
        result = clean_story_text("Câu hỏi nhắm tới sự kiện Chiến dịch Điện Biên Phủ.")
        assert result == "Chiến dịch Điện Biên Phủ."

    def test_clean_trailing_year(self):
        from app.services.engine import clean_story_text
        result = clean_story_text("Sự kiện A xảy ra (1945).")
        assert result == "Sự kiện A xảy ra"

    def test_clean_empty(self):
        from app.services.engine import clean_story_text
        assert clean_story_text("") == ""
        assert clean_story_text(None) == ""


class TestExtractCoreKeywords:
    """Test the extract_core_keywords function."""

    def test_extract_keywords_basic(self):
        from app.services.engine import extract_core_keywords
        text = "Chiến thắng Bạch Đằng năm 1288"
        keywords = extract_core_keywords(text)
        # "năm" is stop word, "1288" is excluded by len > 2 check if it's considered specific
        # Actually numbers are kept if len > 2. "1288" len is 4.
        assert "chiến" in keywords
        assert "thắng" in keywords
        assert "bạch" in keywords
        assert "đằng" in keywords
        assert "năm" not in keywords

    def test_extract_keywords_stop_words(self):
        from app.services.engine import extract_core_keywords
        text = "Sự kiện lịch sử Việt Nam với những chiến công"
        keywords = extract_core_keywords(text)
        # All these should be stop words
        assert len(keywords) == 2 # "chiến", "công" might remain
        assert "chiến" in keywords
        assert "công" in keywords
        assert "lịch" not in keywords
        assert "sử" not in keywords


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
            {"year": 1911, "event": "Nguyễn Tất Thành ra đi tìm đường cứu nước", "story": "Story version 1", "persons": [], "places": []},
            {"year": 1911, "event": "Nguyễn Tất Thành ra đi tìm đường cứu nước", "story": "Story version 2 is longer", "persons": [], "places": []},
        ]
        
        result = engine_answer("năm 1911")
        
        # Should deduplicate similar events
        # We expect 1 event because they are similar
        assert len(result["events"]) == 1
        assert result["events"][0]["story"] == "Story version 2 is longer"
    
    @patch('app.services.engine.scan_by_year')
    def test_different_events_kept(self, mock_scan):
        from app.services.engine import engine_answer
        
        mock_scan.return_value = [
            {"year": 1945, "event": "Cách mạng tháng Tám", "story": "Cuộc cách mạng...", "persons": [], "places": []},
            {"year": 1945, "event": "Tuyên ngôn độc lập", "story": "Hồ Chí Minh đọc...", "persons": [], "places": []},
        ]
        
        result = engine_answer("năm 1945")
        
        # Should have multiple events (dissimilar)
        assert len(result["events"]) == 2


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
