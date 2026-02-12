"""
Test Greeting and Social Responses

Kiểm tra khả năng chatbot phản hồi các câu chào hỏi xã giao.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure ai-service is in path
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies before import
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())

import pytest


class TestGreetingResponses:
    """Test greeting and social interaction responses."""

    def test_english_hello(self):
        """Test English 'hello' greeting."""
        from app.services.engine import engine_answer
        
        result = engine_answer("hello")
        
        assert result["intent"] == "greeting"
        assert result["answer"] is not None
        assert "History Mind AI" in result["answer"]
        assert not result["no_data"]
        assert len(result["events"]) == 0

    def test_english_hi(self):
        """Test English 'hi' greeting."""
        from app.services.engine import engine_answer
        
        result = engine_answer("hi")
        
        assert result["intent"] == "greeting"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_vietnamese_xin_chao(self):
        """Test Vietnamese 'xin chào' greeting."""
        from app.services.engine import engine_answer
        
        result = engine_answer("xin chào")
        
        assert result["intent"] == "greeting"
        assert result["answer"] is not None
        assert "History Mind AI" in result["answer"]
        assert not result["no_data"]

    def test_vietnamese_chao_ban(self):
        """Test Vietnamese 'chào bạn' greeting."""
        from app.services.engine import engine_answer
        
        result = engine_answer("chào bạn")
        
        assert result["intent"] == "greeting"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_casual_alo(self):
        """Test casual 'alo' greeting."""
        from app.services.engine import engine_answer
        
        result = engine_answer("alo")
        
        assert result["intent"] == "greeting"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_good_morning(self):
        """Test 'good morning' greeting."""
        from app.services.engine import engine_answer
        
        result = engine_answer("good morning")
        
        assert result["intent"] == "greeting"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_how_are_you(self):
        """Test 'how are you' greeting."""
        from app.services.engine import engine_answer
        
        result = engine_answer("how are you")
        
        assert result["intent"] == "greeting"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_thank_you_english(self):
        """Test English 'thank you' response."""
        from app.services.engine import engine_answer
        
        result = engine_answer("thank you")
        
        assert result["intent"] == "thank"
        assert result["answer"] is not None
        assert "vui" in result["answer"].lower() or "giúp" in result["answer"].lower()
        assert not result["no_data"]

    def test_thank_you_vietnamese(self):
        """Test Vietnamese 'cảm ơn' response."""
        from app.services.engine import engine_answer
        
        result = engine_answer("cảm ơn")
        
        assert result["intent"] == "thank"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_thank_you_casual(self):
        """Test casual 'thanks' response."""
        from app.services.engine import engine_answer
        
        result = engine_answer("thanks bạn")
        
        assert result["intent"] == "thank"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_goodbye_english(self):
        """Test English 'goodbye' response."""
        from app.services.engine import engine_answer
        
        result = engine_answer("goodbye")
        
        assert result["intent"] == "goodbye"
        assert result["answer"] is not None
        assert "tạm biệt" in result["answer"].lower() or "gặp lại" in result["answer"].lower()
        assert not result["no_data"]

    def test_goodbye_vietnamese(self):
        """Test Vietnamese 'tạm biệt' response."""
        from app.services.engine import engine_answer
        
        result = engine_answer("tạm biệt")
        
        assert result["intent"] == "goodbye"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_goodbye_casual(self):
        """Test casual 'bye bye' response."""
        from app.services.engine import engine_answer
        
        result = engine_answer("bye bye")
        
        assert result["intent"] == "goodbye"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_see_you(self):
        """Test 'see you' response."""
        from app.services.engine import engine_answer
        
        result = engine_answer("see you")
        
        assert result["intent"] == "goodbye"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_greeting_with_question(self):
        """Test greeting combined with question should prioritize greeting."""
        from app.services.engine import engine_answer
        
        result = engine_answer("hello, ai là Trần Hưng Đạo?")
        
        # Should recognize greeting first
        assert result["intent"] == "greeting"
        assert result["answer"] is not None
        assert not result["no_data"]

    def test_case_insensitive_greeting(self):
        """Test greetings are case-insensitive."""
        from app.services.engine import engine_answer
        
        result1 = engine_answer("HELLO")
        result2 = engine_answer("Hello")
        result3 = engine_answer("hello")
        
        assert result1["intent"] == "greeting"
        assert result2["intent"] == "greeting"
        assert result3["intent"] == "greeting"

    def test_greeting_with_punctuation(self):
        """Test greetings with punctuation."""
        from app.services.engine import engine_answer
        
        result1 = engine_answer("hello!")
        result2 = engine_answer("xin chào?")
        
        assert result1["intent"] == "greeting"
        assert result2["intent"] == "greeting"
