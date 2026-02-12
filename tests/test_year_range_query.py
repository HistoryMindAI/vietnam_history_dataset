"""
Test Year Range Query

Kiểm tra khả năng xử lý query về khoảng thời gian (year range).
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from collections import defaultdict

# Ensure ai-service is in path
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

# Mock heavy dependencies before import
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())

import pytest


# Mock data for testing
MOCK_EVENTS = [
    {
        "year": 40,
        "event": "Khởi nghĩa Hai Bà Trưng",
        "story": "Trưng Trắc và Trưng Nhị khởi nghĩa chống Hán.",
        "tone": "heroic",
        "persons": ["Hai Bà Trưng"],
        "persons_all": ["Trưng Trắc", "Trưng Nhị"],
        "places": [],
        "dynasty": "Trưng Vương",
        "keywords": ["khởi_nghĩa"],
        "title": "Khởi nghĩa Hai Bà Trưng"
    },
    {
        "year": 938,
        "event": "Trận Bạch Đằng lần 1",
        "story": "Ngô Quyền đánh bại quân Nam Hán.",
        "tone": "heroic",
        "persons": ["Ngô Quyền"],
        "persons_all": ["Ngô Quyền"],
        "places": ["Bạch Đằng"],
        "dynasty": "Ngô",
        "keywords": ["bạch_đằng", "chiến_thắng"],
        "title": "Trận Bạch Đằng"
    },
    {
        "year": 1288,
        "event": "Trận Bạch Đằng lần 3",
        "story": "Trần Hưng Đạo đánh bại quân Nguyên.",
        "tone": "heroic",
        "persons": ["Trần Hưng Đạo"],
        "persons_all": ["Trần Hưng Đạo"],
        "places": ["Bạch Đằng"],
        "dynasty": "Trần",
        "keywords": ["bạch_đằng", "chiến_thắng", "nguyên"],
        "title": "Trận Bạch Đằng"
    },
    {
        "year": 1945,
        "event": "Cách mạng tháng Tám",
        "story": "Cách mạng tháng Tám thành công.",
        "tone": "heroic",
        "persons": ["Hồ Chí Minh"],
        "persons_all": ["Hồ Chí Minh"],
        "places": ["Hà Nội"],
        "dynasty": "",
        "keywords": ["cách_mạng", "độc_lập"],
        "title": "Cách mạng tháng Tám"
    },
    {
        "year": 2025,
        "event": "Sự kiện hiện đại",
        "story": "Sự kiện trong năm 2025.",
        "tone": "neutral",
        "persons": [],
        "persons_all": [],
        "places": [],
        "dynasty": "",
        "keywords": [],
        "title": "Sự kiện 2025"
    },
]


def _setup_mocks():
    """Setup mock data for tests."""
    import app.core.startup as startup
    
    startup.DOCUMENTS = list(MOCK_EVENTS)
    startup.DOCUMENTS_BY_YEAR = defaultdict(list)
    for doc in startup.DOCUMENTS:
        y = doc.get("year")
        if y is not None:
            startup.DOCUMENTS_BY_YEAR[y].append(doc)
    
    startup.PERSONS_INDEX = defaultdict(list)
    startup.DYNASTY_INDEX = defaultdict(list)
    startup.KEYWORD_INDEX = defaultdict(list)
    startup.PLACES_INDEX = defaultdict(list)
    
    for idx, doc in enumerate(startup.DOCUMENTS):
        all_persons = set(doc.get("persons", []) + doc.get("persons_all", []))
        for person in all_persons:
            startup.PERSONS_INDEX[person.strip().lower()].append(idx)
        dynasty = doc.get("dynasty", "").strip().lower()
        if dynasty:
            startup.DYNASTY_INDEX[dynasty].append(idx)
        for kw in doc.get("keywords", []):
            startup.KEYWORD_INDEX[kw.lower().replace("_", " ")].append(idx)
        for place in doc.get("places", []):
            startup.PLACES_INDEX[place.strip().lower()].append(idx)
    
    startup.PERSON_ALIASES = {}
    startup.DYNASTY_ALIASES = {}
    startup.TOPIC_SYNONYMS = {}


class TestYearRangeExtraction:
    """Test year range extraction from queries."""

    def test_extract_year_range_standard_format(self):
        """Test standard format: 'từ năm X đến năm Y'."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("từ năm 40 đến năm 2025")
        assert result == (40, 2025)

    def test_extract_year_range_short_format(self):
        """Test short format: 'năm X đến Y'."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("năm 40 đến 2025")
        assert result == (40, 2025)

    def test_extract_year_range_dash_format(self):
        """Test dash format: 'X-Y'."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("40-2025")
        assert result == (40, 2025)

    def test_extract_year_range_english_from_to(self):
        """Test English format: 'from X to Y'."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("from 40 to 2025")
        assert result == (40, 2025)

    def test_extract_year_range_english_between(self):
        """Test English format: 'between X and Y'."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("between 40 and 2025")
        assert result == (40, 2025)

    def test_extract_year_range_giai_doan(self):
        """Test 'giai đoạn' format."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("giai đoạn 40-2025")
        assert result == (40, 2025)

    def test_extract_year_range_with_context(self):
        """Test year range extraction with surrounding context."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("Hãy kể cho tôi từ năm 40 đến năm 2025 có những sự kiện gì")
        assert result == (40, 2025)

    def test_extract_year_range_invalid_order(self):
        """Test invalid year range (end < start)."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("từ năm 2025 đến năm 40")
        assert result is None

    def test_extract_year_range_out_of_bounds(self):
        """Test year range out of valid bounds."""
        from app.services.engine import extract_year_range
        
        result = extract_year_range("từ năm 3000 đến năm 4000")
        assert result is None


class TestYearRangeQuery:
    """Test year range query functionality."""

    def setup_method(self):
        _setup_mocks()

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_standard(self, mock_scan):
        """Test standard year range query."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        result = engine_answer("từ năm 40 đến năm 2025 có những sự kiện gì")
        
        assert result["intent"] == "year_range"
        assert not result["no_data"]
        assert len(result["events"]) > 0
        
        # Should call scan_by_year_range with correct parameters
        mock_scan.assert_called_once_with(40, 2025)

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_all_events_included(self, mock_scan):
        """Test that events in range are included."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        result = engine_answer("từ năm 40 đến năm 2025")
        
        events = result["events"]
        years = [e.get("year") for e in events]
        
        # Should have multiple events from the range
        assert len(years) >= 3, f"Expected at least 3 events, got {len(years)}"
        
        # Should have some key years
        assert 40 in years or 938 in years or 1945 in years, "Should have at least one major event"

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_short_format(self, mock_scan):
        """Test short format year range query."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        result = engine_answer("năm 40 đến 2025")
        
        assert result["intent"] == "year_range"
        assert not result["no_data"]
        mock_scan.assert_called_once_with(40, 2025)

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_dash_format(self, mock_scan):
        """Test dash format year range query."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        result = engine_answer("40-2025 có sự kiện gì")
        
        assert result["intent"] == "year_range"
        assert not result["no_data"]
        mock_scan.assert_called_once_with(40, 2025)

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_english(self, mock_scan):
        """Test English year range query."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        result = engine_answer("from 40 to 2025")
        
        assert result["intent"] == "year_range"
        assert not result["no_data"]
        mock_scan.assert_called_once_with(40, 2025)

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_various_phrasings(self, mock_scan):
        """Test various phrasings of year range query."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        queries = [
            "từ năm 40 đến năm 2025 có những sự kiện gì",
            "liệt kê sự kiện từ 40 đến 2025",
            "kể cho tôi từ năm 40 đến 2025",
            "40-2025 có gì",
            "giai đoạn 40-2025",
            "between 40 and 2025",
        ]
        
        for query in queries:
            result = engine_answer(query)
            assert result["intent"] == "year_range", f"Failed for query: {query}"
            assert not result["no_data"], f"No data for query: {query}"
            assert len(result["events"]) > 0, f"No events for query: {query}"

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_answer_format(self, mock_scan):
        """Test that answer is properly formatted."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        result = engine_answer("từ năm 40 đến năm 2025")
        
        answer = result["answer"]
        assert answer is not None
        assert len(answer) > 0
        
        # Answer should mention years
        assert "40" in answer or "Năm 40" in answer
        assert "2025" in answer or "Năm 2025" in answer

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_context7_not_too_strict(self, mock_scan):
        """Test that Context7 doesn't filter out valid events in year range."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        result = engine_answer("từ năm 40 đến năm 2025")
        
        # Should have multiple events (Context7 should not filter too strictly for range queries)
        assert len(result["events"]) >= 3

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_query_chronological_order(self, mock_scan):
        """Test that events are in chronological order."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        result = engine_answer("từ năm 40 đến năm 2025")
        
        events = result["events"]
        years = [e.get("year") for e in events]
        
        # Years should be in ascending order (or at least not descending)
        for i in range(len(years) - 1):
            assert years[i] <= years[i + 1], f"Events not in chronological order: {years}"


class TestYearRangeEdgeCases:
    """Test edge cases for year range queries."""

    def setup_method(self):
        _setup_mocks()

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_single_year_span(self, mock_scan):
        """Test year range with very small span."""
        mock_scan.return_value = [MOCK_EVENTS[0]]
        
        from app.services.engine import engine_answer
        
        result = engine_answer("từ năm 40 đến năm 50")
        
        assert result["intent"] == "year_range"
        assert not result["no_data"]

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_very_large_span(self, mock_scan):
        """Test year range with very large span."""
        mock_scan.return_value = MOCK_EVENTS
        
        from app.services.engine import engine_answer
        
        # Use valid year range (40 is minimum)
        result = engine_answer("từ năm 40 đến năm 2025")
        
        assert result["intent"] == "year_range"
        assert not result["no_data"]

    @patch("app.services.engine.scan_by_year_range")
    def test_year_range_no_events_in_range(self, mock_scan):
        """Test year range with no events."""
        mock_scan.return_value = []
        
        from app.services.engine import engine_answer
        
        result = engine_answer("từ năm 3000 đến năm 3100")
        
        # Should handle gracefully
        assert result["no_data"] or len(result["events"]) == 0
