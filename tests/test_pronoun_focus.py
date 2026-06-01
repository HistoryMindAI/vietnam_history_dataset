"""
test_pronoun_focus.py — Comprehensive unit tests for pronoun replacement logic,
including parenthetical alias safety, collective entity handling, and plural pronouns.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

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
            "các vua hùng": "hùng vương",
            "hùng vương": "hùng vương",
            "vua hùng": "hùng vương",
            "bà triệu": "bà triệu",
            "triệu thị trinh": "bà triệu",
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

    def test_dynamic_female_prefix_detection(self):
        from app.services.engine import replace_repeated_names
        # Test that any name containing 'bà' is dynamically treated as female
        text = "Bà Triệu phất cờ khởi nghĩa năm 248. Bà Triệu chống lại quân Đông Ngô."
        result = replace_repeated_names(text)
        assert "Bà Triệu phất cờ" in result
        assert "Bà chống lại quân" in result

    def test_dynamic_collective_plural_vua_hung(self):
        from app.services.engine import replace_repeated_names
        text = "Các vua Hùng dựng nước Văn Lang. Các vua Hùng truyền được 18 đời."
        result = replace_repeated_names(text)
        assert "Các vua Hùng dựng nước" in result
        assert "Các vua truyền được" in result

    def test_capitalization_after_question_and_exclamation(self):
        from app.services.engine import replace_repeated_names
        text = "Hồ Chí Minh đọc tuyên ngôn! Hồ Chí Minh lúc đó vô cùng xúc động."
        result = replace_repeated_names(text)
        assert "Bác lúc đó vô" in result  # Starts sentence after '! ' -> capitalized to 'Bác'

    def test_protected_compound_nouns(self):
        from app.services.engine import replace_repeated_names
        # 'Chiến dịch Hồ Chí Minh' and 'Thành phố Hồ Chí Minh' are protected and should not be touched
        text = "Hồ Chí Minh là lãnh tụ vĩ đại. Chiến dịch Hồ Chí Minh mang tên Người."
        result = replace_repeated_names(text)
        assert "Hồ Chí Minh là lãnh tụ" in result
        assert "Chiến dịch Hồ Chí Minh" in result  # Unmodified!

    def test_overlapping_aliases_resolution(self):
        from app.services.engine import replace_repeated_names
        # Trần Hưng Đạo and Trần Quốc Tuấn are the same canonical entity -> second is replaced
        text = "Trần Quốc Tuấn soạn Hịch tướng sĩ. Trần Hưng Đạo chỉ huy quân đội đánh Nguyên Mông."
        result = replace_repeated_names(text)
        assert "Trần Quốc Tuấn soạn" in result
        assert "Ông chỉ huy quân đội" in result

    def test_empty_and_short_inputs(self):
        from app.services.engine import replace_repeated_names
        assert replace_repeated_names("") == ""
        assert replace_repeated_names(None) is None
        assert replace_repeated_names("short") == "short"

    # ================================================================
    # ADVANCED BRANCH AND safeguARD COVERAGE TESTS
    # ================================================================

    def test_get_pronoun_direct_fallback_branches(self):
        """Directly call _get_pronoun to cover fallback (empty matched_name) branches."""
        from app.services.engine import _get_pronoun
        
        # Test fallback branches (when matched_name is empty/None)
        assert _get_pronoun("hai bà trưng", "") == "hai bà"
        assert _get_pronoun("hùng vương", "") == "các vua"
        
        # Test specific list patterns in matched_lower
        assert _get_pronoun("hùng vương", "18 đời vua hùng") == "các vua"
        assert _get_pronoun("bà triệu", "Triệu Thị Trinh") == "bà"
        assert _get_pronoun("triệu thị trinh", "") == "bà"

    def test_is_inside_parentheses_nested_and_mismatched(self):
        """Test nested and mismatched parentheses scenarios in _is_inside_parentheses."""
        from app.services.engine import _is_inside_parentheses
        
        # Nested set
        text = "Nguyễn Huệ ((Quang Trung)) đại phá quân Thanh."
        # "Quang Trung" is at index 14 to 25
        assert _is_inside_parentheses(text, 14, 25) is True
        
        # Mismatched set
        text = "(năm 1789) Nguyễn Huệ (Quang Trung)"
        # "Nguyễn Huệ" is at index 11 to 22 (outside parenthetical sets)
        assert _is_inside_parentheses(text, 11, 22) is False

    def test_is_protected_position_multiple_occurrences(self):
        """Test multiple occurrences of a protected compound in _is_protected_position."""
        from app.services.engine import replace_repeated_names
        
        # Both mentions are inside 'Thành phố Hồ Chí Minh' -> neither replaced by Bác
        text = "Chào mừng tới Thành phố Hồ Chí Minh và Thành phố Hồ Chí Minh."
        result = replace_repeated_names(text)
        assert result == text

    def test_replace_repeated_names_non_string(self):
        """Test replace_repeated_names handles non-string inputs safely."""
        from app.services.engine import replace_repeated_names
        assert replace_repeated_names(1234567890) == 1234567890

    def test_replace_repeated_names_safeguard_checks(self):
        """Test replace_repeated_names exits gracefully when startup pointers are missing/empty."""
        import app.core.startup as startup
        from app.services.engine import replace_repeated_names
        
        text = "Hồ Chí Minh sinh năm 1890. Hồ Chí Minh đọc Tuyên ngôn Độc lập."
        
        # 1. PERSON_ALIASES does not exist on startup
        with patch("app.core.startup.PERSON_ALIASES", {}):
            assert replace_repeated_names(text) == text
            
        # 2. PERSON_ALIASES is deleted
        with patch("app.core.startup.PERSON_ALIASES", None):
            # Deleting the attribute dynamically
            if hasattr(startup, 'PERSON_ALIASES'):
                delattr(startup, 'PERSON_ALIASES')
            try:
                assert replace_repeated_names(text) == text
            finally:
                startup.PERSON_ALIASES = {} # Restore to avoid breaking other tests

    def test_replace_repeated_names_short_alias_skipped(self):
        """Test that single-character alias names are skipped to avoid false positives."""
        from app.services.engine import replace_repeated_names
        
        mock_short = {"x": "hồ chí minh"}
        with patch("app.core.startup.PERSON_ALIASES", mock_short):
            text = "Nhân vật X đã lãnh đạo cách mạng. Nhân vật X tiếp tục công việc."
            # 'x' has length 1 -> skipped from match groups -> no pronoun replacement
            assert replace_repeated_names(text) == text

    def test_replace_repeated_names_word_boundaries_exact(self):
        """Test word boundary checks for name containment within longer words."""
        from app.services.engine import replace_repeated_names
        
        # "Nguyễn" is in "Nguyễnhữu" but does not have word boundaries -> should not match
        text = "Nguyễn Huệ soạn chiến dịch. Nguyễnhữu là người khác."
        result = replace_repeated_names(text)
        assert "Nguyễnhữu" in result
        assert "ông" not in result

    def test_single_char_pronoun_capitalization(self):
        """Test capitalization of a mocked single-character pronoun at sentence start."""
        from app.services.engine import replace_repeated_names
        
        # Mock 'hồ chí minh' mapping to a single character pronoun 'u' for test coverage
        with patch("app.services.engine._get_pronoun", return_value="u"):
            text = "Hồ Chí Minh là lãnh tụ. Hồ Chí Minh đọc Tuyên ngôn."
            result = replace_repeated_names(text)
            # Replaced at start of sentence -> capitalized to 'U'
            assert "U đọc Tuyên ngôn." in result
