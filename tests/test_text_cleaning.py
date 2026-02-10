"""
test_text_cleaning.py - Unit tests for text cleaning and formatting

Tests clean_story_text() and format_complete_answer() to prevent
duplicate text and ensure natural Vietnamese output.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Ensure ai-service is in path
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies before import
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())

from app.services.engine import clean_story_text, format_complete_answer


class TestCleanStoryText:
    """Test clean_story_text removes redundant prefixes."""

    def test_empty_string(self):
        assert clean_story_text("") == ""

    def test_none_input(self):
        assert clean_story_text(None) == ""

    def test_remove_year_prefix_nam(self):
        result = clean_story_text("Năm 1930, Thành lập Đảng Cộng sản Việt Nam")
        assert not result.startswith("Năm 1930")
        assert "Thành lập Đảng" in result

    def test_remove_year_prefix_vao_nam(self):
        result = clean_story_text("Vào năm 1945, Cách mạng Tháng Tám")
        assert not result.startswith("Vào năm")
        assert "Cách mạng Tháng Tám" in result

    def test_remove_gan_moc_prefix(self):
        result = clean_story_text("gắn mốc 1930 với Thành lập Đảng Cộng sản Việt Nam")
        assert not result.startswith("gắn mốc")
        assert "Thành lập Đảng" in result

    def test_remove_boi_canh_prefix(self):
        result = clean_story_text("Bối cảnh: Cách mạng Tháng Tám và Tuyên ngôn Độc lập")
        assert not result.startswith("Bối cảnh")
        assert "Cách mạng Tháng Tám" in result

    def test_remove_tom_tat_prefix(self):
        result = clean_story_text("Tóm tắt bối cảnh – diễn biến – kết quả của Khởi nghĩa Yên Bái")
        assert not result.startswith("Tóm tắt")
        assert "Khởi nghĩa Yên Bái" in result

    def test_remove_ke_ve_prefix(self):
        result = clean_story_text("Kể về Nguyễn Thái Học và đóng góp của ông trong Khởi nghĩa Yên Bái")
        assert "Khởi nghĩa Yên Bái" in result

    def test_remove_dien_ra_prefix(self):
        result = clean_story_text("diễn ra Cách mạng Tháng Tám")
        assert not result.startswith("diễn ra")

    def test_remove_trailing_year_parenthesis(self):
        result = clean_story_text("Cách mạng Tháng Tám (1945).")
        assert "(1945)" not in result

    def test_remove_trailing_dia_diem(self):
        result = clean_story_text("Tuyên ngôn Độc lập, địa điểm Hà Nội")
        assert "địa điểm" not in result

    def test_preserve_meaningful_content(self):
        """Text without prefixes should be preserved as-is."""
        text = "Hồ Chí Minh đọc Tuyên ngôn Độc lập tại Quảng trường Ba Đình."
        result = clean_story_text(text)
        assert result == text

    def test_combined_prefix_removal(self):
        """Multiple prefix patterns in one text."""
        text = "Năm 1945, diễn ra Cách mạng Tháng Tám"
        result = clean_story_text(text)
        assert "Cách mạng Tháng Tám" in result
        assert not result.startswith("Năm")
        assert "diễn ra" not in result


class TestFormatCompleteAnswer:
    """Test format_complete_answer produces clean, non-duplicate output."""

    def test_empty_events(self):
        assert format_complete_answer([]) is None

    def test_single_event(self):
        events = [{"year": 1945, "event": "Cách mạng Tháng Tám", "story": "Tổng khởi nghĩa giành chính quyền."}]
        result = format_complete_answer(events)
        assert result is not None
        assert "1945" in result
        assert "Tổng khởi nghĩa" in result

    def test_no_duplicate_events(self):
        """Same story text for same year should not appear twice."""
        events = [
            {"year": 1930, "event": "Năm 1930, Thành lập Đảng", "story": "Năm 1930, Thành lập Đảng"},
            {"year": 1930, "event": "Năm 1930, Thành lập Đảng", "story": "Năm 1930, Thành lập Đảng"},
        ]
        result = format_complete_answer(events)
        # Should only appear once after dedup
        count = result.lower().count("thành lập đảng")
        assert count == 1, f"Expected 1 occurrence, got {count}: {result}"

    def test_multiple_years_sorted(self):
        events = [
            {"year": 1945, "event": "Event 1945", "story": "Cách mạng Tháng Tám."},
            {"year": 1930, "event": "Event 1930", "story": "Thành lập Đảng."},
        ]
        result = format_complete_answer(events)
        # Year 1930 should appear before 1945
        pos_1930 = result.index("1930")
        pos_1945 = result.index("1945")
        assert pos_1930 < pos_1945

    def test_no_double_year_mention(self):
        """Output should not have 'Năm 1930: Năm 1930, ...'"""
        events = [{"year": 1930, "event": "Năm 1930, Thành lập Đảng", "story": "Năm 1930, Thành lập Đảng Cộng sản."}]
        result = format_complete_answer(events)
        # The year prefix should only appear once (in the header)
        count = result.count("1930")
        assert count == 1, f"Year 1930 appears {count} times: {result}"

    def test_answer_ends_with_punctuation(self):
        events = [{"year": 1945, "event": "Test event", "story": "Test story without punct"}]
        result = format_complete_answer(events)
        # Should end with period
        assert result.strip().endswith(".")

    def test_no_gan_moc_in_output(self):
        """'gắn mốc' should be cleaned out of final answer."""
        events = [
            {"year": 1930, "event": "gắn mốc 1930 với Thành lập Đảng Cộng sản Việt Nam.", "story": ""},
        ]
        result = format_complete_answer(events)
        assert "gắn mốc" not in result
        assert "Thành lập Đảng" in result
