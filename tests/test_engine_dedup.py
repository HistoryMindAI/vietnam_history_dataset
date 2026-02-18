"""
test_engine_dedup.py — Comprehensive tests for 3-layer deduplication.

Tests:
  1. normalize_for_dedup — year-prefix-agnostic normalization
  2. aggregate_events — docs → unique events mapping
  3. _is_similar_event — enhanced fuzzy matching
  4. deduplicate_answer — answer-level sentence dedup
  5. canonicalize_year_format — year format normalization
"""

import sys
import os

# Add ai-service to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai-service'))

from app.services.event_aggregator import normalize_for_dedup, aggregate_events
from app.services.answer_postprocessor import deduplicate_answer, canonicalize_year_format, _dedup_intra_line, _is_fuzzy_dup
from app.services.engine import _is_similar_event, compute_text_similarity


# ======================================================================
# 1. normalize_for_dedup TESTS
# ======================================================================

class TestNormalizeForDedup:
    """Test normalize_for_dedup strips year prefixes, bullets, markdown."""

    def test_empty_string(self):
        assert normalize_for_dedup("") == ""
        assert normalize_for_dedup(None) == ""

    def test_year_prefix_nam(self):
        """'Năm 2010, Sự kiện X' → normalized without year prefix"""
        result = normalize_for_dedup("Năm 2010, Sự kiện X")
        assert "sự kiện x" in result

    def test_year_prefix_parenthetical(self):
        """'(năm 2010): Đại lễ' → same as plain 'Đại lễ'"""
        a = normalize_for_dedup("(năm 2010): Đại lễ 1000 năm Thăng Long")
        b = normalize_for_dedup("Đại lễ 1000 năm Thăng Long")
        assert a == b

    def test_year_prefix_dash(self):
        """'2010 – Đại lễ' → same as plain 'Đại lễ'"""
        a = normalize_for_dedup("2010 – Đại lễ 1000 năm Thăng Long")
        b = normalize_for_dedup("Đại lễ 1000 năm Thăng Long")
        assert a == b

    def test_bullet_strip(self):
        """'- Đại lễ' → same as 'Đại lễ'"""
        a = normalize_for_dedup("- Đại lễ 1000 năm Thăng Long")
        b = normalize_for_dedup("Đại lễ 1000 năm Thăng Long")
        assert a == b

    def test_markdown_bold_strip(self):
        """'**Năm 2010:** Đại lễ' → same core text"""
        a = normalize_for_dedup("**Năm 2010:** Đại lễ 1000 năm")
        b = normalize_for_dedup("Đại lễ 1000 năm")
        assert a == b

    def test_equivalent_formats(self):
        """All these should produce the same normalized text."""
        variants = [
            "Đại lễ 1000 năm Thăng Long – Hà Nội.",
            "(năm 2010): Đại lễ 1000 năm Thăng Long – Hà Nội.",
            "2010 – Đại lễ 1000 năm Thăng Long – Hà Nội.",
            "Năm 2010, Đại lễ 1000 năm Thăng Long – Hà Nội.",
            "- Đại lễ 1000 năm Thăng Long – Hà Nội.",
            "**Năm 2010:** Đại lễ 1000 năm Thăng Long – Hà Nội.",
        ]
        normalized = [normalize_for_dedup(v) for v in variants]
        # All should be the same
        for i, n in enumerate(normalized):
            assert n == normalized[0], f"Variant {i} differs: '{n}' vs '{normalized[0]}'"


# ======================================================================
# 2. aggregate_events TESTS
# ======================================================================

class TestAggregateEvents:
    """Test aggregate_events merges duplicate docs."""

    def test_empty_list(self):
        assert aggregate_events([]) == []

    def test_exact_duplicates(self):
        """Two docs with identical stories should merge into one."""
        docs = [
            {"story": "Đại lễ 1000 năm Thăng Long", "year": 2010, "persons": ["A"]},
            {"story": "Đại lễ 1000 năm Thăng Long", "year": 2010, "persons": ["B"]},
        ]
        result = aggregate_events(docs)
        assert len(result) == 1
        # Persons should be merged
        assert set(result[0]["persons"]) == {"A", "B"}

    def test_near_duplicate_year_prefix(self):
        """Docs differing only in year prefix format should merge."""
        docs = [
            {"story": "Đại lễ 1000 năm Thăng Long – Hà Nội", "year": 2010},
            {"story": "(năm 2010): Đại lễ 1000 năm Thăng Long – Hà Nội", "year": 2010},
        ]
        result = aggregate_events(docs)
        assert len(result) == 1

    def test_different_events_preserved(self):
        """Genuinely different events should not be merged."""
        docs = [
            {"story": "Trận Bạch Đằng năm 938", "year": 938},
            {"story": "Chiến dịch Điện Biên Phủ", "year": 1954},
        ]
        result = aggregate_events(docs)
        assert len(result) == 2

    def test_keeps_longer_story(self):
        """When merging, should keep the longer, more detailed story."""
        short = {"story": "Đại lễ 1000 năm Thăng Long", "year": 2010}
        long_story = {"story": "Đại lễ 1000 năm Thăng Long – Hà Nội được tổ chức long trọng tại thủ đô", "year": 2010}
        docs = [short, long_story]
        result = aggregate_events(docs)
        assert len(result) == 1
        assert len(result[0]["story"]) >= len(long_story["story"])

    def test_year_zero_handling(self):
        """Events with year 0 should match same-text events with real years."""
        docs = [
            {"story": "Trận Bạch Đằng đánh bại quân Nam Hán", "year": 938},
            {"story": "Trận Bạch Đằng đánh bại quân Nam Hán", "year": 0},
        ]
        result = aggregate_events(docs)
        assert len(result) == 1
        # Should keep the non-zero year
        assert result[0].get("year") == 938


# ======================================================================
# 3. _is_similar_event TESTS
# ======================================================================

class TestIsSimilarEvent:
    """Test enhanced _is_similar_event with normalize_for_dedup."""

    def test_exact_match(self):
        assert _is_similar_event("đại lễ thăng long", "đại lễ thăng long")

    def test_year_prefix_difference(self):
        """Events differing only in year prefix should match."""
        assert _is_similar_event(
            "năm 2010, đại lễ 1000 năm thăng long",
            "đại lễ 1000 năm thăng long"
        )

    def test_containment(self):
        """Shorter text contained in longer text should match."""
        assert _is_similar_event(
            "đại lễ thăng long",
            "đại lễ thăng long được tổ chức long trọng"
        )

    def test_completely_different(self):
        """Completely different texts should NOT match."""
        assert not _is_similar_event(
            "trận bạch đằng năm 938",
            "chiến dịch điện biên phủ năm 1954"
        )

    def test_keyword_overlap(self):
        """Events with high keyword overlap should match."""
        kw1 = {"đại", "lễ", "thăng", "long", "nghìn", "năm"}
        kw2 = {"kỷ", "niệm", "nghìn", "năm", "thăng", "long"}
        assert _is_similar_event(
            "đại lễ nghìn năm thăng long",
            "kỷ niệm nghìn năm thăng long",
            kw1, kw2
        )


# ======================================================================
# 4. deduplicate_answer TESTS
# ======================================================================

class TestDeduplicateAnswer:
    """Test answer-level sentence dedup."""

    def test_empty_text(self):
        assert deduplicate_answer("") == ""
        assert deduplicate_answer(None) is None

    def test_no_duplicates(self):
        text = "Năm 938: Trận Bạch Đằng.\nNăm 1954: Điện Biên Phủ."
        assert deduplicate_answer(text) == text

    def test_exact_duplicate_lines(self):
        text = "Đại lễ 1000 năm Thăng Long.\nĐại lễ 1000 năm Thăng Long."
        result = deduplicate_answer(text)
        assert result.count("Đại lễ") == 1

    def test_near_duplicate_lines(self):
        """Lines differing only in year prefix should collapse."""
        text = (
            "**Năm 2010:** Đại lễ 1000 năm Thăng Long – Hà Nội.\n"
            "(năm 2010): Đại lễ 1000 năm Thăng Long – Hà Nội."
        )
        result = deduplicate_answer(text)
        assert result.count("Đại lễ") == 1

    def test_preserves_headers(self):
        """Section headers should always be kept."""
        text = "### Thời kỳ dựng nước\nSự kiện A.\n### Thời kỳ Bắc thuộc\nSự kiện B."
        result = deduplicate_answer(text)
        assert "### Thời kỳ dựng nước" in result
        assert "### Thời kỳ Bắc thuộc" in result

    def test_preserves_empty_lines(self):
        """Empty lines should be preserved for formatting."""
        text = "Trận Bạch Đằng năm 938 đánh bại quân Nam Hán.\n\nChiến dịch Điện Biên Phủ năm 1954."
        result = deduplicate_answer(text)
        lines = result.split('\n')
        # Should have 3 lines: content, empty, content
        assert len(lines) == 3
        assert lines[1] == ''


# ======================================================================
# 4b. INTRA-LINE DEDUP TESTS
# ======================================================================

# _dedup_intra_line already imported at top of file

class TestIntraLineDedup:
    """Test within-line clause deduplication."""

    def test_exact_user_reported_case(self):
        """The exact duplication pattern the user complained about."""
        text = (
            "Đại lễ 1000 năm Thăng Long – Hà Nội; Kỷ niệm nghìn năm Thăng Long – Hà Nội, "
            "mang ý nghĩa khẳng định bề dày lịch sử – văn hóa Thủ đô. "
            "(năm 2010): Đại lễ 1000 năm Thăng Long – Hà Nội; Kỷ niệm nghìn năm Thăng Long – Hà Nội, "
            "mang ý nghĩa khẳng định bề dày lịch sử – văn hóa Thủ đô."
        )
        result = _dedup_intra_line(text)
        assert result.count("Đại lễ 1000 năm") == 1, f"Got duplicate: {result}"

    def test_year_marker_split_dedup(self):
        """Content repeated before and after year marker."""
        text = "Sự kiện lịch sử quan trọng. (năm 1945): Sự kiện lịch sử quan trọng."
        result = _dedup_intra_line(text)
        assert result.count("Sự kiện lịch sử") == 1

    def test_sentence_level_dedup(self):
        """Same sentence appearing twice in a line."""
        text = "Trận Bạch Đằng đánh bại quân Nguyên. Trận Bạch Đằng đánh bại quân Nguyên."
        result = _dedup_intra_line(text)
        assert result.count("Trận Bạch Đằng") == 1

    def test_no_false_positive_short(self):
        """Short lines should not be modified."""
        text = "Năm 938."
        assert _dedup_intra_line(text) == text

    def test_no_false_positive_distinct(self):
        """Line with distinct clauses should be preserved."""
        text = "Trận Bạch Đằng năm 938 đánh bại quân Nam Hán. Ngô Quyền lên ngôi vua."
        result = _dedup_intra_line(text)
        assert "Trận Bạch Đằng" in result
        assert "Ngô Quyền" in result

    def test_dedup_answer_single_line(self):
        """deduplicate_answer should handle single-line intra-line dupes."""
        text = (
            "Đại lễ 1000 năm Thăng Long – Hà Nội. "
            "(năm 2010): Đại lễ 1000 năm Thăng Long – Hà Nội."
        )
        result = deduplicate_answer(text)
        assert result.count("Đại lễ 1000 năm") == 1


# ======================================================================
# 5. canonicalize_year_format TESTS
# ======================================================================

class TestCanonicalizeYearFormat:
    """Test year format normalization."""

    def test_parenthetical_year(self):
        result = canonicalize_year_format("(năm 2010): Sự kiện")
        assert "Năm 2010:" in result
        assert "(năm" not in result

    def test_preserves_normal_text(self):
        text = "Sự kiện năm 2010 diễn ra."
        result = canonicalize_year_format(text)
        # Should not alter inner "năm 2010" (not in parentheses at start)
        assert "năm 2010" in result


# ======================================================================
# 6. INTEGRATION TESTS
# ======================================================================

class TestIntegration:
    """Test the full dedup pipeline works together."""

    def test_full_pipeline_removes_duplicates(self):
        """Simulate the full pipeline: aggregate → deduplicate → format → post-process."""
        # Input: 3 docs, 2 are near-duplicates
        docs = [
            {"story": "Đại lễ 1000 năm Thăng Long – Hà Nội", "year": 2010, "persons": [], "places": ["Hà Nội"]},
            {"story": "(năm 2010): Đại lễ 1000 năm Thăng Long – Hà Nội", "year": 2010, "persons": [], "places": []},
            {"story": "Trận Bạch Đằng năm 938 đánh bại quân Nam Hán", "year": 938, "persons": ["Ngô Quyền"], "places": ["Bạch Đằng"]},
        ]

        # Step 1: Aggregate
        aggregated = aggregate_events(docs)
        assert len(aggregated) == 2, f"Expected 2 unique events, got {len(aggregated)}"

        # Step 2: Format answer
        lines = []
        for e in aggregated:
            year = e.get("year", 0)
            story = e.get("story", "")
            if year:
                lines.append(f"**Năm {year}:** {story}")
            else:
                lines.append(story)
        answer = "\n\n".join(lines)

        # Step 3: Post-process
        final = deduplicate_answer(answer)
        assert final.count("Thăng Long") == 1 or final.count("Đại lễ") == 1
        assert "Bạch Đằng" in final


# ======================================================================
# 7. RAPIDFUZZ _is_fuzzy_dup TESTS
# ======================================================================

class TestIsFuzzyDup:
    """Test the _is_fuzzy_dup helper using token_set_ratio."""

    def test_exact_match(self):
        assert _is_fuzzy_dup("trận bạch đằng", "trận bạch đằng") is True

    def test_containment(self):
        assert _is_fuzzy_dup("trận bạch đằng", "trận bạch đằng năm 938") is True

    def test_token_reorder(self):
        """Order-agnostic: 'Trận X năm 938' ≈ 'Năm 938 trận X'."""
        a = normalize_for_dedup("Trận Bạch Đằng năm 938")
        b = normalize_for_dedup("Năm 938 trận Bạch Đằng")
        assert _is_fuzzy_dup(a, b) is True

    def test_distinct_events(self):
        a = normalize_for_dedup("Trận Bạch Đằng đánh bại quân Nam Hán")
        b = normalize_for_dedup("Chiến dịch Điện Biên Phủ năm 1954")
        assert _is_fuzzy_dup(a, b) is False

    def test_empty_inputs(self):
        assert _is_fuzzy_dup("", "anything") is False
        assert _is_fuzzy_dup("anything", "") is False

    def test_near_duplicate_with_minor_difference(self):
        """Same event with minor wording change."""
        a = normalize_for_dedup("Ngô Quyền đánh bại quân Nam Hán tại Bạch Đằng")
        b = normalize_for_dedup("Ngô Quyền đánh tan quân Nam Hán ở Bạch Đằng")
        assert _is_fuzzy_dup(a, b) is True


# ======================================================================
# 8. TOKEN-REORDER DEDUP IN deduplicate_answer
# ======================================================================

class TestTokenReorderDedup:
    """Test that deduplicate_answer catches token-reordered duplicates."""

    def test_reordered_lines_deduplicated(self):
        """Two lines with same tokens in different order → keep only first."""
        text = (
            "**Năm 938:** Trận Bạch Đằng đánh bại quân Nam Hán.\n\n"
            "**Năm 938:** Đánh bại quân Nam Hán trận Bạch Đằng."
        )
        result = deduplicate_answer(text)
        # Should have only one line about Bạch Đằng
        lines = [l for l in result.split('\n') if l.strip()]
        assert len(lines) == 1, f"Expected 1 line, got {len(lines)}: {lines}"

    def test_distinct_events_preserved(self):
        """Distinct events should not be removed."""
        text = (
            "**Năm 938:** Trận Bạch Đằng đánh bại quân Nam Hán.\n\n"
            "**Năm 1954:** Chiến dịch Điện Biên Phủ kết thúc chiến tranh Đông Dương."
        )
        result = deduplicate_answer(text)
        assert "Bạch Đằng" in result
        assert "Điện Biên Phủ" in result
