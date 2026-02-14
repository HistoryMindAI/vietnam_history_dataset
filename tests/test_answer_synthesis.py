"""
test_answer_synthesis.py — Test Suite for Answer Synthesis V2

~30 test cases covering:
- Data scope answers (Principle 5)
- When-question answers (Principle 3)
- Who-question answers
- List answers with period grouping (Principle 4)
- What-question answers
- Edge cases
"""
import pytest
from unittest.mock import patch
from app.services.intent_classifier import QueryAnalysis
from app.services.answer_synthesis import (
    synthesize_answer,
    _build_when_answer,
    _build_who_answer,
    _build_list_answer,
    _build_what_answer,
    _handle_data_scope,
    _get_period_for_year,
)


# ===================================================================
# SAMPLE DATA
# ===================================================================

SAMPLE_EVENTS = [
    {"year": 1911, "story": "Nguyễn Tất Thành rời Bến Nhà Rồng ra đi tìm đường cứu nước.", "title": "Bác Hồ ra đi tìm đường cứu nước"},
    {"year": 1930, "story": "Đảng Cộng sản Việt Nam được thành lập.", "title": "Thành lập Đảng"},
    {"year": 1945, "story": "Cách mạng Tháng Tám thành công. Bác Hồ đọc Tuyên ngôn Độc lập.", "title": "Cách mạng Tháng Tám"},
    {"year": 1954, "story": "Chiến thắng Điện Biên Phủ, kết thúc kháng chiến chống Pháp.", "title": "Điện Biên Phủ"},
    {"year": 1975, "story": "Giải phóng miền Nam, thống nhất đất nước.", "title": "Giải phóng miền Nam"},
]


# ===================================================================
# 1. DATA SCOPE HANDLER
# ===================================================================

class TestDataScope:
    """Test data scope answer generation."""

    @patch("app.services.answer_synthesis.startup")
    def test_data_scope_with_docs(self, mock_startup):
        mock_startup.DOCUMENTS = [
            {"year": 40}, {"year": 938}, {"year": 1945}, {"year": 2025}
        ]
        answer = _handle_data_scope()
        assert "40" in answer
        assert "2025" in answer
        assert "4" in answer  # 4 docs

    @patch("app.services.answer_synthesis.startup")
    def test_data_scope_no_docs(self, mock_startup):
        mock_startup.DOCUMENTS = []
        answer = _handle_data_scope()
        assert "40" in answer  # default fallback
        assert "2025" in answer

    @patch("app.services.answer_synthesis.startup")
    def test_data_scope_no_years(self, mock_startup):
        mock_startup.DOCUMENTS = [{"story": "test"}]
        answer = _handle_data_scope()
        assert "giai đoạn" in answer


# ===================================================================
# 2. WHEN-QUESTION ANSWERS (Principle 3)
# ===================================================================

class TestWhenAnswer:
    """Test focused when-question answers."""

    def test_when_answer_returns_year(self):
        analysis = QueryAnalysis(intent="year_specific", question_type="when")
        answer = _build_when_answer(SAMPLE_EVENTS[:1], analysis)
        assert "1911" in answer
        assert "Nguyễn Tất Thành" in answer

    def test_when_answer_no_data_dump(self):
        """When-questions should NOT return multiple events."""
        analysis = QueryAnalysis(intent="person_query", question_type="when")
        answer = _build_when_answer(SAMPLE_EVENTS, analysis)
        # Should return only the first best match
        assert "1911" in answer
        # Should NOT contain all years
        assert answer.count("**") <= 2  # Only one year bold

    def test_when_answer_empty(self):
        analysis = QueryAnalysis(intent="year_specific", question_type="when")
        answer = _build_when_answer([], analysis)
        assert answer is None


# ===================================================================
# 3. WHO-QUESTION ANSWERS
# ===================================================================

class TestWhoAnswer:
    """Test who-question answers about persons."""

    def test_who_answer(self):
        analysis = QueryAnalysis(intent="definition", question_type="who")
        answer = _build_who_answer(SAMPLE_EVENTS[:3], analysis)
        assert answer is not None
        assert "1911" in answer
        assert "1930" in answer

    def test_who_answer_limits_events(self):
        """Who-answers should limit to 5 events max."""
        many_events = SAMPLE_EVENTS * 3  # 15 events
        analysis = QueryAnalysis(intent="definition", question_type="who")
        answer = _build_who_answer(many_events, analysis)
        # Count how many year markers appear
        year_count = answer.count("**Năm ")
        assert year_count <= 5

    def test_who_answer_deduplicates(self):
        """Should not repeat same story."""
        dup_events = [SAMPLE_EVENTS[0], SAMPLE_EVENTS[0]]
        analysis = QueryAnalysis(intent="definition", question_type="who")
        answer = _build_who_answer(dup_events, analysis)
        assert answer.count("1911") == 1


# ===================================================================
# 4. LIST ANSWERS WITH PERIOD GROUPING (Principle 4)
# ===================================================================

class TestListAnswer:
    """Test list answer generation with period grouping."""

    def test_list_answer(self):
        analysis = QueryAnalysis(intent="year_range", question_type="list")
        answer = _build_list_answer(SAMPLE_EVENTS, analysis)
        assert answer is not None

    def test_list_answer_empty(self):
        analysis = QueryAnalysis(intent="year_range", question_type="list")
        answer = _build_list_answer([], analysis)
        assert answer is None

    def test_list_deduplicates(self):
        dup = [SAMPLE_EVENTS[0], SAMPLE_EVENTS[0]]
        analysis = QueryAnalysis(intent="year_range", question_type="list")
        answer = _build_list_answer(dup, analysis)
        assert answer.count("1911") == 1


# ===================================================================
# 5. WHAT-QUESTION ANSWERS
# ===================================================================

class TestWhatAnswer:
    """Test what-question event answers."""

    def test_what_answer(self):
        analysis = QueryAnalysis(intent="event_query", question_type="what")
        answer = _build_what_answer(SAMPLE_EVENTS[:2], analysis)
        assert "1911" in answer
        assert "1930" in answer

    def test_what_answer_limits_to_7(self):
        many = SAMPLE_EVENTS * 3
        analysis = QueryAnalysis(intent="event_query", question_type="what")
        answer = _build_what_answer(many, analysis)
        year_count = answer.count("**Năm ")
        assert year_count <= 7

    def test_what_answer_empty(self):
        analysis = QueryAnalysis(intent="event_query", question_type="what")
        answer = _build_what_answer([], analysis)
        assert answer is None


# ===================================================================
# 6. PERIOD GROUPING UTILS
# ===================================================================

class TestPeriodGrouping:
    """Test historical period classification."""

    def test_bac_thuoc(self):
        assert _get_period_for_year(100) == "Thời Bắc thuộc"

    def test_tran(self):
        assert _get_period_for_year(1285) == "Thời Trần"

    def test_nguyen(self):
        assert _get_period_for_year(1850) == "Thời Nguyễn"

    def test_khang_chien_phap(self):
        assert _get_period_for_year(1950) == "Cách mạng tháng Tám & Kháng chiến chống Pháp"

    def test_khang_chien_my(self):
        assert _get_period_for_year(1968) == "Kháng chiến chống Mỹ"

    def test_doi_moi(self):
        assert _get_period_for_year(1986) == "Thống nhất – Đổi mới – Hiện đại"


# ===================================================================
# 7. SYNTHESIS INTEGRATION TESTS
# ===================================================================

class TestSynthesizeAnswer:
    """Test the main synthesize_answer function."""

    @patch("app.services.answer_synthesis.startup")
    def test_data_scope_intent(self, mock_startup):
        mock_startup.DOCUMENTS = [{"year": 40}, {"year": 2025}]
        analysis = QueryAnalysis(intent="data_scope", question_type="scope")
        answer = synthesize_answer(analysis, [])
        assert "40" in answer

    def test_when_intent(self):
        analysis = QueryAnalysis(intent="year_specific", question_type="when")
        answer = synthesize_answer(analysis, SAMPLE_EVENTS)
        assert "1911" in answer

    def test_who_intent(self):
        analysis = QueryAnalysis(intent="definition", question_type="who")
        answer = synthesize_answer(analysis, SAMPLE_EVENTS[:2])
        assert answer is not None

    def test_list_intent(self):
        analysis = QueryAnalysis(intent="year_range", question_type="list")
        answer = synthesize_answer(analysis, SAMPLE_EVENTS)
        assert answer is not None

    def test_what_intent(self):
        analysis = QueryAnalysis(intent="event_query", question_type="what")
        answer = synthesize_answer(analysis, SAMPLE_EVENTS[:2])
        assert answer is not None

    def test_no_events(self):
        analysis = QueryAnalysis(intent="semantic", question_type="what")
        answer = synthesize_answer(analysis, [])
        assert answer is None
