"""
test_year_extraction.py - Unit tests for year extraction functions.

Tests: extract_single_year, extract_year_range, extract_multiple_years.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())

from app.services.engine import extract_single_year, extract_year_range, extract_multiple_years


# ===================================================================
# A. extract_single_year (12 tests)
# ===================================================================

class TestExtractSingleYear:
    def test_nam_1288(self):
        assert extract_single_year("Sự kiện năm 1288") == 1288

    def test_nam_938(self):
        assert extract_single_year("Năm 938 có gì?") == 938

    def test_nam_40(self):
        """Year 40 AD — Hai Bà Trưng uprising."""
        assert extract_single_year("Năm 40 có khởi nghĩa nào?") == 40

    def test_nam_1945(self):
        assert extract_single_year("Sự kiện năm 1945") == 1945

    def test_nam_2025_boundary(self):
        assert extract_single_year("Năm 2025") == 2025

    def test_nam_below_40_returns_none(self):
        """Years before 40 AD are out of scope."""
        assert extract_single_year("Năm 10 có gì?") is None

    def test_nam_above_2025_returns_none(self):
        assert extract_single_year("Năm 3000") is None

    def test_no_year_returns_none(self):
        assert extract_single_year("Ai là vua đầu tiên?") is None

    def test_year_in_phrase(self):
        assert extract_single_year("Cuộc kháng chiến lần thứ 3 năm 1288") == 1288

    def test_three_digit_year(self):
        assert extract_single_year("Chiến thắng năm 938") == 938

    def test_four_digit_year(self):
        assert extract_single_year("Triều đại 1802") == 1802

    def test_year_1009_ly_thai_to(self):
        assert extract_single_year("Năm 1009, Lý Công Uẩn lên ngôi") == 1009


# ===================================================================
# B. extract_year_range (10 tests)
# ===================================================================

class TestExtractYearRange:
    def test_tu_nam_den_nam(self):
        result = extract_year_range("Từ năm 1225 đến 1400")
        assert result == (1225, 1400)

    def test_giai_doan(self):
        result = extract_year_range("Giai đoạn 1010 đến 1225")
        assert result == (1010, 1225)

    def test_tu_den_with_nam(self):
        result = extract_year_range("Từ năm 938 đến năm 1009")
        assert result == (938, 1009)

    def test_dash_separator(self):
        result = extract_year_range("Từ 1802-1945")
        assert result == (1802, 1945)

    def test_en_dash_separator(self):
        result = extract_year_range("Từ 1225–1400")
        assert result == (1225, 1400)

    def test_toi_separator(self):
        result = extract_year_range("Từ năm 1225 tới 1400")
        assert result == (1225, 1400)

    def test_invalid_range_start_gt_end(self):
        """start > end should return None."""
        assert extract_year_range("Từ năm 1400 đến 1225") is None

    def test_out_of_scope_years(self):
        assert extract_year_range("Từ năm 10 đến 30") is None

    def test_no_range_returns_none(self):
        assert extract_year_range("Chiến thắng Bạch Đằng") is None

    def test_single_year_not_range(self):
        """A single year should NOT be detected as range."""
        assert extract_year_range("Năm 1288 có gì?") is None


# ===================================================================
# C. extract_multiple_years (8 tests)
# ===================================================================

class TestExtractMultipleYears:
    def test_two_years_va(self):
        result = extract_multiple_years("Năm 938 và năm 1288")
        assert result == [938, 1288]

    def test_three_years(self):
        result = extract_multiple_years("Năm 40, năm 938, năm 1288")
        assert result == [40, 938, 1288]

    def test_single_year_returns_none(self):
        """Single year should NOT be returned (needs 2+)."""
        assert extract_multiple_years("Năm 1288") is None

    def test_range_query_returns_none(self):
        """Year range should be handled separately, not as multi-year."""
        assert extract_multiple_years("Từ năm 1225 đến 1400") is None

    def test_no_years_returns_none(self):
        assert extract_multiple_years("Ai là vua?") is None

    def test_duplicate_years_removed(self):
        result = extract_multiple_years("Năm 1288 và năm 1288 và 938")
        assert result == [938, 1288]  # Sorted, deduplicated

    def test_sorted_output(self):
        result = extract_multiple_years("Năm 1945 và năm 938")
        assert result == [938, 1945]

    def test_mixed_format(self):
        result = extract_multiple_years("Sự kiện 1284 và 1288")
        assert result == [1284, 1288]
