"""
test_same_entity_integration.py — Integration and Unit tests for Same-Entity detection,
same-entity explanations, and their interaction with pronoun replacement.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add ai-service to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-service"))


class TestSameEntityIntegration:
    """Test Suite for Same-Entity Detection and Pronoun Replacement interaction."""

    @pytest.fixture(autouse=True)
    def mock_startup_data(self):
        """Mock startup aliases, synonyms, and index mappings for clean isolated testing."""
        mock_person_aliases = {
            "hồ chí minh": "hồ chí minh",
            "nguyễn tất thành": "hồ chí minh",
            "nguyễn ái quốc": "hồ chí minh",
            "bác hồ": "hồ chí minh",
            "quang trung": "nguyễn huệ",
            "nguyễn huệ": "nguyễn huệ",
            "trần hưng đạo": "trần hưng đạo",
            "trần quốc tuấn": "trần hưng đạo",
        }
        mock_topic_synonyms = {
            "mông cổ": "nguyên mông",
            "nguyên mông": "nguyên mông",
            "giặc nguyên": "nguyên mông",
        }
        mock_dynasty_aliases = {
            "nhà tây sơn": "tây sơn",
            "tây sơn": "tây sơn",
            "triều tây sơn": "tây sơn",
        }
        
        with patch("app.core.startup.PERSON_ALIASES", mock_person_aliases), \
             patch("app.core.startup.TOPIC_SYNONYMS", mock_topic_synonyms), \
             patch("app.core.startup.DYNASTY_ALIASES", mock_dynasty_aliases), \
             patch("app.core.startup.PERSONS_INDEX", {"hồ chí minh": [], "nguyễn huệ": [], "trần hưng đạo": []}):
            yield

    def test_detect_same_entity_persons(self):
        """Detect that 'Nguyễn Huệ' and 'Quang Trung' are the same person."""
        from app.services.engine import _detect_same_entity
        resolved = {"persons": ["Nguyễn Huệ", "Quang Trung"], "topics": [], "dynasties": []}
        
        info = _detect_same_entity("Nguyễn Huệ và Quang Trung là ai?", resolved)
        assert info is not None
        assert info["entity_type"] == "person"
        assert info["canonical"] == "nguyễn huệ"
        assert set(info["names_mentioned"]) == {"nguyễn huệ", "quang trung"}

    def test_detect_same_entity_topics(self):
        """Detect that 'Mông Cổ' and 'Nguyên Mông' are the same topic/event."""
        from app.services.engine import _detect_same_entity
        resolved = {"persons": [], "topics": ["Mông Cổ", "Nguyên Mông"], "dynasties": []}
        
        info = _detect_same_entity("quân Mông Cổ và giặc Nguyên Mông", resolved)
        assert info is not None
        assert info["entity_type"] == "topic"
        assert info["canonical"] == "nguyên mông"
        assert {"mông cổ", "nguyên mông"}.issubset(set(info["names_mentioned"]))

    def test_detect_same_entity_dynasties(self):
        """Detect that 'Nhà Tây Sơn' and 'Triều Tây Sơn' are the same dynasty."""
        from app.services.engine import _detect_same_entity
        resolved = {"persons": [], "topics": [], "dynasties": ["Nhà Tây Sơn", "Triều Tây Sơn"]}
        
        info = _detect_same_entity("nhà Tây Sơn và triều Tây Sơn khác gì nhau", resolved)
        assert info is not None
        assert info["entity_type"] == "dynasty"
        assert info["canonical"] == "tây sơn"
        assert set(info["names_mentioned"]) == {"nhà tây sơn", "triều tây sơn"}

    def test_generate_same_entity_response_person(self):
        """Verify formatted response for same person entity."""
        from app.services.engine import _generate_same_entity_response
        info = {
            "entity_type": "person",
            "entity_type_vi": "người",
            "canonical": "nguyễn huệ",
            "names_mentioned": ["nguyễn huệ", "quang trung"],
            "all_aliases": ["quang trung"],
        }
        res = _generate_same_entity_response(info)
        assert "**Nguyễn Huệ** và **Quang Trung** là **cùng một người**" in res
        assert "Tên chính: **Nguyễn Huệ**" in res
        assert "Các tên gọi khác: Quang Trung" in res

    def test_generate_same_entity_response_topic(self):
        """Verify formatted response for same topic entity."""
        from app.services.engine import _generate_same_entity_response
        info = {
            "entity_type": "topic",
            "entity_type_vi": "chủ đề",
            "canonical": "nguyên mông",
            "names_mentioned": ["mông cổ", "nguyên mông"],
            "all_aliases": ["mông cổ", "giặc nguyên"],
        }
        res = _generate_same_entity_response(info)
        assert "**Mông Cổ** và **Nguyên Mông** là **cùng một chủ đề / sự kiện**" in res
        assert "Tên chính: **Nguyên Mông**" in res
        assert "Các tên gọi khác: Mông Cổ, Giặc Nguyên" in res

    def test_generate_same_entity_response_dynasty(self):
        """Verify formatted response for same dynasty entity."""
        from app.services.engine import _generate_same_entity_response
        info = {
            "entity_type": "dynasty",
            "entity_type_vi": "triều đại",
            "canonical": "tây sơn",
            "names_mentioned": ["nhà tây sơn", "triều tây sơn"],
            "all_aliases": ["nhà tây sơn", "triều tây sơn"],
        }
        res = _generate_same_entity_response(info)
        assert "**Nhà Tây Sơn** và **Triều Tây Sơn** là **cùng một triều đại / thời kỳ**" in res
        assert "Tên chính: **Tây Sơn**" in res

    @patch("app.services.engine.scan_by_entities")
    @patch("app.services.engine.OutputVerifier")
    def test_engine_implicit_relationship_connector(self, mock_verifier, mock_scan):
        """Test implicit relationship when user asks 'Nguyễn Huệ và Quang Trung' (connector + short)."""
        from app.services.engine import engine_answer
        mock_scan.return_value = []
        
        # Mock OutputVerifier
        mock_v_inst = MagicMock()
        mock_v_inst.verify.return_value = MagicMock(passed=True, corrected_answer=None, hard_failed=False)
        mock_verifier.return_value = mock_v_inst

        res = engine_answer("Nguyễn Huệ và Quang Trung")
        # Should detect implicit relationship and prepend same-entity explanation
        assert "cùng một người" in res["answer"].lower()
        # Original names should be preserved, no pronoun replacement
        assert "ông" not in res["answer"].lower()
        assert res["no_data"] is False

    @patch("app.services.engine.scan_by_entities")
    @patch("app.services.engine.OutputVerifier")
    def test_engine_same_entity_no_pronoun_replacement(self, mock_verifier, mock_scan):
        """Verify pronoun replacement is skipped for definition queries with same entity."""
        from app.services.engine import engine_answer
        mock_scan.return_value = []

        mock_v_inst = MagicMock()
        mock_v_inst.verify.return_value = MagicMock(passed=True, corrected_answer=None, hard_failed=False)
        mock_verifier.return_value = mock_v_inst

        res = engine_answer("Quang Trung và Nguyễn Huệ là ai")
        assert "cùng một người" in res["answer"].lower()
        # original names preserved, pronoun replacement not run on the synthesized same-entity explanation
        assert "ông" not in res["answer"].lower()
        assert res["no_data"] is False

    @patch("app.services.engine.scan_by_entities")
    @patch("app.services.engine.OutputVerifier")
    def test_engine_normal_multi_entity_pronoun_replaced(self, mock_verifier, mock_scan):
        """If query is not relationship/definition/implicit same-entity, pronoun replacement should run."""
        from app.services.engine import engine_answer
        mock_scan.return_value = [
            {
                "year": 1789,
                "event": "Đại phá quân Thanh",
                "story": "Quang Trung chỉ huy trận Ngọc Hồi Đống Đa. Quang Trung đã đánh bại hoàn toàn quân Thanh.",
                "persons": ["Nguyễn Huệ"],
            }
        ]

        mock_v_inst = MagicMock()
        mock_v_inst.verify.return_value = MagicMock(passed=True, corrected_answer=None, hard_failed=False)
        mock_verifier.return_value = mock_v_inst

        res = engine_answer("Chiến tích của Quang Trung năm 1789")
        # It's a standard story retrieval about one person (not same-entity definition/implicit relation comparison),
        # so repeated name "Quang Trung" should get replaced by pronoun "ông".
        assert "ông đã đánh bại" in res["answer"].lower()

    def test_duration_guard_anniversary(self):
        """Verify anniversary/duration guard blocks year extraction but allows fact check with explicit year."""
        from app.services.intent_classifier import classify_intent
        
        # Query with 1000 years anniversary of Thang Long (should guard year 1000)
        res_anniversary = classify_intent("Kỷ niệm 1000 năm Thăng Long", year=1000)
        assert res_anniversary.duration_guard is True
        assert res_anniversary.year is None
        
        # Fact-check with 1000 years (held in 2010)
        res_fact_check = classify_intent("Kỷ niệm 1000 năm Thăng Long là vào năm 2010 đúng không?", original_query="Kỷ niệm 1000 năm Thăng Long là vào năm 2010 đúng không?")
        assert res_fact_check.is_fact_check is True
        assert res_fact_check.fact_check_year == 2010
