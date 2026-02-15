"""
test_conflict_detector.py — Tests for Temporal Conflict Detector

Verifies that ConflictDetector correctly identifies temporal contradictions
in queries before search is executed.
"""

import sys
import os
import pytest

# Add ai-service to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-service"))

from app.core.query_schema import QueryInfo
from app.services.conflict_detector import ConflictDetector


@pytest.fixture
def detector():
    return ConflictDetector()


def _make_query_info(
    query: str,
    intent: str = "event_query",
    required_year: int | None = None,
    required_year_range: tuple | None = None,
    required_persons: list | None = None,
    required_topics: list | None = None,
) -> QueryInfo:
    """Helper to create a QueryInfo with specified constraints."""
    return QueryInfo(
        original_query=query,
        normalized_query=query.lower(),
        intent=intent,
        required_year=required_year,
        required_year_range=required_year_range,
        required_persons=required_persons or [],
        required_topics=required_topics or [],
    )


class TestConflictDetector:
    """Test temporal conflict detection for person, dynasty, and range conflicts."""

    # ========================
    # A. Person-Year Conflicts
    # ========================

    def test_person_year_conflict_tran_hung_dao_1945(self, detector):
        """Trần Hưng Đạo (1228-1300) + year 1945 → CONFLICT."""
        qi = _make_query_info(
            query="Năm 1945 Trần Hưng Đạo làm gì?",
            required_year=1945,
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert len(result.conflict_reasons) == 1
        assert "Trần Hưng Đạo" in result.conflict_reasons[0]

    def test_person_year_conflict_ho_chi_minh_1500(self, detector):
        """Hồ Chí Minh (1890-1969) + year 1500 → CONFLICT."""
        qi = _make_query_info(
            query="Hồ Chí Minh sinh năm 1500?",
            required_year=1500,
            required_persons=["Hồ Chí Minh"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert "Hồ Chí Minh" in result.conflict_reasons[0]

    def test_person_year_conflict_alias_quang_trung(self, detector):
        """Quang Trung (1753-1792) alias + year 2000 → CONFLICT."""
        qi = _make_query_info(
            query="Quang Trung năm 2000",
            required_year=2000,
            required_persons=["quang trung"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True

    # ========================
    # B. Dynasty-Year Conflicts
    # ========================

    def test_dynasty_year_conflict_nguyen_2000(self, detector):
        """Triều Nguyễn (1802-1945) + year 2000 → CONFLICT."""
        qi = _make_query_info(
            query="Triều Nguyễn năm 2000 có gì?",
            required_year=2000,
            required_persons=["triều nguyễn"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert "triều nguyễn" in result.conflict_reasons[0]

    def test_dynasty_year_conflict_nha_ly_1885(self, detector):
        """Nhà Lý (1009-1225) + year 1885 → CONFLICT."""
        qi = _make_query_info(
            query="Nhà Lý đánh Pháp năm 1885?",
            required_year=1885,
            required_persons=["nhà lý"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True

    def test_dynasty_short_name_tran_2000(self, detector):
        """Short dynasty name 'trần' + year 2000 → CONFLICT via short name lookup."""
        qi = _make_query_info(
            query="Nhà Trần năm 2000",
            required_year=2000,
            required_persons=["trần"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True

    # ========================
    # C. Range Intersection Conflicts
    # ========================

    def test_range_no_intersection(self, detector):
        """Person (1228-1300) + year_range (1800-1850) → no intersection → CONFLICT."""
        qi = _make_query_info(
            query="Trần Hưng Đạo từ 1800 đến 1850",
            required_year_range=(1800, 1850),
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True

    def test_range_has_intersection(self, detector):
        """Person (1228-1300) + year_range (1250-1350) → intersection exists → NO conflict."""
        qi = _make_query_info(
            query="Trần Hưng Đạo từ 1250 đến 1350",
            required_year_range=(1250, 1350),
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # ========================
    # D. Valid Queries (No Conflict)
    # ========================

    def test_valid_person_year_intersection(self, detector):
        """Trần Hưng Đạo (1228-1300) + year 1288 → VALID, no conflict."""
        qi = _make_query_info(
            query="Năm 1288 Trần Hưng Đạo làm gì?",
            required_year=1288,
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False
        assert len(result.conflict_reasons) == 0

    def test_valid_dynasty_year(self, detector):
        """Nhà Nguyễn (1802-1945) + year 1858 → VALID."""
        qi = _make_query_info(
            query="Nhà Nguyễn năm 1858",
            required_year=1858,
            required_persons=["nhà nguyễn"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_valid_ho_chi_minh_1945(self, detector):
        """Hồ Chí Minh (1890-1969) + year 1945 → VALID."""
        qi = _make_query_info(
            query="Năm 1945 Hồ Chí Minh làm gì?",
            required_year=1945,
            required_persons=["Hồ Chí Minh"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # ========================
    # E. Edge Cases (Safety)
    # ========================

    def test_unknown_entity_no_crash(self, detector):
        """Unknown entity + year → NO conflict (safe default)."""
        qi = _make_query_info(
            query="Năm 1945 Unknown Person làm gì?",
            required_year=1945,
            required_persons=["Unknown Person"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False  # No metadata → no conflict

    def test_no_year_constraint(self, detector):
        """Entity without year → NO conflict possible."""
        qi = _make_query_info(
            query="Trần Hưng Đạo làm gì?",
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_no_entities_with_year(self, detector):
        """Year without entities → NO conflict."""
        qi = _make_query_info(
            query="Năm 1945 có gì?",
            required_year=1945,
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_empty_query_info(self, detector):
        """Empty QueryInfo → NO conflict."""
        qi = _make_query_info(query="lịch sử việt nam")
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_multiple_entities_one_conflict(self, detector):
        """Multiple entities, one conflicting → has_conflict=True."""
        qi = _make_query_info(
            query="Năm 1945 Trần Hưng Đạo và Hồ Chí Minh",
            required_year=1945,
            required_persons=["Trần Hưng Đạo", "Hồ Chí Minh"],
        )
        result = detector.detect(qi)
        # THĐ conflicts (1228-1300 vs 1945), HCM doesn't (1890-1969 includes 1945)
        assert result.has_conflict is True
        assert len(result.conflict_reasons) == 1  # Only THĐ conflict
        assert "Trần Hưng Đạo" in result.conflict_reasons[0]

    def test_vo_nguyen_giap_1954(self, detector):
        """Võ Nguyên Giáp (1911-2013) + year 1954 → VALID."""
        qi = _make_query_info(
            query="Năm 1954 Võ Nguyên Giáp làm gì?",
            required_year=1954,
            required_persons=["võ nguyên giáp"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_custom_metadata(self):
        """Custom entity metadata works correctly."""
        custom_meta = {
            "test entity": {
                "type": "person",
                "lifespan": (100, 200),
            }
        }
        detector = ConflictDetector(entity_metadata=custom_meta)
        qi = _make_query_info(
            query="Test entity năm 500",
            required_year=500,
            required_persons=["test entity"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True

    # ========================
    # F. Edge Cases — User-Requested Scenarios
    # ========================

    def test_boundary_year_start(self, detector):
        """🧨 2a: Start boundary — THĐ (1228-1300) + year 1228 → VALID."""
        qi = _make_query_info(
            query="Trần Hưng Đạo năm 1228",
            required_year=1228,
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_boundary_year_end(self, detector):
        """🧨 2b: End boundary — THĐ (1228-1300) + year 1300 → VALID (inclusive)."""
        qi = _make_query_info(
            query="Trần Hưng Đạo năm 1300?",
            required_year=1300,
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_boundary_year_just_outside(self, detector):
        """🧨 2c: Just outside end boundary — THĐ (1228-1300) + year 1301 → CONFLICT."""
        qi = _make_query_info(
            query="Trần Hưng Đạo năm 1301?",
            required_year=1301,
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True

    def test_partial_range_overlap(self, detector):
        """🧨 3: Partial overlap — THĐ (1228-1300) + range (1295-1310) → overlap 1295–1300 → VALID."""
        qi = _make_query_info(
            query="Trần Hưng Đạo giai đoạn 1295-1310?",
            required_year_range=(1295, 1310),
            required_persons=["Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False  # Partial overlap is valid

    def test_self_conflict_year_outside_range(self, detector):
        """🧨 5a: Self-conflict — year 1945 not in range (1200-1300) → CONFLICT."""
        qi = _make_query_info(
            query="Năm 1945 giai đoạn 1200-1300?",
            required_year=1945,
            required_year_range=(1200, 1300),
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert "self-conflict" in result.conflict_reasons[0].lower()

    def test_self_conflict_year_inside_range(self, detector):
        """🧨 5b: No self-conflict — year 1250 in range (1200-1300) → VALID."""
        qi = _make_query_info(
            query="Năm 1250 giai đoạn 1200-1300?",
            required_year=1250,
            required_year_range=(1200, 1300),
        )
        result = detector.detect(qi)
        assert result.has_conflict is False


class TestAnswerValidatorTemporal:
    """Test AnswerValidator temporal logic — year_range with event.year_range."""

    @pytest.fixture
    def validator(self):
        from app.services.answer_validator import AnswerValidator
        return AnswerValidator()

    def test_year_range_event_has_year_range_overlap(self, validator):
        """🧨 1: required_year_range (1250-1350) + event.year_range (1225-1400) → overlap → PASS."""
        qi = _make_query_info(
            query="Nhà Trần 1250-1350",
            required_year_range=(1250, 1350),
        )
        event = {"event": "Nhà Trần", "year_range": [1225, 1400]}
        assert validator.validate_candidate(qi, event) is True

    def test_year_range_event_has_year_range_no_overlap(self, validator):
        """🧨 2: required_year_range (1800-1850) + event.year_range (1225-1400) → no overlap → FAIL."""
        qi = _make_query_info(
            query="Nhà Trần 1800-1850",
            required_year_range=(1800, 1850),
        )
        event = {"event": "Nhà Trần", "year_range": [1225, 1400]}
        assert validator.validate_candidate(qi, event) is False

    def test_year_range_event_has_year_only(self, validator):
        """required_year_range (1250-1350) + event.year=1288 → PASS."""
        qi = _make_query_info(
            query="Sự kiện 1250-1350",
            required_year_range=(1250, 1350),
        )
        event = {"event": "Trận Bạch Đằng", "year": 1288}
        assert validator.validate_candidate(qi, event) is True

    def test_year_range_event_has_year_outside(self, validator):
        """required_year_range (1250-1350) + event.year=1945 → FAIL."""
        qi = _make_query_info(
            query="Sự kiện 1250-1350",
            required_year_range=(1250, 1350),
        )
        event = {"event": "Some event", "year": 1945}
        assert validator.validate_candidate(qi, event) is False

    def test_year_range_event_no_temporal_data(self, validator):
        """required_year_range + event without year or year_range → FAIL."""
        qi = _make_query_info(
            query="Sự kiện 1250-1350",
            required_year_range=(1250, 1350),
        )
        event = {"event": "Some event"}
        assert validator.validate_candidate(qi, event) is False

    def test_entity_scan_intent_still_checks_temporal(self, validator):
        """🧨 3: person_query + required_year=1945 + event.year=1288 → FAIL (temporal enforced)."""
        qi = _make_query_info(
            query="Trần Hưng Đạo năm 1945",
            intent="person_query",
            required_year=1945,
            required_persons=["Trần Hưng Đạo"],
        )
        event = {"event": "Trận Bạch Đằng", "year": 1288, "persons": ["Trần Hưng Đạo"]}
        # Entity-scan bypasses entity check, but NOT temporal check
        assert validator.validate_candidate(qi, event) is False

    def test_entity_scan_intent_skips_entity_match(self, validator):
        """person_query intent → entity check skipped, temporal + type enforced."""
        qi = _make_query_info(
            query="Trần Hưng Đạo năm 1288",
            intent="person_query",
            required_year=1288,
            required_persons=["Trần Hưng Đạo"],
        )
        # Event doesn't mention THĐ but matches year — should PASS because entity skipped
        event = {"event": "Trận Bạch Đằng lần 3", "year": 1288}
        assert validator.validate_candidate(qi, event) is True


class TestTopicSeparation:
    """Test that topics (soft constraints) are NOT used for hard filtering."""

    @pytest.fixture
    def detector(self):
        return ConflictDetector()

    @pytest.fixture
    def validator(self):
        from app.services.answer_validator import AnswerValidator
        return AnswerValidator()

    def test_topic_not_used_in_conflict_detection(self, detector):
        """Topic-only query should NOT trigger conflict detection."""
        qi = _make_query_info(
            query="Giáo dục thời Lý năm 2000",
            required_year=2000,
            required_topics=["giáo dục"],   # Soft — should be ignored
            # No required_persons → no entity to conflict with
        )
        result = detector.detect(qi)
        assert result.has_conflict is False  # No persons → no conflict

    def test_topic_not_rejected_by_hard_filter(self, validator):
        """Topic-only in query should not reject events missing topic text."""
        qi = _make_query_info(
            query="Giáo dục thời Lý",
            required_topics=["giáo dục"],
            # No required_persons
        )
        # Event doesn't mention "giáo dục" at all
        event = {"event": "Nhà Lý dời đô ra Thăng Long", "year": 1010}
        # Should PASS because topics are soft, not hard
        assert validator.validate_candidate(qi, event) is True

    def test_person_still_enforced_even_with_topics(self, validator):
        """Person is hard constraint — must match even when topics are present."""
        qi = _make_query_info(
            query="Trần Hưng Đạo chiến tranh",
            intent="year_specific",  # Non-entity-scan intent → person check enforced
            required_persons=["trần hưng đạo"],
            required_topics=["chiến tranh"],
        )
        # Event doesn't mention THĐ
        event = {"event": "Chiến tranh chống Pháp", "year": 1945}
        assert validator.validate_candidate(qi, event) is False  # Person not found


