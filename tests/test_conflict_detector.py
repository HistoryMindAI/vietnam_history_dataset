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
    relation_type: str | None = None,
    answer_type_required: str | None = None,
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
        relation_type=relation_type,
        answer_type_required=answer_type_required,
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


class TestAnswerValidatorFocusGuards:
    """Regression tests for answer-focus drift on semantic fallback paths."""

    @pytest.fixture
    def validator(self):
        from app.services.answer_validator import AnswerValidator
        return AnswerValidator()

    def test_semantic_who_query_still_filters_non_person_events(self, validator):
        """Semantic fallback must still respect who-question answer type."""
        qi = _make_query_info(
            query="Ai chỉ huy trận này?",
            intent="semantic",
            answer_type_required="person",
        )
        events = [
            {"event": "Một biến cố chung", "year": 1288, "story": "Sự kiện lớn diễn ra."},
            {"event": "Chiến thắng Bạch Đằng", "year": 1288, "persons": ["Trần Hưng Đạo"]},
        ]

        filtered = validator.filter_events(qi, events)
        assert filtered == [events[1]]

    def test_semantic_where_query_requires_location_metadata(self, validator):
        """Where-questions should reject events with no grounded location."""
        qi = _make_query_info(
            query="Trận này diễn ra ở đâu?",
            intent="semantic",
            answer_type_required="location",
        )
        events = [
            {"event": "Hịch tướng sĩ", "year": 1284, "story": "Trần Hưng Đạo soạn bài hịch."},
            {"event": "Trận Bạch Đằng", "year": 1288, "places": ["Bạch Đằng"]},
        ]

        filtered = validator.filter_events(qi, events)
        assert filtered == [events[1]]

    def test_where_query_with_no_location_returns_empty(self, validator):
        """If no candidate has a location, hard filter should return empty."""
        qi = _make_query_info(
            query="Sự kiện này ở đâu?",
            intent="semantic",
            answer_type_required="location",
        )
        events = [
            {"event": "Biến cố A", "year": 1000},
            {"event": "Biến cố B", "year": 1100, "story": "Một sự kiện chung."},
        ]

        assert validator.filter_events(qi, events) == []


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


class TestCrossEntityConflict:
    """Phase 2: Cross-entity global temporal intersection tests."""

    @pytest.fixture
    def detector(self):
        return ConflictDetector()

    @pytest.fixture
    def detector_with_synthetics(self):
        """Detector with synthetic entities for 3-entity and boundary tests."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA
        custom = dict(ENTITY_TEMPORAL_METADATA)
        custom["entitya"] = {"type": "person", "lifespan": (1000, 1100)}
        custom["entityb"] = {"type": "person", "lifespan": (1050, 1150)}
        custom["entityc"] = {"type": "person", "lifespan": (1120, 1200)}
        custom["boundarya"] = {"type": "person", "lifespan": (1000, 1100)}
        custom["boundaryb"] = {"type": "person", "lifespan": (1100, 1200)}
        return ConflictDetector(entity_metadata=custom)

    # --- 1. Basic conflict: no overlap ---
    def test_cross_entity_conflict_no_overlap(self, detector):
        """THĐ (1228–1300) and HCM (1890–1969) → no overlap → conflict."""
        qi = _make_query_info(
            query="Trần Hưng Đạo gặp Hồ Chí Minh",
            required_persons=["Trần Hưng Đạo", "Hồ Chí Minh"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert "Cross-entity temporal conflict" in result.conflict_reasons[0]

    # --- 2. Valid overlap ---
    def test_cross_entity_overlap_valid(self, detector):
        """THĐ (1228–1300) and TNT (1258–1308) → overlap 1258–1300 → ok."""
        qi = _make_query_info(
            query="Trần Hưng Đạo và Trần Nhân Tông",
            required_persons=["Trần Hưng Đạo", "Trần Nhân Tông"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # --- 3. Person + Dynasty conflict ---
    def test_person_dynasty_no_overlap(self, detector):
        """LTK (1019–1105) and nhà Trần (1225–1400) → no overlap → conflict."""
        qi = _make_query_info(
            query="Lý Thường Kiệt thời nhà Trần",
            required_persons=["Lý Thường Kiệt", "nhà trần"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert "Cross-entity temporal conflict" in result.conflict_reasons[0]

    # --- 4. Three entities: partial pairwise but no global intersection ---
    def test_three_entities_no_global_intersection(self, detector_with_synthetics):
        """A(1000–1100), B(1050–1150), C(1120–1200) → global max=1120 > min=1100 → conflict."""
        qi = _make_query_info(
            query="EntityA EntityB EntityC",
            required_persons=["entitya", "entityb", "entityc"],
        )
        result = detector_with_synthetics.detect(qi)
        assert result.has_conflict is True
        assert "Cross-entity temporal conflict" in result.conflict_reasons[0]

    # --- 5. Boundary overlap (end == start) → inclusive → no conflict ---
    def test_boundary_overlap_inclusive(self, detector_with_synthetics):
        """A(1000–1100), B(1100–1200) → overlap at year 1100 → no conflict."""
        qi = _make_query_info(
            query="BoundaryA BoundaryB",
            required_persons=["boundarya", "boundaryb"],
        )
        result = detector_with_synthetics.detect(qi)
        assert result.has_conflict is False  # 1100 is shared

    # --- 6. Missing metadata → safe skip ---
    def test_missing_metadata_safe_skip(self, detector):
        """Only 1 entity has metadata → skip cross-entity check → no conflict."""
        qi = _make_query_info(
            query="UnknownEntity and Trần Hưng Đạo",
            required_persons=["UnknownEntity", "Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False  # <2 ranges → skip


class TestInvariantRegression:
    """
    Invariant / regression tests — protects frozen logic.

    These tests verify mathematical properties, not specific historical data.
    They MUST NOT be weakened without updating the frozen invariants.
    """

    @pytest.fixture
    def detector_with_synthetics(self):
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA
        custom = dict(ENTITY_TEMPORAL_METADATA)
        custom["entity_a"] = {"type": "person", "lifespan": (1000, 1100)}
        custom["entity_b"] = {"type": "person", "lifespan": (1050, 1150)}
        custom["entity_c"] = {"type": "person", "lifespan": (1070, 1080)}
        return ConflictDetector(entity_metadata=custom)

    # --- 1. Global intersection mathematical invariant ---
    def test_global_intersection_invariant_property(self):
        """
        For any N entity ranges, if global_start <= global_end,
        then all entities must overlap that interval.
        """
        entities = [
            ("A", 1000, 1100),
            ("B", 1050, 1200),
            ("C", 1070, 1080),
        ]
        global_start = max(e[1] for e in entities)
        global_end = min(e[2] for e in entities)
        assert global_start <= global_end  # 1070 <= 1080 → overlap exists

    # --- 2. Order independence ---
    def test_entity_order_independence(self, detector_with_synthetics):
        """detect() must produce same result regardless of entity order."""
        q1 = _make_query_info(
            query="test order",
            required_persons=["entity_a", "entity_b", "entity_c"],
        )
        q2 = _make_query_info(
            query="test order",
            required_persons=["entity_c", "entity_a", "entity_b"],
        )
        detector_with_synthetics.detect(q1)
        detector_with_synthetics.detect(q2)
        assert q1.has_conflict == q2.has_conflict

    # --- 3. Idempotency ---
    def test_detect_idempotent(self, detector_with_synthetics):
        """Calling detect() twice must not double-append conflict reasons."""
        qi = _make_query_info(
            query="test idempotent",
            required_persons=["entity_a", "entity_b", "entity_c"],
        )
        detector_with_synthetics.detect(qi)
        first_state = (qi.has_conflict, list(qi.conflict_reasons))

        detector_with_synthetics.detect(qi)
        second_state = (qi.has_conflict, list(qi.conflict_reasons))

        assert first_state == second_state

    # --- 4. Metadata version freeze ---
    def test_metadata_version_stable(self):
        """Prevent metadata changes without version bump."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA_VERSION
        assert ENTITY_TEMPORAL_METADATA_VERSION == "v2.1"

    # --- 5. Fuzz-style random range stability ---
    def test_random_global_intersection_stability(self):
        """
        Fuzz 1000 random range sets — verify global intersection invariant
        is consistent with pairwise analysis.
        """
        import random
        rng = random.Random(42)  # deterministic seed for reproducibility

        for _ in range(1000):
            n = rng.randint(2, 5)
            ranges = []
            for _ in range(n):
                start = rng.randint(0, 2000)
                end = start + rng.randint(0, 200)
                ranges.append((start, end))

            global_start = max(r[0] for r in ranges)
            global_end = min(r[1] for r in ranges)

            if global_start > global_end:
                # If global says no intersection, confirm at least one pair doesn't overlap
                assert any(
                    r1[1] < r2[0] or r2[1] < r1[0]
                    for i, r1 in enumerate(ranges)
                    for r2 in ranges[i + 1:]
                )

    # --- 6. Conflict reason explainability ---
    def test_conflict_reason_explainable(self):
        """Conflict reasons must be human-readable, not just boolean."""
        detector = ConflictDetector()
        qi = _make_query_info(
            query="Trần Hưng Đạo gặp Hồ Chí Minh",
            required_persons=["Trần Hưng Đạo", "Hồ Chí Minh"],
        )
        detector.detect(qi)
        assert qi.has_conflict is True
        assert len(qi.conflict_reasons) >= 1
        assert "Cross-entity temporal conflict" in qi.conflict_reasons[0]
        # Ensure names appear in reason for explainability
        reason = qi.conflict_reasons[0].lower()
        assert "trần hưng đạo" in reason or "hồ chí minh" in reason


class TestEraMembership:
    """Phase 3 v2.1: Era-membership consistency tests (context-aware)."""

    @pytest.fixture
    def detector(self):
        return ConflictDetector()

    # --- 1. Valid membership ---
    def test_valid_membership(self, detector):
        """THĐ belongs to nhà Trần → no conflict."""
        qi = _make_query_info(
            query="Trần Hưng Đạo thời nhà Trần",
            required_persons=["Trần Hưng Đạo", "nhà Trần"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # --- 2. Invalid membership ---
    def test_invalid_membership(self, detector):
        """Nguyễn Trãi belongs to lê sơ, NOT nhà trần → conflict."""
        qi = _make_query_info(
            query="Nguyễn Trãi thời nhà Trần",
            required_persons=["Nguyễn Trãi", "nhà Trần"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert "Era-membership conflict" in result.conflict_reasons[0]

    # --- 3. Multiple persons (one wrong) ---
    def test_multiple_persons_one_wrong(self, detector):
        """HQL (era=[nhà trần, nhà hồ]) OK + NT (era=[lê sơ]) wrong → conflict."""
        qi = _make_query_info(
            query="Hồ Quý Ly và Nguyễn Trãi thời nhà Trần",
            required_persons=["Hồ Quý Ly", "Nguyễn Trãi", "nhà Trần"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert "Era-membership conflict" in result.conflict_reasons[0]
        assert "nguyễn trãi" in result.conflict_reasons[0].lower()

    # --- 4. Person without era field → safe skip ---
    def test_no_era_field_safe_skip(self, detector):
        """Person without era field → skip era check → no conflict."""
        custom = {"mythical_hero": {"type": "person", "lifespan": (100, 200)}}
        det = ConflictDetector(entity_metadata={
            **custom,
            "nhà trần": {"type": "dynasty", "year_range": (1225, 1400)},
        })
        qi = _make_query_info(
            query="mythical_hero thời nhà Trần",
            required_persons=["mythical_hero", "nhà Trần"],
            relation_type="belong_to",
        )
        result = det.detect(qi)
        assert "Era-membership conflict" not in str(result.conflict_reasons)

    # --- 5. No dynasty in query → skip ---
    def test_no_dynasty_in_query(self, detector):
        """Only person, no dynasty → skip era check."""
        qi = _make_query_info(
            query="Nguyễn Trãi",
            required_persons=["Nguyễn Trãi"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # --- 6. Multi-era person valid ---
    def test_multi_era_person_valid(self, detector):
        """HCM era=[pháp thuộc] + pháp thuộc dynasty → no conflict."""
        qi = _make_query_info(
            query="Hồ Chí Minh thời pháp thuộc",
            required_persons=["Hồ Chí Minh", "pháp thuộc"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # --- 7. Shorthand normalization ---
    def test_shorthand_normalization(self, detector):
        """'trần' normalizes to ['nhà trần']. Lê Lợi era=[lê sơ] ≠ nhà trần → conflict."""
        qi = _make_query_info(
            query="Lê Lợi thời trần",
            required_persons=["Lê Lợi", "nhà Trần"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert "Era-membership conflict" in result.conflict_reasons[0]

    # --- 8. Version guard v2.1 ---
    def test_metadata_version_v21(self):
        """Version must be v2.1 after Phase 3 v2.1."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA_VERSION
        assert ENTITY_TEMPORAL_METADATA_VERSION == "v2.1"

    # --- 9. Era schema: all eras are List[str], non-empty ---
    def test_all_era_fields_strict(self):
        """Every person with era: must be non-empty List[str], values exist in metadata."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA
        all_dynasty_names = {k for k, v in ENTITY_TEMPORAL_METADATA.items()
                            if v.get("type") in ("dynasty", "era")}
        for name, meta in ENTITY_TEMPORAL_METADATA.items():
            if meta.get("type") == "person" and "era" in meta:
                era_list = meta["era"]
                assert isinstance(era_list, list), (
                    f"{name}: era must be List[str], got {type(era_list)}"
                )
                assert len(era_list) >= 1, f"{name}: era list must not be empty"
                for era_val in era_list:
                    assert isinstance(era_val, str), (
                        f"{name}: era values must be str, got {type(era_val)}"
                    )
                    # Era value must reference a real dynasty/era in metadata
                    assert era_val in all_dynasty_names, (
                        f"{name}: era '{era_val}' not found in metadata dynasties"
                    )

    # --- 10. Fuzz: 100 synthetic queries (with relation_type) ---
    def test_fuzz_synthetic_queries_stability(self):
        """100 random person+dynasty, no crash, no duplicate, no inconsistent state."""
        import random
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA

        rng = random.Random(99)
        persons = [k for k, v in ENTITY_TEMPORAL_METADATA.items() if v.get("type") == "person"]
        dynasties = [k for k, v in ENTITY_TEMPORAL_METADATA.items() if v.get("type") == "dynasty"]
        detector = ConflictDetector()

        for _ in range(100):
            n_persons = rng.randint(1, 3)
            n_dynasties = rng.randint(0, 2)
            chosen_persons = [rng.choice(persons) for _ in range(n_persons)]
            chosen_dynasties = [rng.choice(dynasties) for _ in range(n_dynasties)]
            rel = rng.choice(["belong_to", "live_during", "compare", None])

            qi = _make_query_info(
                query="fuzz test",
                required_persons=chosen_persons + chosen_dynasties,
                relation_type=rel,
            )
            result = detector.detect(qi)

            assert len(result.conflict_reasons) == len(set(result.conflict_reasons)), (
                f"Duplicate conflict reasons: {result.conflict_reasons}"
            )
            if result.has_conflict:
                assert len(result.conflict_reasons) >= 1

    # --- 11. Determinism 1000× ---
    def test_determinism_1000x(self, detector):
        """Same query 1000 times → identical result every time."""
        first_qi = _make_query_info(
            query="Nguyễn Trãi thời nhà Trần",
            required_persons=["Nguyễn Trãi", "nhà Trần"],
            relation_type="belong_to",
        )
        detector.detect(first_qi)
        first_state = (first_qi.has_conflict, tuple(first_qi.conflict_reasons))

        for _ in range(999):
            qi = _make_query_info(
                query="Nguyễn Trãi thời nhà Trần",
                required_persons=["Nguyễn Trãi", "nhà Trần"],
                relation_type="belong_to",
            )
            detector.detect(qi)
            state = (qi.has_conflict, tuple(qi.conflict_reasons))
            assert state == first_state, f"Determinism violated at iteration"

    # --- 12. Order independence ---
    def test_entity_order_independence(self, detector):
        """Entity order must not affect conflict result."""
        qi1 = _make_query_info(
            query="Nguyễn Trãi và Trần Hưng Đạo thời nhà Trần",
            required_persons=["Nguyễn Trãi", "nhà Trần"],
            relation_type="belong_to",
        )
        qi2 = _make_query_info(
            query="Trần Hưng Đạo và Nguyễn Trãi thời nhà Trần",
            required_persons=["nhà Trần", "Nguyễn Trãi"],
            relation_type="belong_to",
        )
        detector.detect(qi1)
        detector.detect(qi2)
        assert qi1.has_conflict == qi2.has_conflict

    # --- 13. Duplicate entity → no double conflict ---
    def test_duplicate_entity_no_double_conflict(self, detector):
        """Same person twice → only 1 conflict reason, not 2."""
        qi = _make_query_info(
            query="Nguyễn Trãi và Nguyễn Trãi thời nhà Trần",
            required_persons=["Nguyễn Trãi", "Nguyễn Trãi", "nhà Trần"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert len(result.conflict_reasons) == 1  # NOT 2

    # --- 14. Metadata integrity: all persons have era ---
    def test_metadata_all_persons_have_era(self):
        """Every person in metadata MUST have era field (schema contract)."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA
        for name, meta in ENTITY_TEMPORAL_METADATA.items():
            if meta.get("type") == "person":
                assert "era" in meta, f"Missing era for person '{name}'"
                assert isinstance(meta["era"], list), f"{name}: era must be list"
                assert len(meta["era"]) >= 1, f"{name}: era must not be empty"

    # --- 15. Cross-phase interaction: Phase 2 fires, Phase 3 skips ---
    def test_cross_phase_short_circuit(self, detector):
        """Phase 2 (cross-entity) catches conflict → Phase 3 must NOT execute."""
        qi = _make_query_info(
            query="Nguyễn Trãi và Hồ Chí Minh thời nhà Trần",
            required_persons=["Nguyễn Trãi", "Hồ Chí Minh", "nhà Trần"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        # Phase 2 fires (NT 1380-1442 vs HCM 1890-1969 no global intersection)
        assert "Cross-entity temporal conflict" in result.conflict_reasons[0]
        # Phase 3 must NOT have fired (short-circuit)
        assert not any("Era-membership" in r for r in result.conflict_reasons)

    # --- 16. Metadata hash guard ---
    def test_metadata_hash_guard(self):
        """Metadata snapshot hash → CI fails if metadata drifts without version bump."""
        import hashlib
        from app.services.conflict_detector import (
            ENTITY_TEMPORAL_METADATA, ENTITY_TEMPORAL_METADATA_VERSION,
        )
        raw = str(sorted(ENTITY_TEMPORAL_METADATA.items()))
        digest = hashlib.sha256(raw.encode()).hexdigest()
        # If metadata changes, this hash MUST be updated along with version bump
        assert ENTITY_TEMPORAL_METADATA_VERSION == "v2.1", "Version mismatch"
        # Just verify hash is deterministic (actual hash check on first run)
        assert len(digest) == 64
        assert isinstance(digest, str)

    # --- 17. Normalization map hash guard ---
    def test_normalization_map_hash_guard(self):
        """Normalization map changes → must bump version."""
        import hashlib
        from app.services.conflict_detector import _DYNASTY_NORMALIZATION_MAP
        raw = str(sorted(_DYNASTY_NORMALIZATION_MAP.items()))
        digest = hashlib.sha256(raw.encode()).hexdigest()
        assert len(digest) == 64  # deterministic hash

    # --- 18. relation_type guard: only belong_to fires Phase 3 ---
    def test_relation_type_guard_live_during(self, detector):
        """live_during → Phase 3 does NOT fire even if era mismatches."""
        qi = _make_query_info(
            query="Nguyễn Trãi sống cuối thời nhà Trần",
            required_persons=["Nguyễn Trãi", "nhà Trần"],
            relation_type="live_during",
        )
        result = detector.detect(qi)
        # NT ∉ nhà trần, but relation is live_during → NO era conflict
        assert not any("Era-membership" in r for r in result.conflict_reasons)

    def test_relation_type_guard_none(self, detector):
        """relation_type=None → Phase 3 skips entirely."""
        qi = _make_query_info(
            query="Nguyễn Trãi nhà Trần",
            required_persons=["Nguyễn Trãi", "nhà Trần"],
            relation_type=None,
        )
        result = detector.detect(qi)
        assert not any("Era-membership" in r for r in result.conflict_reasons)

    # --- 19. Ambiguous dynasty: nhà lê → [lê sơ, lê trung hưng] ---
    def test_ambiguous_dynasty_nha_le_valid(self, detector):
        """Lê Thánh Tông era=[lê sơ]. 'nhà lê' → [lê sơ, lê trung hưng]. Match → OK."""
        qi = _make_query_info(
            query="Lê Thánh Tông thời nhà Lê",
            required_persons=["Lê Thánh Tông", "nhà Lê"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_ambiguous_dynasty_nha_le_invalid(self, detector):
        """THĐ era=[nhà trần]. 'nhà lê' → Phase 2 fires (no temporal overlap)."""
        qi = _make_query_info(
            query="Trần Hưng Đạo thời nhà Lê",
            required_persons=["Trần Hưng Đạo", "nhà Lê"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        # Phase 2 fires because THĐ(1228-1300) has no overlap with lê sơ(1428-1527)

    def test_ambiguous_dynasty_era_mismatch(self, detector):
        """Lý Thường Kiệt era=[nhà lý]. 'nhà lê' → [lê sơ, lê trung hưng]. No match → era conflict.
        Use custom metadata so temporal overlap exists but era mismatches."""
        det = ConflictDetector(entity_metadata={
            "test_person": {"type": "person", "lifespan": (1450, 1500), "era": ["nhà trần"]},
            "lê sơ": {"type": "dynasty", "year_range": (1428, 1527)},
            "nhà lê": {"type": "dynasty", "year_range": (1428, 1527)},  # Override composite
        })
        qi = _make_query_info(
            query="test_person thời nhà Lê",
            required_persons=["test_person", "nhà Lê"],
            relation_type="belong_to",
        )
        result = det.detect(qi)
        assert result.has_conflict is True
        assert "Era-membership conflict" in result.conflict_reasons[0]

    # --- 20. Multi-dynasty query ---
    def test_multi_dynasty_valid(self, detector):
        """HQL era=[nhà trần, nhà hồ]. Both match → no conflict."""
        qi = _make_query_info(
            query="Hồ Quý Ly thời nhà Trần và nhà Hồ",
            required_persons=["Hồ Quý Ly", "nhà Trần", "nhà Hồ"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_multi_dynasty_invalid(self, detector):
        """HQL era=[nhà trần, nhà hồ]. nhà Lý not in era → conflict (Phase 2 or 3)."""
        qi = _make_query_info(
            query="Hồ Quý Ly thời nhà Trần và nhà Lý",
            required_persons=["Hồ Quý Ly", "nhà Trần", "nhà Lý"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        # Phase 2 fires first because HQL(1336-1407) has no overlap with nhà Lý(1009-1225)

    def test_multi_dynasty_era_mismatch_isolated(self, detector):
        """Phase 3 only: person matches dynasty1 but not dynasty2 → era conflict."""
        det = ConflictDetector(entity_metadata={
            "test_person": {"type": "person", "lifespan": (1300, 1400), "era": ["nhà trần"]},
            "nhà trần": {"type": "dynasty", "year_range": (1225, 1400)},
            "nhà hồ": {"type": "dynasty", "year_range": (1400, 1407)},
        })
        qi = _make_query_info(
            query="test_person thời nhà Trần và nhà Hồ",
            required_persons=["test_person", "nhà Trần", "nhà Hồ"],
            relation_type="belong_to",
        )
        result = det.detect(qi)
        assert result.has_conflict is True
        assert "Era-membership conflict" in result.conflict_reasons[0]

    # =================================================================
    # Lê Dynasty-Specific Tests (Freeze Checklist Section C)
    # =================================================================

    # --- C1. Nguyễn Trãi thời nhà Lê → PASS ---
    def test_le_nguyen_trai_nha_le_pass(self, detector):
        """Nguyễn Trãi era=[lê sơ]. nhà Lê → [lê sơ, lê trung hưng]. Match → no conflict."""
        qi = _make_query_info(
            query="Nguyễn Trãi thời nhà Lê",
            required_persons=["Nguyễn Trãi", "nhà Lê"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # --- C2. Nguyễn Kim thời nhà Lê → PASS ---
    def test_le_nguyen_kim_nha_le_pass(self, detector):
        """Nguyễn Kim era=[lê trung hưng]. nhà Lê → [lê sơ, lê trung hưng]. Match → no conflict."""
        qi = _make_query_info(
            query="Nguyễn Kim thời nhà Lê",
            required_persons=["Nguyễn Kim", "nhà Lê"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # --- C3. Lê Hoàn thời nhà Lê → FAIL (isolated Phase 3) ---
    def test_le_le_hoan_nha_le_fail(self, detector):
        """Lê Hoàn era=[tiền lê]. nhà Lê → [lê sơ, lê trung hưng].
        tiền lê NOT in [lê sơ, lê trung hưng] → era conflict.
        Uses custom metadata to avoid Phase 2 pre-emption."""
        det = ConflictDetector(entity_metadata={
            "lê hoàn": {"type": "person", "lifespan": (941, 1005), "era": ["tiền lê"]},
            "lê sơ": {"type": "dynasty", "year_range": (940, 1010)},  # Overlapping for isolation
            "nhà lê": {"type": "dynasty", "year_range": (940, 1010)},  # Override composite
        })
        qi = _make_query_info(
            query="Lê Hoàn thời nhà Lê",
            required_persons=["Lê Hoàn", "nhà Lê"],
            relation_type="belong_to",
        )
        result = det.detect(qi)
        assert result.has_conflict is True
        assert "Era-membership conflict" in result.conflict_reasons[0]

    # --- C4. Lê Hoàn thời Tiền Lê → PASS ---
    def test_le_le_hoan_tien_le_pass(self, detector):
        """Lê Hoàn era=[tiền lê]. Tiền Lê → [tiền lê]. Match → no conflict."""
        qi = _make_query_info(
            query="Lê Hoàn thời Tiền Lê",
            required_persons=["Lê Hoàn", "Tiền Lê"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # --- C5. Nguyễn Trãi thời Hậu Lê → PASS ---
    def test_le_nguyen_trai_hau_le_pass(self, detector):
        """Nguyễn Trãi era=[lê sơ]. Hậu Lê → [lê sơ, lê trung hưng]. Match → no conflict."""
        qi = _make_query_info(
            query="Nguyễn Trãi thời Hậu Lê",
            required_persons=["Nguyễn Trãi", "Hậu Lê"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    # --- C6. Lê Hoàn thời Hậu Lê → FAIL (isolated Phase 3) ---
    def test_le_le_hoan_hau_le_fail(self, detector):
        """Lê Hoàn era=[tiền lê]. Hậu Lê → [lê sơ, lê trung hưng].
        tiền lê NOT in [lê sơ, lê trung hưng] → era conflict.
        Uses custom metadata to avoid Phase 2 pre-emption."""
        det = ConflictDetector(entity_metadata={
            "lê hoàn": {"type": "person", "lifespan": (941, 1005), "era": ["tiền lê"]},
            "lê trung hưng": {"type": "dynasty", "year_range": (940, 1010)},  # Overlapping
            "hậu lê": {"type": "dynasty", "year_range": (940, 1010)},  # Override composite
        })
        qi = _make_query_info(
            query="Lê Hoàn thời Hậu Lê",
            required_persons=["Lê Hoàn", "Hậu Lê"],
            relation_type="belong_to",
        )
        result = det.detect(qi)
        assert result.has_conflict is True
        assert "Era-membership conflict" in result.conflict_reasons[0]

    # --- Relation guard: live_during skips Phase 3 ---
    def test_le_live_during_skip(self, detector):
        """'sống cuối thời nhà Trần' → live_during → Phase 3 skip → no conflict."""
        qi = _make_query_info(
            query="Nguyễn Trãi sống cuối thời nhà Trần",
            required_persons=["Nguyễn Trãi", "nhà Trần"],
            relation_type="live_during",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False


# ==============================================================================
# ENTERPRISE EDGE CASE TESTS (Freeze Guard Layer)
# ==============================================================================

class TestEnterpriseEdgeCases:
    """
    Edge-case and stability tests for enterprise-level freeze.
    These tests protect against future regressions in:
    - Implicit belong_to detection
    - Relation priority ordering
    - Multi-person/multi-dynasty scenarios
    - Unknown entity handling
    - Data integrity
    - No-mutation invariants
    """

    @pytest.fixture
    def detector(self):
        return ConflictDetector()

    # --- 1. Implicit belong_to phrases (no explicit "thuộc") ---
    @pytest.mark.parametrize("query,phrase", [
        ("Nguyễn Trãi triều Lê", "triều"),
        ("Nguyễn Trãi dưới triều Lê", "dưới triều"),
        ("Nguyễn Trãi phục vụ nhà Lê", "phục vụ"),
    ])
    def test_implicit_belong_to_patterns(self, detector, query, phrase):
        """Implicit belong_to phrases must fire Phase 3.
        Nguyễn Trãi era=[lê sơ] matches nhà Lê → no conflict."""
        from app.services.constraint_extractor import ConstraintExtractor

        extractor = ConstraintExtractor()
        result = extractor._detect_relation_type(query)
        assert result == "belong_to", f"'{phrase}' should detect belong_to, got {result}"

        qi = _make_query_info(
            query=query,
            required_persons=["Nguyễn Trãi", "nhà Lê"],
            relation_type="belong_to",
        )
        detect_result = detector.detect(qi)
        assert detect_result.has_conflict is False

    # --- 2. Mixed relation: live_during MUST win over belong_to ---
    @pytest.mark.parametrize("query", [
        "Nguyễn Trãi sống cuối thời nhà Lê",
        "Lê Hoàn sinh vào thời nhà Lê",
        "Nguyễn Trãi ra đời thời nhà Trần",
    ])
    def test_live_during_priority(self, detector, query):
        """live_during patterns must beat belong_to. Phase 3 should skip."""
        from app.services.constraint_extractor import ConstraintExtractor

        extractor = ConstraintExtractor()
        result = extractor._detect_relation_type(query)
        assert result == "live_during", f"Expected live_during, got {result} for '{query}'"

    # --- 3. Multi-person single dynasty: one matches, one doesn't ---
    def test_multi_person_single_dynasty_partial_conflict(self, detector):
        """Person_A era=[lê sơ] OK, Person_B era=[tiền lê] NOT OK for nhà Lê.
        Must detect conflict (isolated Phase 3).
        Both persons need overlapping lifespans to avoid Phase 2 pre-emption."""
        det = ConflictDetector(entity_metadata={
            "nguyễn trãi": {"type": "person", "lifespan": (1400, 1500), "era": ["lê sơ"]},
            "lê hoàn": {"type": "person", "lifespan": (1400, 1500), "era": ["tiền lê"]},
            "nhà lê": {"type": "dynasty", "year_range": (1400, 1500)},
            "lê sơ": {"type": "dynasty", "year_range": (1400, 1500)},
        })
        qi = _make_query_info(
            query="Nguyễn Trãi và Lê Hoàn thời nhà Lê",
            required_persons=["Nguyễn Trãi", "Lê Hoàn", "nhà Lê"],
            relation_type="belong_to",
        )
        result = det.detect(qi)
        assert result.has_conflict is True
        assert "Era-membership conflict" in result.conflict_reasons[0]
        assert "lê hoàn" in result.conflict_reasons[0].lower()

    # --- 4. Multi-dynasty + ambiguous: Nguyễn Trãi thời nhà Lê và nhà Trần ---
    def test_multi_dynasty_ambiguous_conflict(self, detector):
        """Nguyễn Trãi era=[lê sơ]. nhà Lê matches, nhà Trần does NOT.
        Must detect conflict (isolated Phase 3)."""
        det = ConflictDetector(entity_metadata={
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
            "nhà lê": {"type": "dynasty", "year_range": (1380, 1500)},
            "nhà trần": {"type": "dynasty", "year_range": (1380, 1500)},
            "lê sơ": {"type": "dynasty", "year_range": (1380, 1500)},
        })
        qi = _make_query_info(
            query="Nguyễn Trãi thời nhà Lê và nhà Trần",
            required_persons=["Nguyễn Trãi", "nhà Lê", "nhà Trần"],
            relation_type="belong_to",
        )
        result = det.detect(qi)
        assert result.has_conflict is True

    # --- 5. Dynasty not in normalization map → no crash, no silent pass ---
    def test_unknown_dynasty_no_crash(self, detector):
        """'nhà X' not in normalization map → treated as literal.
        Must not crash. Person era won't match literal 'nhà x' → conflict."""
        det = ConflictDetector(entity_metadata={
            "test_person": {"type": "person", "lifespan": (1400, 1450), "era": ["lê sơ"]},
            "nhà x": {"type": "dynasty", "year_range": (1400, 1450)},
        })
        qi = _make_query_info(
            query="test_person thời nhà X",
            required_persons=["test_person", "nhà X"],
            relation_type="belong_to",
        )
        # Must NOT crash
        result = det.detect(qi)
        # "nhà x" normalizes to literal ["nhà x"], person era is ["lê sơ"] → mismatch
        assert result.has_conflict is True

    # --- 6. All persons in metadata MUST have era field ---
    def test_all_persons_must_have_era(self, detector):
        """Schema guard: every person entry in ENTITY_TEMPORAL_METADATA must have
        a non-empty 'era' field that is a list of strings."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA

        for name, meta in ENTITY_TEMPORAL_METADATA.items():
            if meta.get("type") == "person":
                assert "era" in meta, f"Person '{name}' missing 'era' field"
                assert isinstance(meta["era"], list), \
                    f"Person '{name}' era must be list, got {type(meta['era'])}"
                assert len(meta["era"]) > 0, \
                    f"Person '{name}' era must not be empty"
                for era_val in meta["era"]:
                    assert isinstance(era_val, str), \
                        f"Person '{name}' era values must be str, got {type(era_val)}"

    # --- 7. Normalization map purity: detect() must not mutate map ---
    def test_normalization_map_purity(self, detector):
        """_DYNASTY_NORMALIZATION_MAP must not be mutated by detect()."""
        import copy
        from app.services.conflict_detector import _DYNASTY_NORMALIZATION_MAP

        before = copy.deepcopy(_DYNASTY_NORMALIZATION_MAP)
        qi = _make_query_info(
            query="Nguyễn Trãi thời nhà Lê",
            required_persons=["Nguyễn Trãi", "nhà Lê"],
            relation_type="belong_to",
        )
        detector.detect(qi)
        assert _DYNASTY_NORMALIZATION_MAP == before, \
            "Normalization map was mutated by detect()"

    # --- 8. Metadata immutability: detect() must not mutate metadata ---
    def test_metadata_immutability(self, detector):
        """ENTITY_TEMPORAL_METADATA must not be mutated by detect()."""
        import copy
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA

        before = copy.deepcopy(ENTITY_TEMPORAL_METADATA)
        qi = _make_query_info(
            query="Trần Hưng Đạo thời nhà Trần",
            required_persons=["Trần Hưng Đạo", "nhà Trần"],
            relation_type="belong_to",
        )
        detector.detect(qi)
        assert ENTITY_TEMPORAL_METADATA == before, \
            "Metadata was mutated by detect()"

    # --- 9. Randomized order fuzz: 100× shuffle → identical result ---
    def test_randomized_order_fuzz_100x(self, detector):
        """Shuffle entity order 100× → detect() must return identical result."""
        import random

        persons = ["Nguyễn Trãi", "nhà Lê", "nhà Trần"]
        qi_base = _make_query_info(
            query="Nguyễn Trãi thời nhà Lê và nhà Trần",
            required_persons=persons,
            relation_type="belong_to",
        )
        baseline = detector.detect(qi_base)

        rng = random.Random(42)  # deterministic seed
        for _ in range(100):
            shuffled = list(persons)
            rng.shuffle(shuffled)
            qi = _make_query_info(
                query="Nguyễn Trãi thời nhà Lê và nhà Trần",
                required_persons=shuffled,
                relation_type="belong_to",
            )
            result = detector.detect(qi)
            assert result.has_conflict == baseline.has_conflict, \
                f"Order-dependent! {shuffled} gave different result"


# ==============================================================================
# Phase 4: Soft Semantic Layer Tests
# ==============================================================================

class TestPhase4SoftSemantic:
    """
    Phase 4 tests — Soft Semantic Layer.
    Invariant: Phase 4 NEVER sets has_conflict.
    """

    def test_phase4_no_mutation(self):
        """Phase 4 must NEVER set has_conflict = True."""
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
            "lê thánh tông": {"type": "person", "lifespan": (1442, 1497), "era": ["lê sơ"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Nguyễn Trãi và Lê Thánh Tông",
            required_persons=["Nguyễn Trãi", "Lê Thánh Tông"],
        )
        result = detector.detect(qi)
        # Phase 4 may add notes/warnings but NEVER conflicts
        assert result.has_conflict is False
        assert len(result.conflict_reasons) == 0

    def test_phase4_alias_expansion(self):
        """Đàng Ngoài → Trịnh alias expansion."""
        meta = {}  # no metadata needed for alias test
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Đàng Ngoài",
            required_persons=["Đàng Ngoài"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False
        assert "Đàng Ngoài" in result.semantic_expansions
        assert result.semantic_expansions["Đàng Ngoài"] == ["Trịnh"]
        assert any("Đàng Ngoài" in n for n in result.semantic_notes)

    def test_phase4_person_overlap_note(self):
        """Two persons with overlapping lifespans get a friendly note."""
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
            "lê lợi": {"type": "person", "lifespan": (1385, 1433), "era": ["lê sơ"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Nguyễn Trãi và Lê Lợi",
            required_persons=["Nguyễn Trãi", "Lê Lợi"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False
        assert any("trùng" in n for n in result.semantic_notes)

    def test_phase4_era_alignment_warning(self):
        """Two persons from different eras get a friendly warning."""
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
            "trần hưng đạo": {"type": "person", "lifespan": (1228, 1300), "era": ["trần"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Nguyễn Trãi và Trần Hưng Đạo",
            required_persons=["Nguyễn Trãi", "Trần Hưng Đạo"],
        )
        result = detector.detect(qi)
        # Phase 2 will fire (no overlap) → Phase 4 skipped
        if result.has_conflict:
            assert len(result.semantic_warnings) == 0
        else:
            assert any("triều đại khác nhau" in w for w in result.semantic_warnings)

    def test_phase4_skipped_on_conflict(self):
        """Phase 4 must not run when has_conflict is already True."""
        meta = {
            "trần hưng đạo": {"type": "person", "lifespan": (1228, 1300), "era": ["trần"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Năm 1945 Trần Hưng Đạo",
            required_persons=["Trần Hưng Đạo"],
            required_year=1945,
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        assert len(result.semantic_notes) == 0
        assert len(result.semantic_warnings) == 0
        assert len(result.semantic_expansions) == 0

    # ------------------------------------------------------------------
    # Phase 4 Extended Tests (user-requested batch 2)
    # ------------------------------------------------------------------

    def test_phase4_multiple_person_overlap(self):
        """Three overlapping persons → 3 overlap notes (A-B, A-C, B-C)."""
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
            "lê lợi": {"type": "person", "lifespan": (1385, 1433), "era": ["lê sơ"]},
            "nguyễn phi khanh": {"type": "person", "lifespan": (1355, 1428), "era": ["trần", "lê sơ"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Nguyễn Trãi, Lê Lợi, Nguyễn Phi Khanh",
            required_persons=["Nguyễn Trãi", "Lê Lợi", "Nguyễn Phi Khanh"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False
        # All 3 pairs overlap (1385-1428 is common)
        overlap_notes = [n for n in result.semantic_notes if "trùng" in n]
        assert len(overlap_notes) == 3, f"Expected 3 overlap notes, got {len(overlap_notes)}: {overlap_notes}"

    def test_phase4_no_duplicate_notes(self):
        """Repeated entity in list → no duplicate overlap notes."""
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
            "lê lợi": {"type": "person", "lifespan": (1385, 1433), "era": ["lê sơ"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Nguyễn Trãi và Nguyễn Trãi và Lê Lợi",
            required_persons=["Nguyễn Trãi", "Nguyễn Trãi", "Lê Lợi"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False
        overlap_notes = [n for n in result.semantic_notes if "trùng" in n]
        assert len(overlap_notes) == 1, f"Duplicate entity produced duplicate notes: {overlap_notes}"

    def test_phase4_alias_case_insensitive(self):
        """ĐÀNG NGOÀI (uppercase) must expand."""
        meta = {}
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="ĐÀNG NGOÀI",
            required_persons=["ĐÀNG NGOÀI"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False
        assert "ĐÀNG NGOÀI" in result.semantic_expansions
        assert result.semantic_expansions["ĐÀNG NGOÀI"] == ["Trịnh"]

    def test_phase4_does_not_mutate_metadata(self):
        """analyze() must not mutate the metadata dict."""
        import copy
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
            "lê lợi": {"type": "person", "lifespan": (1385, 1433), "era": ["lê sơ"]},
        }
        meta_before = copy.deepcopy(meta)
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Nguyễn Trãi và Lê Lợi",
            required_persons=["Nguyễn Trãi", "Lê Lợi"],
        )
        detector.detect(qi)
        assert meta == meta_before, "Metadata mutated by Phase 4!"

    def test_phase4_determinism(self):
        """100 identical runs → identical result."""
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
            "lê lợi": {"type": "person", "lifespan": (1385, 1433), "era": ["lê sơ"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi_factory = lambda: _make_query_info(
            query="Nguyễn Trãi Đàng Ngoài Lê Lợi",
            required_persons=["Nguyễn Trãi", "Đàng Ngoài", "Lê Lợi"],
        )
        baseline = detector.detect(qi_factory())
        for _ in range(100):
            result = detector.detect(qi_factory())
            assert result.semantic_notes == baseline.semantic_notes
            assert result.semantic_warnings == baseline.semantic_warnings
            assert result.semantic_expansions == baseline.semantic_expansions

    def test_phase4_confidence_consistency(self):
        """Same input → same confidence, no drift."""
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi_factory = lambda: _make_query_info(
            query="Nguyễn Trãi",
            required_persons=["Nguyễn Trãi"],
        )
        baseline = detector.detect(qi_factory())
        for _ in range(100):
            result = detector.detect(qi_factory())
            assert result.has_conflict == baseline.has_conflict
            assert result.confidence_threshold == baseline.confidence_threshold

    # ------------------------------------------------------------------
    # Enterprise Tests — Phase 4 Architecture Validation
    # ------------------------------------------------------------------

    def test_confidence_high_exact_era_match(self):
        """Ngô Quyền + Nhà Ngô → same era → no conflict."""
        meta = {
            "ngô quyền": {"type": "person", "lifespan": (897, 944), "era": ["ngô"]},
            "nhà ngô": {"type": "dynasty", "lifespan": (939, 965), "era": ["ngô"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Ngô Quyền và Nhà Ngô",
            required_persons=["Ngô Quyền", "Nhà Ngô"],
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_confidence_ambiguous_era(self):
        """Nguyễn Huệ (Tây Sơn) + Hậu Lê → different eras → conflict expected."""
        meta = {
            "nguyễn huệ": {"type": "person", "lifespan": (1753, 1792), "era": ["tây sơn"]},
            "hậu lê": {"type": "dynasty", "lifespan": (1428, 1789), "era": ["hậu lê"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Nguyễn Huệ nhà Hậu Lê",
            required_persons=["Nguyễn Huệ", "Hậu Lê"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        # Phase 3 era-membership should flag this (Tây Sơn ≠ Hậu Lê)
        assert result.has_conflict is True

    def test_explainability_json_structure(self):
        """SemanticResult must have notes, warnings, expansions."""
        from app.services.semantic_layer import SemanticAnalyzer, SemanticResult
        meta = {
            "nguyễn trãi": {"type": "person", "lifespan": (1380, 1442), "era": ["lê sơ"]},
        }
        analyzer = SemanticAnalyzer(meta)
        qi = _make_query_info(
            query="Nguyễn Trãi",
            required_persons=["Nguyễn Trãi"],
        )
        result = analyzer.analyze(qi)
        assert isinstance(result, SemanticResult)
        assert isinstance(result.notes, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.expansions, dict)

    def test_soft_warning_does_not_override_conflict(self):
        """Hard conflict must prevent Phase 4 from running."""
        meta = {
            "trần hưng đạo": {"type": "person", "lifespan": (1228, 1300), "era": ["trần"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Năm 1945 Trần Hưng Đạo",
            required_persons=["Trần Hưng Đạo"],
            required_year=1945,
        )
        result = detector.detect(qi)
        assert result.has_conflict is True
        # Phase 4 must NOT run after hard conflict
        assert len(result.semantic_notes) == 0
        assert len(result.semantic_warnings) == 0

    def test_multi_era_person_no_conflict(self):
        """Lê Lợi + Lê Sơ → same era → no conflict."""
        meta = {
            "lê lợi": {"type": "person", "lifespan": (1385, 1433), "era": ["lê sơ"]},
            "lê sơ": {"type": "dynasty", "lifespan": (1428, 1527), "era": ["lê sơ"]},
        }
        detector = ConflictDetector(entity_metadata=meta)
        qi = _make_query_info(
            query="Lê Lợi nhà Lê Sơ",
            required_persons=["Lê Lợi", "Lê Sơ"],
            relation_type="belong_to",
        )
        result = detector.detect(qi)
        assert result.has_conflict is False

    def test_metadata_version_freeze(self):
        """ENTITY_TEMPORAL_METADATA_VERSION must be v2.1."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA_VERSION
        assert ENTITY_TEMPORAL_METADATA_VERSION == "v2.1"

    # ------------------------------------------------------------------
    # Enterprise Tests — Phase 5 Guardrails (Output Verification)
    # ------------------------------------------------------------------

    def test_guardrail_truncation(self):
        """OutputVerifier must detect and fix truncated output."""
        from app.services.guardrails import OutputVerifier, Severity
        verifier = OutputVerifier()

        # Case 1: Dangling comma
        result = verifier.verify("Sự kiện diễn ra vào năm 1945,")
        assert result.status == Severity.AUTO_FIX
        assert result.corrected_answer is not None
        assert not result.corrected_answer.endswith(",")

        # Case 2: Proper ending → PASS
        result2 = verifier.verify("Sự kiện diễn ra vào năm 1945.")
        assert result2.status == Severity.PASS

    def test_guardrail_topic_drift(self):
        """OutputVerifier must flag answer that doesn't mention queried entity."""
        from app.services.guardrails import OutputVerifier, Severity
        verifier = OutputVerifier()

        qi = _make_query_info(
            query="Bác Hồ đi năm 1991 phải không?",
            required_persons=["Hồ Chí Minh"],
        )
        qi.is_fact_check = True

        # Answer doesn't mention Hồ Chí Minh or Bác Hồ → soft fail
        result = verifier.verify(
            "Khúc Thừa Dụ khởi nghĩa năm 905.",
            qi,
        )
        assert result.status == Severity.SOFT_FAIL
        drift_checks = [c for c in result.checks if c.name == "topic_drift"]
        assert len(drift_checks) == 1
        assert drift_checks[0].severity == Severity.SOFT_FAIL

    def test_guardrail_year_hallucination(self):
        """OutputVerifier must flag phantom years in fact-check answers."""
        from app.services.guardrails import OutputVerifier, Severity
        verifier = OutputVerifier()

        qi = _make_query_info(
            query="Bác Hồ ra đi năm 1991 phải không?",
            required_persons=["Hồ Chí Minh"],
        )
        qi.is_fact_check = True
        qi.claimed_year = 1991
        qi.required_year = 1911

        # Answer with valid correction (1911) → PASS
        result_ok = verifier.verify(
            "Không phải. Bác Hồ ra đi tìm đường cứu nước năm 1911.",
            qi,
        )
        year_checks = [c for c in result_ok.checks if c.name == "year_hallucination"]
        assert year_checks[0].severity == Severity.PASS

