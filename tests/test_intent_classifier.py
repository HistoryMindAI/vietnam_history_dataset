"""
test_intent_classifier.py — Test Suite for Intent Classifier V2

~40 test cases covering:
- Duration guard (Principle 2)
- Question type detection (Principle 3)
- Data scope detection (Principle 5)
- All 10 intents
- Edge cases and typo tolerance
"""
import pytest
from app.services.intent_classifier import (
    detect_duration_guard,
    detect_question_type,
    is_data_scope_query,
    classify_intent,
    QueryAnalysis,
)


# ===================================================================
# 1. DURATION GUARD TESTS (Principle 2)
# ===================================================================

class TestDurationGuard:
    """Test that duration expressions are NOT confused with years."""

    def test_ky_niem_1000_nam(self):
        assert detect_duration_guard("kỷ niệm 1000 năm Thăng Long") is True

    def test_ki_niem_1000_nam_unaccented(self):
        assert detect_duration_guard("kỉ niệm 1000 năm Thăng Long") is True

    def test_hon_150_nam(self):
        assert detect_duration_guard("hơn 150 năm chia cắt") is True

    def test_gan_100_nam(self):
        assert detect_duration_guard("gần 100 năm đô hộ") is True

    def test_tron_100_nam(self):
        assert detect_duration_guard("tròn 100 năm") is True

    def test_1000_nam_thang_long(self):
        assert detect_duration_guard("1000 năm Thăng Long") is True

    def test_150_nam_chia_cat(self):
        assert detect_duration_guard("150 năm chia cắt") is True

    def test_khoang_200_nam(self):
        assert detect_duration_guard("khoảng 200 năm tồn tại") is True

    def test_100_nam_ke_tu(self):
        assert detect_duration_guard("100 năm kể từ") is True

    def test_NOT_duration_nam_1000(self):
        """'năm 1000' is an explicit year, not a duration."""
        assert detect_duration_guard("năm 1000") is False

    def test_NOT_duration_nam_1945(self):
        assert detect_duration_guard("năm 1945 có gì") is False

    def test_NOT_duration_plain_year(self):
        assert detect_duration_guard("sự kiện năm 1975") is False

    def test_NOT_duration_no_number(self):
        assert detect_duration_guard("Trần Hưng Đạo là ai") is False


# ===================================================================
# 2. QUESTION TYPE DETECTION TESTS (Principle 3)
# ===================================================================

class TestQuestionType:
    """Test question type classification."""

    def test_when_nam_nao(self):
        assert detect_question_type("Bác Hồ ra đi năm nào") == "when"

    def test_when_khi_nao(self):
        assert detect_question_type("khi nào thống nhất") == "when"

    def test_when_nam_bao_nhieu(self):
        assert detect_question_type("xảy ra năm bao nhiêu") == "when"

    def test_when_english(self):
        assert detect_question_type("when did the war end") == "when"

    def test_who_la_ai(self):
        assert detect_question_type("Trần Hưng Đạo là ai") == "who"

    def test_who_ai_la(self):
        assert detect_question_type("ai là vua triều Trần") == "who"

    def test_who_english(self):
        assert detect_question_type("who is Trần Hưng Đạo") == "who"

    def test_list_cac_su_kien(self):
        assert detect_question_type("các sự kiện thời Trần") == "list"

    def test_list_nhung_gi(self):
        assert detect_question_type("những gì xảy ra") == "list"

    def test_list_liet_ke(self):
        assert detect_question_type("liệt kê các trận đánh") == "list"

    def test_list_co_gi(self):
        assert detect_question_type("năm 1945 có gì") == "list"

    def test_list_lich_su(self):
        assert detect_question_type("lịch sử Việt Nam") == "list"

    def test_scope_co_du_lieu(self):
        assert detect_question_type("bạn có dữ liệu gì") == "scope"

    def test_scope_dataset(self):
        assert detect_question_type("dataset của bạn gồm gì") == "scope"

    def test_scope_pham_vi(self):
        assert detect_question_type("phạm vi dữ liệu") == "scope"

    def test_default_what(self):
        assert detect_question_type("Trần Hưng Đạo đánh giặc") == "what"


# ===================================================================
# 3. DATA SCOPE TESTS (Principle 5)
# ===================================================================

class TestDataScope:
    """Test data scope query detection."""

    def test_co_du_lieu_gi(self):
        assert is_data_scope_query("bạn có dữ liệu gì") is True

    def test_du_kien_cua_ban(self):
        assert is_data_scope_query("dữ kiện của bạn") is True

    def test_pham_vi_du_lieu(self):
        assert is_data_scope_query("phạm vi dữ liệu") is True

    def test_co_lich_su_den_nam(self):
        assert is_data_scope_query("có lịch sử đến năm nào") is True

    def test_NOT_scope_regular(self):
        assert is_data_scope_query("Trần Hưng Đạo đánh giặc") is False


# ===================================================================
# 4. INTENT CLASSIFICATION TESTS (All 10 Intents)
# ===================================================================

class TestClassifyIntent:
    """Test the core intent classification."""

    # 4.1 data_scope
    def test_data_scope(self):
        r = classify_intent("bạn có dữ liệu gì")
        assert r.intent == "data_scope"
        assert r.focus == "scope"

    # 4.2 year_range
    def test_year_range(self):
        r = classify_intent("sự kiện", year_range=(1945, 1975))
        assert r.intent == "year_range"

    # 4.3 year_range from multi_years
    def test_multi_years(self):
        r = classify_intent("sự kiện", multi_years=[1945, 1954, 1975])
        assert r.intent == "year_range"
        assert r.year_range == (1945, 1975)

    # 4.4 relationship
    def test_relationship(self):
        r = classify_intent(
            "Quang Trung và Nguyễn Huệ có quan hệ gì",
            resolved_entities={"persons": ["Quang Trung", "Nguyễn Huệ"]}
        )
        assert r.intent == "relationship"

    # 4.5 definition
    def test_definition_person(self):
        r = classify_intent(
            "Trần Hưng Đạo là ai",
            resolved_entities={"persons": ["Trần Hưng Đạo"]}
        )
        assert r.intent == "definition"
        assert r.question_type == "who"

    # 4.6 person_query
    def test_person_query(self):
        r = classify_intent(
            "Trần Hưng Đạo đã làm gì",
            resolved_entities={"persons": ["Trần Hưng Đạo"]}
        )
        assert r.intent == "person_query"
        assert r.focus == "person"

    # 4.7 dynasty_query
    def test_dynasty_query(self):
        r = classify_intent(
            "thời Trần có gì",
            resolved_entities={"dynasties": ["Trần"]}
        )
        assert r.intent == "dynasty_query"

    # 4.8 dynasty_timeline
    def test_dynasty_timeline(self):
        r = classify_intent(
            "các triều đại Việt Nam",
            resolved_entities={"dynasties": ["triều đại"]}
        )
        assert r.intent == "dynasty_timeline"

    # 4.9 event_query
    def test_event_query(self):
        r = classify_intent(
            "trận Bạch Đằng",
            resolved_entities={"topics": ["trận Bạch Đằng"]}
        )
        assert r.intent == "event_query"

    # 4.10 year_specific
    def test_year_specific(self):
        r = classify_intent("năm 1945", year=1945)
        assert r.intent == "year_specific"

    # 4.11 semantic fallback
    def test_semantic_fallback(self):
        r = classify_intent("câu hỏi mơ hồ không rõ")
        assert r.intent == "semantic"
        assert r.confidence == 0.5

    # 4.12 broad_history
    def test_broad_history(self):
        r = classify_intent("lịch sử Việt Nam")
        assert r.intent == "broad_history"

    # 4.13 resistance (plain "kháng chiến" → event_query, "các cuộc" → broad)
    def test_resistance(self):
        r = classify_intent("kháng chiến chống giặc")
        assert r.intent == "event_query"
        assert r.question_type == "list"

    def test_resistance_broad(self):
        """'các cuộc kháng chiến' is broad enough to trigger broad_history."""
        r = classify_intent("các cuộc kháng chiến")
        assert r.intent == "broad_history"


# ===================================================================
# 5. DURATION GUARD INTEGRATION TESTS
# ===================================================================

class TestDurationGuardIntegration:
    """Test that duration guard correctly blocks year extraction."""

    def test_1000_nam_thang_long_no_year(self):
        """'kỷ niệm 1000 năm' should NOT trigger year_specific intent."""
        r = classify_intent("kỷ niệm 1000 năm Thăng Long", year=1000)
        # Duration guard should nullify the year
        assert r.duration_guard is True
        assert r.year is None
        assert r.intent != "year_specific"

    def test_hon_150_nam_no_year(self):
        r = classify_intent("hơn 150 năm chia cắt", year=150)
        assert r.duration_guard is True
        assert r.year is None

    def test_nam_1945_preserves_year(self):
        """Regular year queries should NOT be blocked."""
        r = classify_intent("năm 1945 có gì", year=1945)
        assert r.duration_guard is False
        assert r.year == 1945


# ===================================================================
# 6. PERSON + WHEN COMBINATION
# ===================================================================

class TestPersonWhenCombo:
    """Test when-questions about specific persons."""

    def test_person_when_query(self):
        r = classify_intent(
            "Bác Hồ sinh năm nào",
            resolved_entities={"persons": ["Hồ Chí Minh"]}
        )
        assert r.intent == "person_query"
        assert r.question_type == "when"

    def test_person_what_query(self):
        r = classify_intent(
            "Bác Hồ đã làm gì trong cách mạng",
            resolved_entities={"persons": ["Hồ Chí Minh"]}
        )
        assert r.intent == "person_query"
        assert r.question_type == "what"
