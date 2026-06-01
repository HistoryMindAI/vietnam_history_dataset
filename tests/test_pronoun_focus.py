"""
test_pronoun_focus.py — Comprehensive unit tests for pronoun replacement logic,
including parenthetical alias safety, collective entity handling, and plural pronouns.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch

# Add ai-service to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-service"))


class TestPronounReplacement:
    """Test pronoun replacement edge cases and fixes."""

    @pytest.fixture(autouse=True)
    def mock_aliases(self):
        """Mock PERSON_ALIASES for testing."""
        mock_aliases = {
            "hồ chí minh": "hồ chí minh",
            "nguyễn tất thành": "hồ chí minh",
            "nguyễn ái quốc": "hồ chí minh",
            "bác hồ": "hồ chí minh",
            "quang trung": "nguyễn huệ",
            "nguyễn huệ": "nguyễn huệ",
            "trần hưng đạo": "trần hưng đạo",
            "trần quốc tuấn": "trần hưng đạo",
            "trưng trắc": "hai bà trưng",
            "trưng nhị": "hai bà trưng",
            "hai bà trưng": "hai bà trưng",
        }
        with patch("app.core.startup.PERSON_ALIASES", mock_aliases):
            yield

    def test_parentheses_preserved(self):
        from app.services.engine import replace_repeated_names
        text = "Năm 1789, Nguyễn Huệ (Quang Trung) đại phá quân Thanh."
        result = replace_repeated_names(text)
        # Should NOT replace Quang Trung with "ông" since it is in parentheses
        assert "Nguyễn Huệ (Quang Trung)" in result
        assert "ông" not in result

    def test_parentheses_with_tuc_la(self):
        from app.services.engine import replace_repeated_names
        text = "Quang Trung (tức Nguyễn Huệ) đại phá quân Thanh."
        result = replace_repeated_names(text)
        # Should NOT replace Nguyễn Huệ with "ông" since it is in parentheses
        assert "Quang Trung (tức Nguyễn Huệ)" in result
        assert "ông" not in result

    def test_collective_group_not_collapsed(self):
        from app.services.engine import replace_repeated_names
        text = "Năm 40, Trưng Trắc và Trưng Nhị phất cờ khởi nghĩa."
        result = replace_repeated_names(text)
        # Trưng Trắc and Trưng Nhị are distinct group members -> should NOT collapse
        assert "Trưng Trắc" in result
        assert "Trưng Nhị" in result
        assert "bà" not in result

    def test_collective_group_repeated_exact_matches(self):
        from app.services.engine import replace_repeated_names
        text = "Trưng Trắc phất cờ khởi nghĩa. Trưng Trắc là con gái Lạc tướng."
        result = replace_repeated_names(text)
        # Exact same name repeated -> second occurrence replaced by pronoun
        assert "Trưng Trắc phất cờ khởi nghĩa." in result
        assert "Bà là con gái Lạc tướng." in result

    def test_collective_group_plural_pronoun(self):
        from app.services.engine import replace_repeated_names
        text = "Hai Bà Trưng phất cờ khởi nghĩa năm 40. Hai Bà Trưng đánh đuổi quân Đông Hán."
        result = replace_repeated_names(text)
        # Second occurrence of "Hai Bà Trưng" replaced by correct plural pronoun "hai bà"
        assert "Hai Bà Trưng phất cờ" in result
        assert "Hai bà đánh đuổi quân Đông Hán." in result

    def test_standard_pronoun_replacement(self):
        from app.services.engine import replace_repeated_names
        text = "Hồ Chí Minh sinh năm 1890. Hồ Chí Minh đọc Tuyên ngôn Độc lập năm 1945."
        result = replace_repeated_names(text)
        # Hồ Chí Minh replaced by "Bác" at the start of sentence
        assert "Hồ Chí Minh sinh năm 1890." in result
        assert "Bác đọc Tuyên ngôn" in result

    def test_standard_pronoun_capitalization_inline(self):
        from app.services.engine import replace_repeated_names
        text = "Trần Hưng Đạo soạn Hịch tướng sĩ. Sau đó, Trần Hưng Đạo chỉ huy trận Bạch Đằng."
        result = replace_repeated_names(text)
        # Second occurrence inline -> replaced by lowercase "ông"
        assert "Sau đó, ông chỉ huy" in result

    def test_standard_pronoun_capitalization_sentence_start(self):
        from app.services.engine import replace_repeated_names
        text = "Trần Hưng Đạo soạn Hịch tướng sĩ. Trần Hưng Đạo chỉ huy trận Bạch Đằng."
        result = replace_repeated_names(text)
        # Second occurrence start of sentence -> replaced by capitalized "Ông"
        assert "Ông chỉ huy trận Bạch Đằng." in result
