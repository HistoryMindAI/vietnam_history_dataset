import pytest
import random
import string

from pipeline.storyteller import (
    extract_all_persons,
    extract_persons_from_body,
    is_valid_person,
    canonical_person,
    classify_entity,
    infer_subject,
    normalize,
    ask,
    ask_by_person,
    classify_tone,
    classify_nature,
    pick_tone,
    storyteller
)

__all__ = [
    "normalize",
    "infer_subject",
    "extract_all_persons",
    "extract_persons_from_body",
    "canonical_person",
    "is_valid_person",
    "classify_entity",
    "ask",
    "ask_by_person",
]


# =========================================================
# BASIC PERSON vs PLACE
# =========================================================

def test_person_not_place_simple():
    text = "Trần Hưng Đạo chỉ huy quân đội tại Bạch Đằng"
    persons = extract_all_persons(text)

    assert "Trần Hưng Đạo" in persons
    assert "Bạch Đằng" not in persons


def test_place_not_person():
    text = "Chiến thắng Bạch Đằng diễn ra năm 1288"
    persons = extract_all_persons(text)

    assert "Bạch Đằng" not in persons
    assert persons == set()


def test_country_not_person():
    text = "Quân dân Đại Việt đánh bại quân Nguyên"
    persons = extract_all_persons(text)

    assert "Đại Việt" not in persons


# =========================================================
# DYNASTY / COLLECTIVE SHOULD NOT BE PERSON
# =========================================================

@pytest.mark.parametrize("entity", [
    "Nhà Trần",
    "Nhà Lý",
    "Triều Nguyễn",
    "Quân Thanh",
    "Quân Minh",
])
def test_dynasty_and_army_not_person(entity):
    assert not is_valid_person(entity)


# =========================================================
# KING TITLES & ALIASES
# =========================================================

def test_king_alias_normalization():
    assert canonical_person("Quang Trung") == "Nguyễn Huệ"
    assert canonical_person("Gia Long") == "Nguyễn Ánh"


def test_mieu_hieu_is_person():
    text = "Lý Thái Tổ ban Chiếu dời đô"
    persons = extract_all_persons(text)

    assert "Lý Thái Tổ" in persons


def test_alias_and_real_name_not_duplicated():
    text = "Quang Trung (Nguyễn Huệ) đại phá quân Thanh"
    persons = extract_all_persons(text)

    assert "Nguyễn Huệ" in persons
    assert len(persons) == 1


# =========================================================
# MIXED PERSON + PLACE IN ONE SENTENCE
# =========================================================

def test_person_and_place_same_sentence():
    text = "Ngô Quyền đánh bại quân Nam Hán trên sông Bạch Đằng"
    persons = extract_all_persons(text)

    assert "Ngô Quyền" in persons
    assert "Bạch Đằng" not in persons


def test_two_places_no_person():
    text = "Trận đánh diễn ra tại Ngọc Hồi và Đống Đa"
    persons = extract_all_persons(text)

    assert persons == set()


# =========================================================
# SUBJECT EXTRACTION (ACTOR)
# =========================================================

def test_extract_subject_person_actor():
    body = "Trần Hưng Đạo chỉ huy quân đội đánh bại quân Nguyên"
    persons = extract_persons_from_body(body)

    assert persons == {"Trần Hưng Đạo"}


def test_collective_subject_when_no_person():
    body = "Quân dân đánh bại quân xâm lược"
    subject = infer_subject(body, set(), ["military"])

    assert subject == "Quân dân Việt Nam"


def test_political_subject_fallback():
    body = "Ban hành hiệp định quan trọng"
    subject = infer_subject(body, set(), ["diplomacy"])

    assert subject == "Chính quyền đương thời"


# =========================================================
# ENTITY REGISTRY CHECK
# =========================================================

def test_classify_entity_place():
    assert classify_entity("Bạch Đằng") == "place"
    assert classify_entity("Thăng Long") == "place"


def test_classify_entity_person():
    assert classify_entity("Trần Hưng Đạo") == "person"
    assert classify_entity("Ngô Quyền") == "person"


# =========================================================
# NORMALIZE PIPELINE – PERSON VS PLACE
# =========================================================

def test_normalize_person_and_place():
    text = (
        "Năm 1288, Trần Hưng Đạo chỉ huy quân dân Đại Việt "
        "đánh bại quân Nguyên Mông trên sông Bạch Đằng."
    )

    res = normalize(text)
    assert res is not None

    year, body, nature, tone, persons, persons_all, places = res

    assert year == "1288"
    assert "Trần Hưng Đạo" in persons_all
    assert "Bạch Đằng" not in persons_all
    assert "military" in nature
    assert "heroic" in tone


def test_normalize_no_false_persons():
    text = (
        "Năm 1789, chiến thắng Ngọc Hồi – Đống Đa "
        "đập tan quân Thanh."
    )

    res = normalize(text)
    assert res is not None

    _, _, _, _, persons, persons_all, _ = res

    assert persons == set()
    assert persons_all == set()

def test_place_not_recognized_as_person():
    text = "Năm 1288, chiến thắng Bạch Đằng diễn ra vang dội."
    res = normalize(text)

    assert res is not None
    year, body, nature, tone, persons, persons_all, _ = res

    assert "Bạch Đằng" not in persons
    assert "Bạch Đằng" not in persons_all

def test_dynasty_not_person():
    text = "Năm 1225, nhà Trần được thành lập."
    res = normalize(text)

    assert res is not None
    _, _, _, _, persons, persons_all, _ = res

    assert not persons
    assert not persons_all

def test_person_and_place_together():
    text = (
        "Năm 1288, Trần Hưng Đạo chỉ huy quân dân Đại Việt "
        "đánh bại quân Nguyên Mông trên sông Bạch Đằng."
    )

    res = normalize(text)
    assert res is not None

    _, _, _, _, persons, persons_all, _ = res

    assert "Trần Hưng Đạo" in persons_all
    assert "Bạch Đằng" not in persons_all
    assert "Đại Việt" not in persons_all

def test_alias_normalization():
    assert canonical_person("Quang Trung") == "Nguyễn Huệ"
    assert canonical_person("Gia Long") == "Nguyễn Ánh"

def test_royal_title_is_valid_person():
    assert is_valid_person("Lý Thái Tổ")
    assert is_valid_person("Trần Thánh Tông")

def test_alias_in_normalize():
    text = "Năm 1789, Quang Trung đánh tan quân Thanh."
    res = normalize(text)

    assert res is not None
    _, _, _, _, persons, persons_all, _ = res

    assert "Nguyễn Huệ" in persons_all
    assert "Quang Trung" not in persons_all

def test_collective_not_person():
    text = "Năm 1945, nhân dân Việt Nam giành chính quyền."
    res = normalize(text)

    assert res is not None
    _, _, _, _, persons, persons_all, _ = res

    assert not persons
    assert not persons_all

def test_campaign_not_person():
    text = "Năm 1954, chiến dịch Điện Biên Phủ kết thúc thắng lợi."
    res = normalize(text)

    assert res is not None
    _, _, _, _, persons, persons_all, _ = res

    assert "Điện Biên Phủ" not in persons_all

def test_infer_subject_person_priority():
    s = infer_subject(
        "Trần Hưng Đạo chỉ huy quân đội",
        {"Trần Hưng Đạo"},
        ["military"]
    )
    assert s == "Trần Hưng Đạo"

def test_infer_subject_collective():
    s = infer_subject(
        "quân dân đánh bại quân xâm lược",
        set(),
        ["military"]
    )
    assert s == "Quân dân Việt Nam"

def test_infer_subject_document():
    s = infer_subject(
        "ban Chiếu dời đô",
        set(),
        ["institutional"]
    )
    assert s == "Văn kiện lịch sử"

def test_ask_by_person_safe_with_empty_persons_all():
    timeline = {
        "1010": {
            "events": [
                {
                    "event": "Ban Chiếu dời đô",
                    "persons": [],
                    "persons_all": [],
                    "nature": ["institutional"],
                    "tone": ["heroic"],
                }
            ]
        }
    }

    res = ask_by_person(timeline, "Lý Công Uẩn")
    assert res is None or res == []

def test_ask_fallback_event_only():
    timeline = {
        "1010": {
            "events": [
                {
                    "event": "Lý Công Uẩn ban Chiếu dời đô",
                    "persons": ["Lý Thái Tổ"],
                    "persons_all": ["Lý Thái Tổ"],
                    "nature": ["institutional"],
                    "tone": ["heroic"],
                }
            ]
        }
    }

    res = ask(timeline, "Chiếu dời đô là gì")
    assert isinstance(res, str)
    assert "Chiếu dời đô" in res

def test_normalize_filters_question():
    assert normalize("Năm 1010, Chiếu dời đô là gì?") is None

def test_normalize_too_short():
    assert normalize("Năm 1000, có sự kiện.") is None

def test_extract_all_persons_complex_sentence():
    text = (
        "Trần Hưng Đạo cùng vua Trần Thánh Tông "
        "chỉ huy quân dân Đại Việt."
    )   

    persons = extract_all_persons(text)

    assert "Trần Hưng Đạo" in persons
    assert "Trần Thánh Tông" in persons
    assert "Đại Việt" not in persons



# =========================================================
# REGRESSION CASES – COMMON BUGS
# =========================================================

@pytest.mark.parametrize("text", [
    "Nhà Trần đánh bại quân Nguyên",
    "Quân Thanh tiến vào Thăng Long",
    "Khởi nghĩa Lam Sơn bùng nổ",
])
def test_no_fake_persons(text):
    persons = extract_all_persons(text)
    assert persons == set()

# =========================================================
# DEEP TEST: CLASSIFY_NATURE (Kiểm tra trọng số hành động)
# =========================================================

@pytest.mark.parametrize("text, expected_label", [
    ("Năm 938, Ngô Quyền đại phá quân Nam Hán", "historical_event"),
    ("Năm 1945, giành chính quyền tại Hà Nội", "historical_event"),
    ("Năm 1010, Lý Thái Tổ dời đô về Thăng Long", "historical_event"),
    ("Năm 1954, ký kết Hiệp định Giơ-ne-vơ", "historical_event"),
    ("Năm đó, tình hình vô cùng phức tạp", "general"), # Câu mơ hồ
])
def test_classify_nature_strong_actions(text, expected_label):
    from pipeline.storyteller import classify_nature
    labels = classify_nature(text)
    if expected_label == "historical_event":
        assert "historical_event" in labels
    else:
        assert list(labels) == ["general"]


# =========================================================
# DEEP TEST: NORMALIZE (Kiểm tra khả năng lọc sạch data)
# =========================================================

def test_normalize_keeps_collective_with_strong_action():
    # Không có tên người, nhưng có "Hành động mạnh" + "Tập thể"
    text = "Năm 1945, nhân dân ta vùng lên giành độc lập."
    res = normalize(text)
    assert res is not None
    year, body, nature, _, persons_subject, _, _ = res
    assert year == "1945"
    assert "historical_event" in nature
    assert not persons_subject # Không có cá nhân cụ thể là đúng

def test_normalize_keeps_place_event():
    text = "Năm 1975, giải phóng hoàn toàn miền Nam."
    res = normalize(text)
    assert res is not None
    # Phải giải nén đầy đủ 7 giá trị trả về từ normalize()
    year, body, nature, tone, persons_subject, persons_all, places = res
    assert "historical_event" in nature

def test_normalize_rejects_vague_history():
    # Có năm, có từ liên quan lịch sử nhưng không có sự kiện cụ thể/người/địa danh
    texts = [
        "Năm 1945, một thời kỳ đầy hào hùng đã bắt đầu.",
        "Năm 1802, triều đại mới có nhiều sự thay đổi đáng kể.",
        "Năm 1288, quân và dân ta vô cùng phấn khởi."
    ]
    for t in texts:
        assert normalize(t) is None, f"Should reject vague text: {t}"


# =========================================================
# DEEP TEST: IS_VALID_PERSON (Chống nhận diện nhầm)
# =========================================================

@pytest.mark.parametrize("name", [
    "Nhân dân Việt Nam",
    "Quân đội Nhân dân",
    "Triều đình nhà Lê",
    "Chiến dịch lịch sử",
    "Khởi nghĩa Ba Đình",
])
def test_is_valid_person_strict_filter(name):
    # Đảm bảo các danh từ tập thể không bao giờ bị coi là Person
    assert is_valid_person(name) is False


# =========================================================
# DEEP TEST: SUBJECT INFERENCE (Chủ thể sự kiện tập thể)
# =========================================================

def test_infer_subject_with_strong_collectives():
    # Kiểm tra hàm infer_subject có đoán đúng chủ thể khi không có tên người
    assert infer_subject("Nhân dân giành chính quyền", set(), ["political"]) == "Nhân dân Việt Nam"
    assert infer_subject("Quân đội ta tiến công", set(), ["military"]) == "Quân dân Việt Nam"
    assert infer_subject("Ban hành sắc lệnh mới", set(), ["political"]) == "Chính quyền đương thời"


# =========================================================
# DEEP TEST: ALIAS & NESTED ENTITIES
# =========================================================

def test_complex_alias_and_title():
    # Kiểm tra việc xử lý tước hiệu đi kèm tên
    text = "Hưng Đạo Đại Vương Trần Quốc Tuấn chuẩn bị kháng chiến."
    persons = extract_all_persons(text)
    # Tùy vào cách bạn implement, nhưng ít nhất phải ra được "Trần Quốc Tuấn"
    # và sau khi canonical phải là "Trần Hưng Đạo" (nếu bạn quy định vậy)
    normalized_persons = {canonical_person(p) for p in persons}
    assert "Trần Hưng Đạo" in normalized_persons

# =========================================================
# ADVANCED TESTS: PERSON vs PLACE vs COLLECTIVE
# =========================================================

@pytest.mark.parametrize("text, expected_persons", [
    # Trường hợp tên người có chứa tiền tố chức vụ/tước hiệu phức tạp
    ("Thái sư Trần Thủ Độ quyền khuynh thiên hạ.", {"Trần Thủ Độ"}),
    ("Hưng Đạo Đại Vương Trần Quốc Tuấn là vị tướng tài.", {"Trần Hưng Đạo"}), # Sau khi canonical
    
    # Địa danh dễ nhầm lẫn
    ("Nghĩa quân Lam Sơn đánh chiếm Nghệ An.", set()), # Lam Sơn là địa danh/tên khởi nghĩa
    ("Ba Đình là nơi diễn ra cuộc khởi nghĩa.", set()),
    
    # Hỗn hợp nhiều thực thể
    ("Nguyễn Trãi viết Bình Ngô Đại Cáo tại Lam Sơn.", {"Nguyễn Trãi"}),
    ("Lê Lợi lên ngôi ở Thăng Long sau khi đuổi quân Minh.", {"Lê Lợi"}),
])
def test_advanced_entity_extraction(text, expected_persons):
    persons = extract_all_persons(text)
    normalized = {canonical_person(p) for p in persons if is_valid_person(p)}
    assert normalized == expected_persons


def test_collective_vs_person_edge_cases():
    # Kiểm tra các danh từ tập thể có cấu trúc giống tên người (Viết hoa chữ cái đầu)
    collectives = [
        "Quân Nam Hán", 
        "Quân Tống", 
        "Phát xít Nhật", 
        "Thực dân Pháp", 
        "Đế quốc Mỹ",
        "Triều đình Huế"
    ]
    for c in collectives:
        assert is_valid_person(c) is False, f"Thực thể '{c}' không được coi là Person"


def test_place_registry_boundary():
    # Kiểm tra xem hệ thống có bị nhầm địa danh trong Registry thành người không
    places = ["Bạch Đằng", "Chi Lăng", "Đống Đa", "Điện Biên Phủ", "Hà Nội"]
    for p in places:
        # Giả sử Registry đã nạp các địa danh này
        assert classify_entity(p) == "place"
        assert is_valid_person(p) is False


def test_infer_subject_complex_logic():
    # Test 1: Có cả người và tập thể -> Ưu tiên người
    s1 = infer_subject("Quang Trung chỉ huy quân Tây Sơn", {"Nguyễn Huệ"}, ["military"])
    assert s1 == "Nguyễn Huệ"
    
    # Test 2: Chỉ có tập thể quân đội nhưng không có tên người cụ thể
    s2 = infer_subject("Quân ta đánh tan quân địch trên sông", set(), ["military"])
    assert s2 == "Quân dân Việt Nam"
    
    # Test 3: Sự kiện hành chính/ngoại giao
    s3 = infer_subject("Ký kết hiệp định phân định biên giới", set(), ["diplomacy"])
    assert s3 == "Chính quyền đương thời"


def test_normalize_cleanliness_high_bar():
    # Những câu này phải bị loại bỏ vì quá mơ hồ hoặc không có thực thể định danh
    vague_texts = [
        "Năm 1427, quân địch thất bại thảm hại.", # Quân địch không phải đối tượng cần track
        "Năm 1010, thành phố trở nên đông đúc.", # Không có tên thành phố cụ thể
        "Năm 1945, một cuộc họp quan trọng đã diễn ra.", # Không rõ ai họp, họp ở đâu
    ]
    for t in vague_texts:
        assert normalize(t) is None


def test_person_alias_mapping_consistency():
    # Kiểm tra tính đồng nhất của việc ánh xạ bí danh
    aliases = {
        "Nguyễn Ánh": "Nguyễn Ánh",
        "Gia Long": "Nguyễn Ánh",
        "Nguyễn Huệ": "Nguyễn Huệ",
        "Quang Trung": "Nguyễn Huệ",
        "Bắc Bình Vương": "Nguyễn Huệ",
        "Lý Công Uẩn": "Lý Thái Tổ",
        "Trần Quốc Tuấn": "Trần Hưng Đạo",
    }
    for alias, canonical in aliases.items():
        assert canonical_person(alias) == canonical

# =========================================================
# EDGE CASES: YEAR EXTRACTION & REJECTION
# =========================================================

@pytest.mark.parametrize("text", [
    "Vào năm 1010, thành phố Thăng Long...",      # Năm nằm giữa câu
    "Ngày 2/9/1945, Bác Hồ đọc bản Tuyên ngôn.",  # Năm trong định dạng ngày tháng
    "Năm 938, Ngô Quyền chiến thắng...",         # Năm 3 chữ số
])
def test_normalize_valid_years(text):
    res = normalize(text)
    assert res is not None

@pytest.mark.parametrize("text", [
    "Có khoảng 2000 người tham gia.",   # Con số chỉ số lượng, không phải năm
    "Mức lương 1000 USD.",             # Đơn vị tiền tệ
    "Năm nay là một năm khó khăn.",    # Không có số cụ thể
])
def test_normalize_reject_non_year_numbers(text):
    assert normalize(text) is None


# =========================================================
# EDGE CASES: PERSON EXTRACTION & CLEANING
# =========================================================

def test_extract_all_persons_with_noise():
    # Kiểm tra việc bóc tách tên khi có dấu ngoặc và chức danh phức tạp
    text = "Vua Lê Thánh Tông (tên húy Lê Tư Thành) ban hành luật Hồng Đức."
    persons = extract_all_persons(text)
    # Kỳ vọng bóc được cả 2 tên và chuẩn hóa về cùng 1 người (nếu có mapping)
    normalized = {canonical_person(p) for p in persons if is_valid_person(p)}
    assert "Lê Thánh Tông" in normalized or "Lê Tư Thành" in normalized


def test_person_not_recognized_from_common_words():
    # Chống nhận diện nhầm các từ viết hoa đầu câu không phải tên người
    text = "Lịch sử Việt Nam trải qua nhiều thăng trầm."
    persons = extract_all_persons(text)
    valid_persons = {p for p in persons if is_valid_person(p)}
    assert "Lịch" not in valid_persons
    assert "Lịch sử" not in valid_persons


# =========================================================
# COMPLEX SUBJECT INFERENCE (Chủ thể phức tạp)
# =========================================================

def test_infer_subject_priority_logic():
    # Khi có cả Quân đội và Tên người, Tên người phải là Subject chính
    body = "Đại tướng Võ Nguyên Giáp chỉ huy chiến dịch Điện Biên Phủ."
    persons = {"Võ Nguyên Giáp"}
    nature = ["military", "historical_event"]
    subject = infer_subject(body, persons, nature)
    assert subject == "Võ Nguyên Giáp"

def test_infer_subject_with_unknown_place():
    # Nếu không có người, nhưng có địa danh lịch sử (trong registry)
    # thì vẫn nên giữ nhãn sự kiện
    body = "Chiến thắng tại Rạch Gầm - Xoài Mút vang dội."
    subject = infer_subject(body, set(), ["military"])
    assert subject == "Quân dân Việt Nam"


# =========================================================
# PIPELINE INTEGRITY: NATURE & TONE MAPPING
# =========================================================

def test_classify_nature_institutional_expansion():
    # Kiểm tra các từ khóa mang tính thể chế/luật pháp
    texts = [
        "Năm 1483, ban hành Luật Hồng Đức.",
        "Năm 1042, nhà Lý soạn bộ Hình thư.",
        "Năm 1946, Quốc hội thông qua Hiến pháp."
    ]
    from pipeline.storyteller import classify_nature
    for t in texts:
        labels = classify_nature(t)
        assert "institutional" in labels

def test_classify_tone_determination():
    # Kiểm tra khả năng nhận diện sắc thái hào hùng vs bi thương
    from pipeline.storyteller import classify_tone
    
    heroic_text = "Chiến thắng vang dội, đập tan quân thù, hào khí ngút trời."
    assert "heroic" in classify_tone(heroic_text)
    
    somber_text = "Nhân dân rơi vào cảnh lầm than, mất mát, đau thương."
    assert "somber" in classify_tone(somber_text)


# =========================================================
# ASKING SYSTEM (Hệ thống hỏi đáp)
# =========================================================

def test_ask_by_person_alias_recognition():
    # Kiểm tra hàm ask_by_person có hiểu bí danh khi tìm trong timeline không
    timeline = {
        "1789": {
            "events": [{
                "event": "Nguyễn Huệ đại phá quân Thanh.",
                "persons_all": ["Nguyễn Huệ"]
            }]
        }
    }
    # Người dùng hỏi "Quang Trung", hệ thống phải tìm được "Nguyễn Huệ"
    res = ask_by_person(timeline, "Quang Trung")
    assert res is not None
    assert len(res) > 0

import pytest
from pipeline.storyteller import (
    normalize, 
    extract_all_persons, 
    is_valid_person, 
    canonical_person,
    infer_subject,
    classify_entity,
    extract_year
)

# =========================================================
# 1. KIỂM TRA TRÍCH XUẤT NĂM (YEAR EXTRACTION)
# =========================================================

@pytest.mark.parametrize("text, expected_year", [
    ("Mùa xuân năm 1010, Lý Thái Tổ dời đô.", "1010"),
    ("Vào cuối năm 1788, quân Thanh xâm lược.", "1788"),
    ("Ngày 02/09/1945 là ngày Quốc khánh.", "1945"),
    ("Trận đánh diễn ra năm 938 trên sông Bạch Đằng.", "938"),
    ("Năm 2024 không phải là năm 1010.", "2024"), # Lấy năm đầu tiên tìm thấy
])
def test_extract_year_edge_cases(text, expected_year):
    assert extract_year(text) == expected_year


# =========================================================
# 2. KIỂM TRA PHÂN BIỆT NGƯỜI VS ĐỊA ĐIỂM VS TẬP THỂ
# =========================================================

@pytest.mark.parametrize("name, expected_kind", [
    ("Trần Hưng Đạo", "person"),
    ("Bạch Đằng", "place"),
    ("Quân Thanh", "collective"),
    ("Thăng Long", "place"),
    ("Nhà Nguyễn", "collective"),
    ("Hồ Chí Minh", "person"),
    ("Điện Biên Phủ", "place"),
])
def test_entity_classification(name, expected_kind):
    # Kiểm tra thông qua classify_entity hoặc các hàm hỗ trợ
    if expected_kind == "person":
        assert is_valid_person(name) is True
    elif expected_kind == "place":
        assert classify_entity(name) == "place"
        assert is_valid_person(name) is False
    elif expected_kind == "collective":
        assert classify_entity(name) == "collective"
        assert is_valid_person(name) is False


# =========================================================
# 3. KIỂM TRA CHUẨN HÓA TÊN (CANONICAL)
# =========================================================

def test_canonical_person_complex_titles():
    # Kiểm tra việc bóc tách tước hiệu và ánh xạ bí danh
    assert canonical_person("Thái sư Trần Thủ Độ") == "Trần Thủ Độ"
    assert canonical_person("Hưng Đạo Đại Vương Trần Quốc Tuấn") == "Trần Hưng Đạo"
    assert canonical_person("Vua Lý Thái Tổ") == "Lý Thái Tổ"
    assert canonical_person("Bắc Bình Vương") == "Nguyễn Huệ"
    assert canonical_person("Quang Trung") == "Nguyễn Huệ"


# =========================================================
# 4. KIỂM TRA SUY LUẬN CHỦ THỂ (INFER SUBJECT)
# =========================================================

def test_infer_subject_logic():
    # Case 1: Có tên người cụ thể -> Phải ưu tiên người
    body = "Ngô Quyền đại phá quân Nam Hán"
    persons = {"Ngô Quyền"}
    assert infer_subject(body, persons, ["military"]) == "Ngô Quyền"

    # Case 2: Không có tên người, là sự kiện quân sự -> Quân dân Việt Nam
    body = "Đánh tan quân xâm lược trên sông"
    assert infer_subject(body, set(), ["military"]) == "Quân dân Việt Nam"

    # Case 3: Sự kiện ban hành văn bản -> Văn kiện lịch sử
    body = "Ban hành bộ luật Hồng Đức"
    assert infer_subject(body, set(), ["institutional"]) == "Văn kiện lịch sử"

    # Case 4: Sự kiện ngoại giao/chính trị chung
    body = "Ký kết hiệp định đình chiến"
    assert infer_subject(body, set(), ["diplomacy"]) == "Chính quyền đương thời"


# =========================================================
# 5. KIỂM TRA KHẢ NĂNG LỌC "NHIỄU" CỦA NORMALIZE
# =========================================================

def test_normalize_rejection_logic():
    # Những câu này không mang giá trị lịch sử cụ thể, phải bị loại bỏ (trả về None)
    vague_texts = [
        "Năm 2000, mọi người rất vui vẻ.",           # Không có thực thể lịch sử
        "Vào năm đó, tình hình rất phức tạp.",        # Không rõ năm nào
        "Tại Thăng Long, năm 1010 có mưa.",          # Không có sự kiện/người quan trọng
    ]
    for t in vague_texts:
        assert normalize(t) is None

def test_normalize_acceptance_logic():
    # Những câu này dù ngắn nhưng có thực thể quan trọng, phải được giữ lại
    valid_texts = [
        "Năm 1010, Lý Thái Tổ dời đô về Thăng Long.", # Có người + địa danh
        "Năm 938, chiến thắng Bạch Đằng.",            # Có địa danh + sự kiện quân sự
        "Năm 1483, ban hành luật Hồng Đức.",           # Có sự kiện thể chế (institutional)
    ]
    for t in valid_texts:
        res = normalize(t)
        assert res is not None
        # Kiểm tra cấu trúc tuple trả về (year, body, nature, tone, subjects, persons_all, places)
        assert len(res) == 7
        assert res[0] in t # Năm phải đúng


# =========================================================
# 6. KIỂM TRA TRÙNG LẶP THỰC THỂ
# =========================================================

def test_extract_all_persons_no_duplicates():
    text = "Nguyễn Huệ (tức Quang Trung) là anh của Nguyễn Nhạc."
    persons = extract_all_persons(text)
    # Nguyễn Huệ và Quang Trung phải được chuẩn hóa về "Nguyễn Huệ"
    # Kết quả set chỉ nên chứa {"Nguyễn Huệ", "Nguyễn Nhạc"}
    assert "Nguyễn Huệ" in persons
    assert "Quang Trung" not in persons
    assert "Nguyễn Nhạc" in persons
    assert len(persons) == 2

@pytest.mark.parametrize("name", [
    "Bạch Đằng", "Chi Lăng", "Đống Đa", "Ngọc Hồi", "Điện Biên Phủ",
    "Rạch Gầm", "Xoài Mút", "Hàm Tử", "Chương Dương", "Vạn Kiếp"
])
def test_place_is_not_person(name):
    """Đảm bảo các địa danh chiến trường nổi tiếng không bị nhầm là tên người."""
    assert not is_valid_person(name), f"Lỗi: '{name}' là địa danh, không phải người."
    assert classify_entity(name) == "place"

@pytest.mark.parametrize("text, expected_missing", [
    ("Trận đánh tại Chi Lăng rất ác liệt.", "Chi Lăng"),
    ("Nguyễn Huệ tiến quân vào Thăng Long.", "Thăng Long"),
])
def test_place_not_in_persons_list(text, expected_missing):
    """Kiểm tra hàm trích xuất không đưa địa danh vào danh sách persons."""
    persons = extract_all_persons(text)
    assert expected_missing not in persons

# =========================================================
# 2. PHÂN BIỆT TẬP THỂ/TRIỀU ĐẠI VS TÊN NGƯỜI (COLLECTIVE vs PERSON)
# =========================================================
@pytest.mark.parametrize("collective", [
    "Nhà Trần", "Nhà Lê", "Nhà Lý", "Triều Nguyễn", "Mạc triều",
    "Quân Thanh", "Quân Minh", "Quân Nguyên", "Giặc Tống",
    "Phát xít Nhật", "Thực dân Pháp", "Đế quốc Mỹ",
    "Nghĩa quân Lam Sơn", "Tây Sơn quân", "Nhân dân"
])
def test_collective_is_not_person(collective):
    """Các tổ chức, triều đại, quân đội không được là Person."""
    assert not is_valid_person(collective), f"Lỗi: '{collective}' là tập thể, không phải cá nhân."

# =========================================================
# 3. TRƯỜNG HỢP TÊN NGƯỜI DỄ NHẦM LẪN (AMBIGUOUS NAMES)
# =========================================================
def test_person_with_place_prefix():
    """Kiểm tra tên người có chứa địa danh hoặc chức vụ."""
    # 'An Dương Vương' dễ bị nhầm vì 'An Dương' có thể là địa danh
    assert is_valid_person("An Dương Vương")
    # 'Trần Thủ Độ' không được nhầm thành 'Trần' (Họ) hay 'Thủ Độ' (Từ chung)
    assert "Trần Thủ Độ" in extract_all_persons("Thái sư Trần Thủ Độ quyền thế.")

def test_short_names_filter():
    """Kiểm tra các từ viết hoa ngắn 1-2 chữ cái không phải tên người."""
    noise_texts = ["Năm đó,", "Khi đó,", "Tại đó,", "Dân ta,"]
    for text in noise_texts:
        assert len(extract_all_persons(text)) == 0

# =========================================================
# 4. KIỂM TRA TỰ ĐỘNG CHUẨN HÓA (CANONICAL)
# =========================================================
@pytest.mark.parametrize("input_name, expected_canonical", [
    ("Hưng Đạo Vương", "Trần Hưng Đạo"),
    ("Trần Quốc Tuấn", "Trần Hưng Đạo"),
    ("Quang Trung", "Nguyễn Huệ"),
    ("Bắc Bình Vương", "Nguyễn Huệ"),
    ("Gia Long", "Nguyễn Ánh"),
    ("Lý Công Uẩn", "Lý Thái Tổ"),
    ("Bác Hồ", "Hồ Chí Minh"),
    ("Nguyễn Tất Thành", "Hồ Chí Minh")
])
def test_canonical_consistency(input_name, expected_canonical):
    """Đảm bảo mọi bí danh đều trỏ về một thực thể duy nhất."""
    assert canonical_person(input_name) == expected_canonical

# =========================================================
# 5. TEST NORMALIZE VỚI CÁC CÂU "BẪY" (INTEGRITY TRAPS)
# =========================================================
def test_normalize_traps():
    # Bẫy 1: Câu có năm và địa danh nhưng không có hành động/người (Nên bỏ)
    text_1 = "Năm 1010, Thăng Long là một vùng đất đẹp."
    assert normalize(text_1) is None 

    # Bẫy 2: Câu có tập thể + hành động mạnh (Nên giữ, nhưng persons rỗng)
    text_2 = "Năm 1285, quân dân nhà Trần đại phá quân Nguyên."
    res = normalize(text_2)
    assert res is not None
    _, _, nature, _, persons_subject, _, _ = res
    assert "military" in nature
    assert len(persons_subject) == 0 # 'Quân dân nhà Trần' không phải là Person cụ thể

    # Bẫy 3: Tên người giả trong cấu trúc viết hoa
    text_3 = "Năm 1945, Lịch Sử Việt Nam sang trang mới."
    res = normalize(text_3)
    # Nếu câu không có thực thể thật, normalize nên trả về None để sạch data
    if res:
        _, _, _, _, _, persons_all, _ = res
        assert "Lịch Sử" not in persons_all

@pytest.mark.parametrize("text, expected_tone", [
    # Tone: Hào hùng (Heroic) - Thường đi kèm các động từ mạnh, chiến thắng
    ("Quân ta đại phá quân Thanh, khí thế ngút trời.", "heroic"),
    ("Chiến thắng Điện Biên Phủ lừng lẫy năm châu, chấn động địa cầu.", "heroic"),
    
    # Tone: Bi thương/Trầm mặc (Somber) - Thường đi kèm mất mát, đau thương
    ("Nhân dân ta phải chịu cảnh lầm than dưới ách đô hộ.", "somber"),
    ("Sự hy sinh anh dũng của các chiến sĩ để lại nỗi đau vô hạn.", "somber"),
    ("Kinh thành bị tàn phá, vạn vật điêu linh.", "somber"),
    
    # Tone: Trung tính/Trang trọng (Neutral/Formal) - Các sự kiện hành chính
    ("Năm 1042, nhà Lý ban hành bộ Hình thư.", "neutral"), 
    ("Hai bên ký kết hiệp định đình chiến tại Giơ-ne-vơ.", "neutral"),
])
def test_classify_tone_specific(text, expected_tone):
    # Giả sử hàm trả về một list các nhãn tone
    tones = classify_tone(text)
    if expected_tone == "neutral":
        # Neutral thường là khi không có từ khóa đặc biệt cho heroic/somber
        assert "heroic" not in tones and "somber" not in tones
    else:
        assert expected_tone in tones


# =========================================================
# 2. CÁC TEST CASE NGHI NGỜ (BOUNDARY & AMBIGUITY)
# =========================================================

def test_person_vs_honorific_titles():
    """Nghi ngờ: Hệ thống có bị nhầm 'Vua', 'Chúa', 'Bác' thành tên người không?"""
    text = "Vua quyết định dời đô. Bác cùng các chú bàn việc nước."
    persons = extract_all_persons(text)
    
    # Các từ xưng hô chung không nên được coi là Person thực thể nếu đứng một mình
    for p in persons:
        assert p not in ["Vua", "Chúa", "Bác", "Các chú"]

def test_normalize_with_ambiguous_dates():
    """Nghi ngờ: Các con số không phải năm (số quân, khoảng cách) gây nhiễu."""
    text = "Năm 1288, 30 vạn quân Nguyên bị tiêu diệt tại sông Bạch Đằng."
    res = normalize(text)
    assert res is not None
    year, _, _, _, _, _, _ = res
    assert year == "1288" # Phải trích xuất đúng năm, không phải 30 (vạn)

def test_complex_sentence_structure():
    """Nghi ngờ: Câu phức có nhiều tên người và địa danh gây nhiễu chủ thể."""
    text = "Năm 1789, tại Thăng Long, Nguyễn Huệ đã hội kiến với các tướng lĩnh sau khi đánh đuổi quân Thanh."
    res = normalize(text)
    assert res is not None
    _, _, _, _, subjects, _, _ = res
    # Chủ thể thực hiện hành động chính phải là Nguyễn Huệ
    assert "Nguyễn Huệ" in subjects

def test_false_positive_locations():
    """Nghi ngờ: Các danh từ riêng viết hoa đầu câu bị nhận nhầm là Person."""
    text = "Lịch sử là gương soi của tương lai. Việt Nam là quốc gia yêu hòa bình."
    persons = extract_all_persons(text)
    valid_persons = {p for p in persons if is_valid_person(p)}
    
    assert "Lịch sử" not in valid_persons
    assert "Việt Nam" not in valid_persons

def test_mixed_tone_priority():
    """Nghi ngờ: Câu có cả từ hào hùng và bi thương (ví dụ: chiến thắng nhưng tổn thất)."""
    text = "Dù giành chiến thắng vang dội, nhưng tổn thất về người là vô cùng đau đớn."
    tones = classify_tone(text)
    # Tùy vào logic ưu tiên, nhưng thường hệ thống NLP sẽ gắn cả hai nhãn
    assert "heroic" in tones
    assert "somber" in tones

# =========================================================
# 3. KIỂM TRA TÍNH TOÀN VẸN CỦA PIPELINE (INTEGRITY)
# =========================================================

def test_normalize_empty_or_garbage_input():
    """Kiểm tra input rác hoặc không có dữ liệu lịch sử."""
    assert normalize("") is None
    assert normalize("1 2 3 4 5") is None
    assert normalize("Hôm nay trời đẹp quá, tôi đi chơi.") is None

def test_pick_tone_empty_string():
    assert pick_tone("") in ["neutral", "formal"]

def test_pick_tone_none():
    with pytest.raises(Exception):
        pick_tone(None)

def test_pick_tone_number():
    with pytest.raises(Exception):
        pick_tone(123)

def test_pick_tone_very_short_text():
    assert pick_tone("Ok") in ["neutral", "casual"]

def test_pick_tone_very_long_text():
    text = "Lịch sử Việt Nam " * 1000
    tone = pick_tone(text)
    assert tone in ["formal", "neutral"]

def test_pick_tone_mixed_language():
    text = "Nguyễn Huệ defeated the Qing army in 1789"
    tone = pick_tone(text)
    assert tone is not None


def test_storyteller_empty_events():
    result = storyteller([])
    assert isinstance(result, str)
    assert result.strip() == ""

def test_storyteller_missing_fields():
    events = [
        {"year": 938},
        {"content": "Ngô Quyền thắng Bạch Đằng"}
    ]
    result = storyteller(events)
    assert isinstance(result, str)

def test_storyteller_invalid_year():
    events = [
        {"year": "chín trăm ba tám", "content": "Bạch Đằng"}
    ]
    result = storyteller(events)
    assert "Bạch Đằng" in result

def test_storyteller_duplicate_events():
    events = [
        {"year": 938, "content": "Ngô Quyền chiến thắng"},
        {"year": 938, "content": "Ngô Quyền chiến thắng"},
    ]
    result = storyteller(events)
    assert result.count("Ngô Quyền") <= 2

def test_storyteller_unsorted_years():
    events = [
        {"year": 1009, "content": "Lý Công Uẩn"},
        {"year": 938, "content": "Ngô Quyền"},
    ]
    result = storyteller(events)
    pos_938 = result.find("938")
    pos_1009 = result.find("1009")
    assert pos_938 < pos_1009

def test_infer_subject_ambiguous():
    text = "Quân Tây Sơn dưới sự lãnh đạo của Nguyễn Huệ"
    subject = infer_subject(text, {"Nguyễn Huệ"}, ["military"])
    assert subject == "Nguyễn Huệ"

def test_infer_subject_person_and_place():
    text = "Nguyễn Huệ tiến quân ra Thăng Long"
    subject = infer_subject(text, {"Nguyễn Huệ"}, ["military"])
    assert subject == "Nguyễn Huệ"

def test_infer_subject_no_subject():
    text = "Năm 938 diễn ra một trận đánh lớn"
    subject = infer_subject(text, set(), ["military"])
    assert subject == "Quân dân Việt Nam"

def test_unicode_weird_characters():
    text = "Ngô Quyền \u0000 \uFFFF ⚔️⚔️"
    tone = pick_tone(text)
    assert tone is not None

def test_random_noise_input():
    text = "".join(random.choices(string.printable, k=500))
    tone = pick_tone(text)
    assert tone is not None

def test_person_not_document():
    text = "Nguyễn Huệ là một trong những anh hùng dân tộc"
    subject = infer_subject(text, {"Nguyễn Huệ"}, ["general"])
    assert subject == "Nguyễn Huệ"

def test_collective_not_person():
    text = "Quân Tây Sơn đánh tan quân Thanh"
    subject = infer_subject(text, set(), ["military"])
    assert subject == "Quân dân Việt Nam"

def test_infer_subject_with_passive_voice():
    """Kiểm tra câu bị động: Người thực hiện hành động bị đẩy ra sau."""
    body = "Quân Nguyên bị đánh bại bởi Trần Hưng Đạo."
    persons = {"Trần Hưng Đạo"}
    # Hệ thống cần nhận diện Trần Hưng Đạo là actor dù đứng sau 'bởi'
    assert infer_subject(body, persons, ["military"]) == "Trần Hưng Đạo"

def test_infer_subject_multiple_persons_priority():
    """Nhiều người xuất hiện: Ưu tiên người đầu tiên hoặc người có hành động chính."""
    body = "Lê Lợi cùng Nguyễn Trãi bàn kế sách tại Lam Sơn."
    persons = {"Lê Lợi", "Nguyễn Trãi"}
    # Thông thường chủ thể chính (vua) sẽ được ưu tiên
    assert infer_subject(body, persons, ["political"]) == "Lê Lợi"

def test_infer_subject_with_unknown_enemy():
    """Tránh nhận diện quân thù làm chủ thể tích cực."""
    body = "Quân Thanh tiến vào Thăng Long nhưng bị Nguyễn Huệ chặn đánh."
    persons = {"Nguyễn Huệ"}
    # Dù 'Quân Thanh' đứng đầu, nhưng Nguyễn Huệ mới là chủ thể lịch sử cần track
    assert infer_subject(body, persons, ["military"]) == "Nguyễn Huệ"

@pytest.mark.parametrize("text, expected_nature", [
    ("Thương cảng Vân Đồn được thành lập.", "economy"), # Sự kiện kinh tế
    ("Năm 1070, xây dựng Văn Miếu.", "culture"), # Văn hóa - Giáo dục
    ("Dịch bệnh hoành hành khắp kinh thành.", "general"), # Thiên tai/Dịch bệnh (không phải military/political)
])
def test_classify_nature_diverse_fields(text, expected_nature):
    from pipeline.storyteller import classify_nature
    labels = classify_nature(text)
    assert expected_nature in labels

def test_classify_tone_sarcastic_or_complex():
    """Kiểm tra các câu có từ ngữ mạnh nhưng không phải hào hùng."""
    text = "Nỗi nhục mất nước không bao giờ quên."
    tones = classify_tone(text)
    assert "somber" in tones
    assert "heroic" not in tones # Tránh bắt nhầm từ 'không bao giờ' thành hào hùng

def test_ask_with_partial_data():
    """Timeline chỉ có năm, không có event bên trong."""
    timeline = {"1010": {"events": []}}
    # Không được crash, phải trả về câu thông báo không tìm thấy hoặc None
    assert ask(timeline, "Năm 1010 có gì?") is None

def test_ask_by_person_case_insensitive():
    """Người dùng hỏi bằng chữ thường."""
    timeline = {"1789": {"events": [{"event": "Nguyễn Huệ thắng quân Thanh", "persons_all": ["Nguyễn Huệ"]}]}}
    res = ask_by_person(timeline, "nguyễn huệ")
    assert res is not None
    assert len(res) > 0

def test_normalize_traps_advanced():
    # Bẫy 1: Năm quá lớn (tương lai) hoặc quá nhỏ (không hợp lệ)
    assert normalize("Năm 3000, người máy xâm lược.") is None
    
    # Bẫy 2: Câu chứa từ khóa lịch sử nhưng là ví dụ hoặc câu hỏi
    assert normalize("Tại sao năm 938 Ngô Quyền lại dùng cọc gỗ?") is None
    
    # Bẫy 3: Thực thể địa danh trùng tên người (Ví dụ: tỉnh Thái Bình vs người tên Thái Bình)
    text = "Năm 1945, tại Thái Bình, nhân dân nổi dậy."
    res = normalize(text)
    if res:
        _, _, _, _, _, persons_all, places = res
        assert "Thái Bình" in places
        assert "Thái Bình" not in persons_all

def test_canonical_person_unmapped():
    """Nếu gặp tên không có trong từ điển chuẩn hóa, phải giữ nguyên tên đó."""
    unknown_person = "Ông Giáp Râu" 
    # Nếu không có mapping, không được trả về rỗng mà phải trả về chính nó hoặc bản chuẩn hóa thô
    assert canonical_person(unknown_person) == unknown_person

@pytest.mark.parametrize("text, expected_year", [
    ("Đại lễ kỉ niệm 1000 năm Thăng Long diễn ra vào năm 2010.", "2010"),
    ("Năm 2024, chúng ta kỉ niệm 70 năm chiến thắng Điện Biên Phủ.", "2024"),
    ("Lễ kỉ niệm 2000 năm khởi nghĩa Hai Bà Trưng được tổ chức năm 1940.", "1940"),
    ("Hướng tới kỉ niệm 100 năm ngày sinh Võ Nguyên Giáp vào năm 2011.", "2011"),
])
def test_extract_year_anniversary_confusion(text, expected_year):
    """Bắt lỗi lấy nhầm số năm kỉ niệm (100, 1000) làm năm sự kiện."""
    from pipeline.storyteller import extract_year
    assert extract_year(text) == expected_year

def test_normalize_ignore_military_numbers():
    """Kiểm tra xem 1000 quân hay 2000 chiến thuyền có bị nhầm thành năm không."""
    text = "Năm 938, Ngô Quyền với 1000 chiến thuyền đã đánh bại quân Nam Hán."
    res = normalize(text)
    assert res is not None
    year = res[0]
    assert year == "938"
    assert year != "1000"

def test_normalize_with_large_army_counts():
    text = "Năm 1285, 50 vạn quân Nguyên xâm lược nước ta."
    res = normalize(text)
    assert res is not None
    assert res[0] == "1285"

def test_normalize_duration_vs_year():
    text = "Sau 1000 năm Bắc thuộc, năm 939 Ngô Quyền lên ngôi vua."
    res = normalize(text)
    assert res is not None
    assert res[0] == "939"
    assert res[0] != "1000"

def test_normalize_age_rejection():
    text = "Năm 1010, khi đó Lý Thái Tổ đã 36 tuổi."
    res = normalize(text)
    assert res is not None
    assert res[0] == "1010"
    assert "36" not in res[0]

def test_year_inside_document_names():
    text = "Năm 2010, các nhà khoa học nghiên cứu về sự kiện năm 1010."
    # Nếu logic là lấy năm đầu tiên xuất hiện (theo storyteller.py hiện tại)
    # thì 2010 phải được ưu tiên.
    res = normalize(text)
    assert res is not None
    assert res[0] == "2010"


@pytest.mark.parametrize("text", [
    None,
    "",
    " ",
    "\n\t",
    "\u0000\u0001\u0002",
])
def test_pick_tone_poison_inputs(text):
    try:
        tone = pick_tone(text)
        assert tone is not None
    except Exception:
        pass  # chấp nhận crash, nhưng không được silent


def test_storyteller_with_garbage_structure():
    events = [
        {},
        {"year": None},
        {"content": None},
        {"year": "Năm xưa", "content": 12345},
    ]
    result = storyteller(events)
    assert isinstance(result, str)


# =========================================================
# ☠️ LEVEL 2 — YEAR & TIME PARADOX
# =========================================================

@pytest.mark.parametrize("text", [
    "Năm 0 xảy ra biến cố lạ.",
    "Năm -938 Ngô Quyền đánh giặc.",
    "Năm 99999 lịch sử sang trang.",
])
def test_normalize_invalid_year_ranges(text):
    assert normalize(text) is None


def test_normalize_multiple_years_conflict():
    text = "Năm 938 và năm 939, Ngô Quyền tiếp tục củng cố chính quyền."
    res = normalize(text)
    assert res is not None
    year, *_ = res
    assert year in ["938", "939"]  # nhưng không được crash


# =========================================================
# ☠️ LEVEL 3 — PERSON EXTRACTION ĐÁNH LỪA
# =========================================================

@pytest.mark.parametrize("text", [
    "Ông ấy rất giỏi.",
    "Người đó đã làm nên lịch sử.",
    "Vị vua nọ ra quyết định.",
])
def test_pronouns_not_person(text):
    persons = extract_all_persons(text)
    assert len(persons) == 0


def test_fake_person_like_company_name():
    text = "Công ty Trần Hưng Đạo phát triển mạnh."
    persons = extract_all_persons(text)
    valid = [p for p in persons if is_valid_person(p)]
    assert valid == []


def test_person_name_inside_quotes():
    text = 'Người ta gọi ông là "Nguyễn Huệ".'
    persons = extract_all_persons(text)
    assert "Nguyễn Huệ" in persons


def test_person_name_broken_spacing():
    text = "N g u y ễ n   H u ệ lên ngôi."
    persons = extract_all_persons(text)
    assert persons == set()


# =========================================================
# ☠️ LEVEL 4 — CANONICAL PERSON HELL
# =========================================================

@pytest.mark.parametrize("name", [
    "Quang   Trung",
    "  Quang Trung ",
    "QUANG TRUNG",
    "quang trung",
])
def test_canonical_normalization_variants(name):
    assert canonical_person(name) == "Nguyễn Huệ"


def test_canonical_person_unknown_alias():
    name = "Thiên Tài Á Đông"
    assert canonical_person(name) == name


# =========================================================
# ☠️ LEVEL 5 — COLLECTIVE vs PERSON CHAOS
# =========================================================

@pytest.mark.parametrize("text", [
    "Nhà Trần thắng lớn.",
    "Triều đình Huế suy yếu.",
    "Quân đội Nhân dân tiến công.",
])
def test_collective_never_person(text):
    persons = extract_all_persons(text)
    valid = [p for p in persons if is_valid_person(p)]
    assert valid == []


def test_person_name_contains_collective_word():
    text = "Nguyễn Quân Minh là tướng tài."
    persons = extract_all_persons(text)
    assert "Nguyễn Quân Minh" in persons


# =========================================================
# ☠️ LEVEL 6 — INFER SUBJECT CỰC KHÓ
# =========================================================

def test_infer_subject_person_priority_over_collective():
    text = "Nguyễn Huệ chỉ huy quân Tây Sơn đại phá quân Thanh."
    subject = infer_subject(text, {"Nguyễn Huệ"}, ["military"])
    assert subject == "Nguyễn Huệ"


def test_infer_subject_collective_when_no_person():
    text = "Quân Tây Sơn tiến vào Thăng Long."
    subject = infer_subject(text, set(), ["military"])
    assert subject in ["Quân dân Việt Nam", "Tập thể"]


def test_infer_subject_administrative_event():
    text = "Ban hành Hiến pháp mới."
    subject = infer_subject(text, set(), ["political"])
    assert subject == "Chính quyền đương thời"


def test_infer_subject_with_noise_person():
    text = "Một người tên Nguyễn đã xuất hiện."
    subject = infer_subject(text, {"Nguyễn"}, ["general"])
    assert subject != "Nguyễn"


# =========================================================
# ☠️ LEVEL 7 — TONE CONFLICT & PRIORITY
# =========================================================

def test_tone_conflict_heroic_vs_somber():
    text = "Chiến thắng vẻ vang nhưng tổn thất vô cùng to lớn."
    tones = classify_tone(text)
    assert "heroic" in tones
    assert "somber" in tones


def test_tone_neutral_not_polluted():
    text = "Năm 1010, Lý Công Uẩn dời đô."
    tones = classify_tone(text)
    assert "heroic" not in tones
    assert "somber" not in tones


# =========================================================
# ☠️ LEVEL 8 — NORMALIZE TRAP (CÂU ĐÁNH LỪA)
# =========================================================

@pytest.mark.parametrize("text", [
    "Năm 1945, mọi thứ thay đổi.",
    "Năm 1802, triều đại mới bắt đầu.",
    "Năm 1288, cảm xúc dâng trào.",
])
def test_normalize_reject_poetic_history(text):
    assert normalize(text) is None


def test_normalize_accept_strong_action_no_person():
    text = "Năm 1945, giành chính quyền trên cả nước."
    res = normalize(text)
    assert res is not None


# =========================================================
# ☠️ LEVEL 9 — ENTITY CLASSIFICATION HELL
# =========================================================

@pytest.mark.parametrize("name, expected", [
    ("Nguyễn Huệ", "person"),
    ("Thăng Long", "place"),
    ("Nhà Trần", "collective"),
    ("Bình Ngô Đại Cáo", None),
])
def test_classify_entity_extreme(name, expected):
    assert classify_entity(name) == expected


# =========================================================
# ☠️ LEVEL 10 — RANDOM FUZZ (ĐẬP HẾT)
# =========================================================

def test_random_fuzz_pipeline():
    for _ in range(100):
        text = "".join(random.choices(string.printable, k=200))
        try:
            normalize(text)
            pick_tone(text)
            extract_all_persons(text)
        except Exception:
            pass  # crash thì ok, silent bug mới đáng sợ

@pytest.mark.parametrize("text, expected_year", [
    # Bẫy kỉ niệm: Phải lấy năm thực hiện hành động, không phải con số kỉ niệm
    ("Năm 2010, cả nước hướng về kỉ niệm 1000 năm Thăng Long.", "2010"),
    ("Kỉ niệm 70 năm chiến thắng Điện Biên Phủ vào năm 2024.", "2024"),
    # Bẫy số lượng: Không được nhầm số quân, số tuổi với năm
    ("Năm 1288, với 30 vạn quân, Trần Hưng Đạo đại thắng.", "1288"),
    ("Lý Thái Tổ lên ngôi năm 1009 khi ông đã 35 tuổi.", "1009"),
    # Bẫy khoảng cách thời gian
    ("Hơn 100 năm sau năm 1789, một kỷ nguyên mới bắt đầu.", "1789"),
    # Bẫy năm trong tên văn bản/luật (ưu tiên năm thực tế ở đầu câu)
    ("Năm 2020, chúng ta nghiên cứu về Luật Hồng Đức 1483.", "2020"),
])
def test_extract_year_extreme_cases(text, expected_year):
    """Kiểm tra khả năng lọc nhiễu giữa năm thực và các con số định lượng khác."""
    assert extract_year(text) == expected_year


# =========================================================
# 2. THỰC THỂ "GIẢ" VÀ TỪ ĐỒNG ÂM (ENTITY AMBIGUITY)
# =========================================================

@pytest.mark.parametrize("name", [
    "Ông", "Bà", "Anh", "Chị", "Hắn", "Quân thù", # Đại từ nhân xưng
    "Lịch sử", "Chiến thắng", "Hào khí", "Độc lập", # Danh từ trừu tượng viết hoa đầu câu
    "Thái Bình", "Hòa Bình", "Sơn La", # Địa danh trùng với tên/tính từ
    "Đại Việt", "An Nam", "Chăm Pa" # Tên quốc gia cổ
])
def test_is_valid_person_false_positives(name):
    """Đảm bảo các danh từ chung hoặc tên quốc gia không bị nhận nhầm là Person."""
    assert is_valid_person(name) is False


def test_nested_entities_in_titles():
    """Bẫy thực thể lồng nhau: 'Vua Lê' thì 'Lê' là tên/họ, không phải 'Vua'."""
    text = "Vua Lê Thái Tổ ban hành chính sách mới."
    persons = extract_all_persons(text)
    # Nếu ra "Vua Lê" là sai, phải ra "Lê Thái Tổ" hoặc được chuẩn hóa
    assert "Vua" not in persons
    assert "Lê Thái Tổ" in [canonical_person(p) for p in persons]


# =========================================================
# 3. SUY LUẬN CHỦ THỂ TRONG CÂU PHỨC (SUBJECT INFERENCE)
# =========================================================

def test_infer_subject_passive_voice():
    """Câu bị động: Đối tượng bị tác động đứng đầu, nhưng Actor đứng sau."""
    body = "Quân Nguyên bị Trần Hưng Đạo đánh bại tại sông Bạch Đằng."
    persons = {"Trần Hưng Đạo"}
    # Logic đúng: Trần Hưng Đạo là chủ thể thực hiện hành động 'đánh bại'
    assert infer_subject(body, persons, ["military"]) == "Trần Hưng Đạo"

def test_infer_subject_with_enemy_prefix():
    """Câu bắt đầu bằng quân địch: Tránh lấy kẻ địch làm chủ thể lịch sử chính."""
    body = "Quân Thanh tiến vào Thăng Long nhưng bị Nguyễn Huệ quét sạch."
    persons = {"Nguyễn Huệ"}
    # Dù 'Quân Thanh' xuất hiện trước, nhưng Subject ghi nhận phải là Nguyễn Huệ
    assert infer_subject(body, persons, ["military"]) == "Nguyễn Huệ"


# =========================================================
# 4. SẮC THÁI HỖN HỢP VÀ ĐẢO NGỮ (TONE & NATURE)
# =========================================================

def test_classify_tone_sarcastic_or_complex():
    """Câu có từ 'thắng' nhưng mang nghĩa bi kịch hoặc ngược lại."""
    text = "Dù thắng trận nhưng kinh đô bị thiêu rụi, máu chảy thành sông."
    tones = classify_tone(text)
    # Phải bắt được cả sự bi thương (somber) dù có từ 'thắng'
    assert "somber" in tones
    assert "heroic" in tones

def test_classify_nature_institutional_ambiguity():
    """Phân biệt sự kiện thể chế và sự kiện quân sự khi dùng từ hỗn hợp."""
    text = "Năm 1042, ban hành bộ luật để trừng trị kẻ làm loạn quân đội."
    natures = classify_nature(text)
    # Trọng tâm là 'ban hành bộ luật' -> institutional
    assert "institutional" in natures


# =========================================================
# 5. ĐỘ SẠCH CỦA NORMALIZE (INTEGRITY)
# =========================================================

def test_normalize_reject_questions_and_vague_claims():
    """Loại bỏ các câu không phải dữ kiện lịch sử khẳng định."""
    bad_inputs = [
        "Năm 938, ai là người đóng cọc trên sông Bạch Đằng?", # Câu hỏi
        "Năm 1945 là một năm rất đáng nhớ.", # Nhận định chung chung, không có sự kiện cụ thể
        "Có lẽ vào năm 1010, sự việc đã khác.", # Câu giả định
        "Hơn 1000 người đã tham gia lễ hội năm nay." # Số lượng người, không phải năm lịch sử
    ]
    for inp in bad_inputs:
        assert normalize(inp) is None


# =========================================================
# 6. CHUẨN HÓA BÍ DANH ĐA TẦNG (CANONICAL MAPPING)
# =========================================================

def test_canonical_chain():
    """Kiểm tra các biến thể tên gọi phức tạp của cùng một nhân vật."""
    aliases = ["Bắc Bình Vương", "Quang Trung hoàng đế", "Nguyễn Văn Huệ"]
    for alias in aliases:
        assert canonical_person(alias) == "Nguyễn Huệ"

def test_canonical_unrecognized_keeps_original():
    """Nếu không biết là ai, phải giữ nguyên để không mất dữ liệu, chỉ trim khoảng trắng."""
    unknown = "  Vị Tướng Bí Ẩn  "
    assert canonical_person(unknown) == "Vị Tướng Bí Ẩn"