"""
test_timeline_format.py — Parametrized tests for centralized timeline formatter.

Tests:
1. format_timeline_entry — canonical format for all year edge cases
2. extract_year — year extraction from event dict and text fallback
3. enforce_timeline_format — per-line enforcement on full answer text
4. No duplicate year prefix
5. Pattern test: every output line matches ^Năm\\s+\\d{3,4},
"""

import re
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-service"))

from app.services.formatters.timeline_formatter import (
    extract_year,
    format_timeline_entry,
    enforce_timeline_format,
)


YEAR_PREFIX_PATTERN = re.compile(r"^Năm\s+\d{3,4}[,.]")


# ── format_timeline_entry tests ──────────────────────────────────


class TestFormatTimelineEntry:
    """format_timeline_entry is the single source of truth for year formatting."""

    @pytest.mark.parametrize("year, story, expected_prefix", [
        (1911, "Nguyễn Tất Thành ra đi tìm đường cứu nước.", "Năm 1911,"),
        (938, "Ngô Quyền đánh bại quân Nam Hán trên sông Bạch Đằng.", "Năm 938,"),
        (1954, "Chiến thắng Điện Biên Phủ.", "Năm 1954,"),
        (40, "Hai Bà Trưng khởi nghĩa.", "Năm 40,"),
    ])
    def test_basic_formatting(self, year, story, expected_prefix):
        result = format_timeline_entry(year, story)
        assert result.startswith(expected_prefix), f"Expected '{expected_prefix}', got: {result}"

    @pytest.mark.parametrize("year, story", [
        (1911, "**Năm 1911:** Nguyễn Tất Thành ra đi tìm đường cứu nước."),
        (1911, "Năm 1911, Nguyễn Tất Thành ra đi tìm đường cứu nước."),
        (1911, "Năm 1911: Nguyễn Tất Thành ra đi tìm đường cứu nước."),
        (1954, "**1954** Chiến thắng Điện Biên Phủ."),
    ])
    def test_strips_existing_prefix(self, year, story):
        """Existing year prefixes should be stripped to avoid duplication."""
        result = format_timeline_entry(year, story)
        assert result.count(f"Năm {year}") == 1, f"Duplicate year in: {result}"

    def test_no_year_returns_raw_story(self):
        result = format_timeline_entry(None, "Ngô Quyền đánh bại quân Nam Hán.")
        assert result == "Ngô Quyền đánh bại quân Nam Hán."

    def test_empty_story_with_year(self):
        result = format_timeline_entry(1911, "")
        assert result == ""

    def test_year_only_no_content(self):
        """When story is empty after stripping prefix, return 'Năm XXXX.'"""
        result = format_timeline_entry(1911, "Năm 1911")
        assert "Năm 1911" in result


# ── extract_year tests ───────────────────────────────────────────


class TestExtractYear:
    """extract_year extracts from event dict or falls back to story text."""

    def test_from_event_dict(self):
        assert extract_year({"year": 1911}, "") == 1911

    def test_fallback_from_story(self):
        assert extract_year(
            {"year": 0},
            "Khởi nghĩa Lam Sơn bùng nổ năm 1418."
        ) == 1418

    def test_fallback_from_story_no_year_key(self):
        assert extract_year(
            {},
            "Chiến thắng Điện Biên Phủ năm 1954 làm rung chuyển địa cầu."
        ) == 1954

    def test_no_year_at_all(self):
        assert extract_year({}, "Không có năm nào cả.") is None

    def test_year_none(self):
        assert extract_year({"year": None}, "năm 938 Ngô Quyền") == 938

    def test_year_out_of_range(self):
        """Years outside 40–2025 should not be returned."""
        assert extract_year({"year": 5000}, "") is None

    @pytest.mark.parametrize("story, expected", [
        ("năm 938 Ngô Quyền chiến thắng", 938),
        ("Sự kiện xảy ra vào năm 1789", 1789),
        ("Năm 1945, Tuyên ngôn Độc lập", 1945),
    ])
    def test_various_text_patterns(self, story, expected):
        assert extract_year({"year": 0}, story) == expected


# ── enforce_timeline_format tests ────────────────────────────────


class TestEnforceTimelineFormat:
    """enforce_timeline_format processes final answer per-line."""

    def test_already_formatted(self):
        text = "Năm 1911, Nguyễn Tất Thành ra đi tìm đường cứu nước."
        assert enforce_timeline_format(text) == text

    def test_missing_prefix_gets_fixed(self):
        text = "Nguyễn Tất Thành ra đi tìm đường cứu nước năm 1911, bắt đầu hành trình cứu nước."
        result = enforce_timeline_format(text)
        assert YEAR_PREFIX_PATTERN.match(result), f"Missing prefix in: {result}"

    def test_headers_preserved(self):
        text = "### Thời kỳ Bắc thuộc (111 TCN–939)\nNăm 938, Ngô Quyền đánh bại quân Nam Hán."
        result = enforce_timeline_format(text)
        assert result.startswith("### Thời kỳ")

    def test_short_lines_preserved(self):
        text = "Ok\nNăm 1911, Nguyễn Tất Thành ra đi."
        result = enforce_timeline_format(text)
        assert result.startswith("Ok")

    def test_multiline_enforcement(self):
        text = (
            "Năm 1911, Nguyễn Tất Thành ra đi tìm đường cứu nước.\n"
            "Chiến thắng Điện Biên Phủ diễn ra năm 1954, kết thúc chiến tranh Đông Dương."
        )
        result = enforce_timeline_format(text)
        lines = [l for l in result.split('\n') if l.strip() and len(l.strip()) >= 30]
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('-') or stripped.startswith('•'):
                stripped = re.sub(r'^[-•*]\s*', '', stripped)
            assert re.match(r'Năm\s+\d{3,4}[,.]', stripped), f"Missing prefix: {stripped}"


# ── No duplicate year prefix ────────────────────────────────────


class TestNoDuplicateYearPrefix:
    """Ensure year prefix is never duplicated."""

    @pytest.mark.parametrize("year, story", [
        (1911, "Năm 1911, Nguyễn Tất Thành ra đi tìm đường cứu nước."),
        (938, "**Năm 938:** Ngô Quyền chiến thắng trên sông Bạch Đằng."),
        (1954, "Năm 1954: Chiến thắng Điện Biên Phủ."),
    ])
    def test_no_duplicate_prefix(self, year, story):
        result = format_timeline_entry(year, story)
        count = len(re.findall(rf"Năm\s+{year}", result))
        assert count == 1, f"Found {count} occurrences of 'Năm {year}' in: {result}"
