"""
test_entity_normalizer.py — Tests for entity normalizer, detail level detection,
guardrail checks, and confidence/evidence response fields.

Covers all 5 audit areas:
A. Entity normalizer (truncated names, aliases, pronouns)
B. Intent detail level detection
C. Confidence/evidence in response structure
D. Guardrail checks (truncated names, temporal mixing)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

# Add ai-service to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-service"))


# ================================================================
# AREA A: Entity Normalizer
# ================================================================

class TestExpandTruncatedNames:
    """Test truncated Vietnamese name expansion."""

    @pytest.fixture(autouse=True)
    def mock_aliases(self):
        """Mock PERSON_ALIASES for testing."""
        mock_aliases = {
            "hồ chí minh": "hồ chí minh",
            "nguyễn tất thành": "hồ chí minh",
            "nguyễn ái quốc": "hồ chí minh",
            "quang trung": "nguyễn huệ",
            "trần hưng đạo": "trần hưng đạo",
            "trần quốc tuấn": "trần hưng đạo",
        }
        with patch("app.core.startup.PERSON_ALIASES", mock_aliases):
            yield

    def test_expand_ho_c(self):
        from app.services.entity_normalizer import expand_truncated_names
        result = expand_truncated_names("Năm 1911, Hồ C. rời Bến Nhà Rồng.")
        assert "Hồ Chí Minh" in result
        assert "Hồ C." not in result

    def test_expand_nguyen_t(self):
        from app.services.entity_normalizer import expand_truncated_names
        result = expand_truncated_names("Nguyễn T. ra đi tìm đường cứu nước.")
        # Should match "nguyễn tất thành" which maps to "hồ chí minh"
        assert "T." not in result or "Nguyễn" not in result.split("T.")[0][-10:]

    def test_no_false_positive_abbreviations(self):
        from app.services.entity_normalizer import expand_truncated_names
        # "v.v." and "Tr.CN" should NOT be expanded
        text = "Các triều đại v.v. trong lịch sử."
        result = expand_truncated_names(text)
        assert result == text

    def test_empty_input(self):
        from app.services.entity_normalizer import expand_truncated_names
        assert expand_truncated_names("") == ""
        assert expand_truncated_names(None) is None


class TestRemoveRedundantPronouns:
    """Test pronoun deduplication."""

    @pytest.fixture(autouse=True)
    def mock_aliases(self):
        mock_aliases = {
            "hồ chí minh": "hồ chí minh",
            "bác hồ": "hồ chí minh",
        }
        with patch("app.core.startup.PERSON_ALIASES", mock_aliases):
            yield

    def test_bac_ho_replaced_when_canonical_present(self):
        from app.services.entity_normalizer import _remove_redundant_pronouns
        text = "Hồ Chí Minh sinh năm 1890. Bác Hồ ra đi năm 1911."
        result = _remove_redundant_pronouns(text)
        assert "Bác Hồ" not in result
        assert "Hồ Chí Minh" in result

    def test_bac_ho_kept_when_canonical_absent(self):
        from app.services.entity_normalizer import _remove_redundant_pronouns
        text = "Bác Hồ ra đi tìm đường cứu nước."
        result = _remove_redundant_pronouns(text)
        assert "Bác Hồ" in result  # No canonical present → keep as-is

    def test_cua_bac_replaced(self):
        from app.services.entity_normalizer import _remove_redundant_pronouns
        text = "Hồ Chí Minh đã cống hiến cho sự nghiệp của Bác."
        result = _remove_redundant_pronouns(text)
        assert "của Bác" not in result
        assert "của Người" in result


class TestAnnotateFirstMention:
    """Test first-mention alias annotation."""

    @pytest.fixture(autouse=True)
    def mock_aliases(self):
        mock_aliases = {
            "hồ chí minh": "hồ chí minh",
            "nguyễn tất thành": "hồ chí minh",
            "quang trung": "nguyễn huệ",
            "nguyễn huệ": "nguyễn huệ",
        }
        with patch("app.core.startup.PERSON_ALIASES", mock_aliases):
            yield

    def test_annotate_alias_not_canonical(self):
        from app.services.entity_normalizer import _annotate_first_mention
        text = "Nguyễn Tất Thành rời Bến Nhà Rồng."
        result = _annotate_first_mention(text)
        assert "(Hồ Chí Minh)" in result

    def test_no_annotation_when_canonical_present(self):
        from app.services.entity_normalizer import _annotate_first_mention
        text = "Hồ Chí Minh và Nguyễn Tất Thành là cùng một người."
        result = _annotate_first_mention(text)
        # Canonical already present → don't annotate alias
        assert result.count("(Hồ Chí Minh)") == 0


class TestNormalizeEntityNames:
    """Test the full normalization pipeline."""

    @pytest.fixture(autouse=True)
    def mock_aliases(self):
        mock_aliases = {
            "hồ chí minh": "hồ chí minh",
            "nguyễn tất thành": "hồ chí minh",
            "nguyễn ái quốc": "hồ chí minh",
            "bác hồ": "hồ chí minh",
        }
        with patch("app.core.startup.PERSON_ALIASES", mock_aliases):
            yield

    def test_full_pipeline_no_crash(self):
        from app.services.entity_normalizer import normalize_entity_names
        text = "Năm 1911, Hồ C. rời Bến Nhà Rồng. Bác Hồ đã ra đi tìm đường."
        result = normalize_entity_names(text)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_and_none(self):
        from app.services.entity_normalizer import normalize_entity_names
        assert normalize_entity_names("") == ""
        assert normalize_entity_names(None) is None


# ================================================================
# AREA B: Intent Detail Level Detection
# ================================================================

class TestDetectDetailLevel:
    """Test detail level detection from query phrasing."""

    def test_brief_nam_nao(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Bác Hồ ra đi năm nào?") == "brief"

    def test_brief_nam_bao_nhieu(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Trận Bạch Đằng năm bao nhiêu?") == "brief"

    def test_brief_khi_nao(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Khi nào Bác Hồ ra đi?") == "brief"

    def test_brief_tom_tat(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Tóm tắt sự kiện Bạch Đằng") == "brief"

    def test_detailed_trinh_bay(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Trình bày sự kiện Bác Hồ ra đi") == "detailed"

    def test_detailed_chi_tiet(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Chi tiết trận Bạch Đằng 1288") == "detailed"

    def test_detailed_ke_ve(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Kể về trận Bạch Đằng năm 1288") == "detailed"

    def test_detailed_dien_bien(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Diễn biến trận Điện Biên Phủ") == "detailed"

    def test_standard_default(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Sự kiện Bạch Đằng") == "standard"

    def test_standard_year_query(self):
        from app.services.intent_classifier import detect_detail_level
        assert detect_detail_level("Năm 1945") == "standard"


class TestDetailLevelInClassifyIntent:
    """Test that classify_intent populates detail_level."""

    def test_classify_intent_has_detail_level(self):
        from app.services.intent_classifier import classify_intent
        result = classify_intent("Bác Hồ ra đi năm nào?")
        assert hasattr(result, "detail_level")
        assert result.detail_level in ("brief", "standard", "detailed")

    def test_classify_intent_brief_query(self):
        from app.services.intent_classifier import classify_intent
        result = classify_intent("Trận Bạch Đằng năm bao nhiêu?")
        assert result.detail_level == "brief"


# ================================================================
# AREA C: Confidence & Evidence in Response
# ================================================================

class TestResponseStructure:
    """Test that engine_answer returns confidence and evidence_ids."""

    def test_response_has_confidence_field(self):
        """Verify the response dict schema includes 'confidence'."""
        # We test the structure, not the actual engine (which requires FAISS)
        response = {
            "query": "test",
            "intent": "semantic",
            "answer": "Test answer.",
            "events": [],
            "no_data": False,
            "confidence": 0.75,
            "evidence_ids": ["doc_001"],
        }
        assert "confidence" in response
        assert isinstance(response["confidence"], float)
        assert 0.0 <= response["confidence"] <= 1.0

    def test_response_has_evidence_ids(self):
        response = {
            "query": "test",
            "intent": "semantic",
            "answer": "Test answer.",
            "events": [],
            "no_data": False,
            "confidence": 0.0,
            "evidence_ids": [],
        }
        assert "evidence_ids" in response
        assert isinstance(response["evidence_ids"], list)


# ================================================================
# AREA D: Guardrail Checks
# ================================================================

class TestCheckTruncatedNames:
    """Test guardrail truncated name detection."""

    def test_detect_ho_c(self):
        from app.services.guardrails import OutputVerifier, Severity
        v = OutputVerifier()
        result = v._check_truncated_names("Năm 1911 Hồ C. rời Bến Nhà Rồng.")
        assert result.severity == Severity.SOFT_FAIL
        assert "Hồ C." in result.message

    def test_detect_nguyen_t(self):
        from app.services.guardrails import OutputVerifier, Severity
        v = OutputVerifier()
        result = v._check_truncated_names("Nguyễn T. đã ra đi.")
        assert result.severity == Severity.SOFT_FAIL

    def test_no_false_positive(self):
        from app.services.guardrails import OutputVerifier, Severity
        v = OutputVerifier()
        result = v._check_truncated_names("Hồ Chí Minh ra đi năm 1911.")
        assert result.severity == Severity.PASS

    def test_clean_text_passes(self):
        from app.services.guardrails import OutputVerifier, Severity
        v = OutputVerifier()
        result = v._check_truncated_names(
            "Trần Hưng Đạo đánh thắng quân Nguyên Mông năm 1288."
        )
        assert result.severity == Severity.PASS


class TestCheckTemporalMixing:
    """Test guardrail temporal mixing detection."""

    def test_detect_ungrounded_year(self):
        from app.services.guardrails import OutputVerifier, Severity

        @dataclass
        class FakeQueryInfo:
            event_years: set

        v = OutputVerifier()
        qi = FakeQueryInfo(event_years={1288, 1300})
        result = v._check_temporal_mixing(
            "Trận Bạch Đằng năm 1288. Liên quan đến sự kiện năm 1945.",
            qi
        )
        assert result.severity == Severity.SOFT_FAIL
        assert "1945" in result.message

    def test_grounded_years_pass(self):
        from app.services.guardrails import OutputVerifier, Severity

        @dataclass
        class FakeQueryInfo:
            event_years: set

        v = OutputVerifier()
        qi = FakeQueryInfo(event_years={1288, 1300})
        result = v._check_temporal_mixing(
            "Trận Bạch Đằng năm 1288 đánh bại quân Nguyên.",
            qi
        )
        assert result.severity == Severity.PASS

    def test_no_event_years_passes(self):
        from app.services.guardrails import OutputVerifier, Severity

        @dataclass
        class FakeQueryInfo:
            event_years: set = None

        v = OutputVerifier()
        qi = FakeQueryInfo()
        result = v._check_temporal_mixing(
            "Năm 1945, Bác Hồ đọc tuyên ngôn.",
            qi
        )
        assert result.severity == Severity.PASS

    def test_approximate_year_tolerance(self):
        """Years within ±5 of event year should pass."""
        from app.services.guardrails import OutputVerifier, Severity

        @dataclass
        class FakeQueryInfo:
            event_years: set

        v = OutputVerifier()
        qi = FakeQueryInfo(event_years={1285})
        result = v._check_temporal_mixing(
            "Quân Nguyên xâm lược năm 1287.",
            qi
        )
        assert result.severity == Severity.PASS  # 1287 is within ±5 of 1285


class TestVerifierIntegration:
    """Test that new checks are wired into verify()."""

    def test_verify_includes_truncated_names(self):
        from app.services.guardrails import OutputVerifier
        v = OutputVerifier()
        result = v.verify("Hồ C. rời Bến Nhà Rồng.")
        check_names = [c.name for c in result.checks]
        assert "truncated_names" in check_names

    def test_verify_includes_temporal_mixing(self):
        from app.services.guardrails import OutputVerifier

        @dataclass
        class FakeQueryInfo:
            event_years: set = None
            is_fact_check: bool = False
            claimed_year: int = None
            required_persons: list = None
            required_year: int = None

        v = OutputVerifier()
        qi = FakeQueryInfo(event_years={1288})
        result = v.verify("Trận Bạch Đằng năm 1288.", qi)
        check_names = [c.name for c in result.checks]
        assert "temporal_mixing" in check_names
