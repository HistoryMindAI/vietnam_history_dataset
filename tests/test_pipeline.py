"""
test_pipeline.py - Unit tests for storyteller pipeline

Tests person/place extraction, entity classification, and normalization.
"""
import pytest
import sys
from pathlib import Path

# Add pipeline directory to path
PIPELINE_DIR = Path(__file__).parent.parent / "pipeline"
if str(PIPELINE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR.parent))

from pipeline.storyteller import (
    extract_all_persons,
    extract_persons_from_body,
    is_valid_person,
    canonical_person,
    classify_entity,
    infer_subject,
    normalize,
    classify_tone,
    classify_nature,
    extract_year,
)


# =========================================================
# YEAR EXTRACTION
# =========================================================

@pytest.mark.parametrize("text, expected_year", [
    ("Năm 1010, Lý Thái Tổ dời đô.", "1010"),
    ("Vào năm 1945, cách mạng thành công.", "1945"),
    ("Trận đánh năm 938 trên sông Bạch Đằng.", "938"),
])
def test_extract_year(text, expected_year):
    """Test year extraction from text."""
    assert extract_year(text) == expected_year


# =========================================================
# PERSON VS PLACE EXTRACTION
# =========================================================

def test_person_not_place():
    """Test that persons are extracted, not places."""
    text = "Trần Hưng Đạo chỉ huy quân đội tại Bạch Đằng"
    persons = extract_all_persons(text)
    
    assert "Trần Hưng Đạo" in persons
    assert "Bạch Đằng" not in persons


def test_place_not_person():
    """Test that places are not extracted as persons."""
    text = "Chiến thắng Bạch Đằng diễn ra năm 1288"
    persons = extract_all_persons(text)
    
    assert "Bạch Đằng" not in persons


def test_country_not_person():
    """Test that country names are not persons."""
    text = "Quân dân Đại Việt đánh bại quân Nguyên"
    persons = extract_all_persons(text)
    
    assert "Đại Việt" not in persons


# =========================================================
# DYNASTY / COLLECTIVE EXCLUSION
# =========================================================

@pytest.mark.parametrize("entity", [
    "Nhà Trần",
    "Nhà Lý",
    "Triều Nguyễn",
    "Quân Thanh",
    "Quân Minh",
])
def test_dynasty_not_person(entity):
    """Test that dynasties and armies are not persons."""
    assert not is_valid_person(entity)


# =========================================================
# PERSON ALIAS NORMALIZATION
# =========================================================

def test_king_alias():
    """Test alias normalization for kings."""
    assert canonical_person("Quang Trung") == "Nguyễn Huệ"
    assert canonical_person("Gia Long") == "Nguyễn Ánh"


def test_royal_title_is_person():
    """Test that royal titles are valid persons."""
    text = "Lý Thái Tổ ban Chiếu dời đô"
    persons = extract_all_persons(text)
    
    assert "Lý Thái Tổ" in persons


# =========================================================
# ENTITY CLASSIFICATION
# =========================================================

def test_classify_entity_place():
    """Test place classification."""
    assert classify_entity("Bạch Đằng") == "place"
    assert classify_entity("Thăng Long") == "place"


def test_classify_entity_person():
    """Test person classification."""
    assert classify_entity("Trần Hưng Đạo") == "person"
    assert classify_entity("Ngô Quyền") == "person"


# =========================================================
# SUBJECT INFERENCE
# =========================================================

def test_infer_subject_person():
    """Test subject inference with person."""
    body = "Trần Hưng Đạo chỉ huy quân đội"
    persons = {"Trần Hưng Đạo"}
    subject = infer_subject(body, persons, ["military"])
    
    assert subject == "Trần Hưng Đạo"


def test_infer_subject_collective():
    """Test subject inference for collective."""
    body = "quân dân đánh bại quân xâm lược"
    subject = infer_subject(body, set(), ["military"])
    
    assert subject == "Quân dân Việt Nam"


def test_infer_subject_document():
    """Test subject inference for documents."""
    body = "ban Chiếu dời đô"
    subject = infer_subject(body, set(), ["institutional"])
    
    assert subject == "Văn kiện lịch sử"


# =========================================================
# NORMALIZE FUNCTION
# =========================================================

def test_normalize_person_and_place():
    """Test normalize extracts person and place correctly."""
    text = "Năm 1288, Trần Hưng Đạo đánh bại quân Nguyên trên sông Bạch Đằng."
    
    res_list = normalize(text)
    assert res_list
    res = res_list[0]
    
    year, body, nature, tone, persons, persons_all, places, dynasty = res
    
    assert year == "1288"
    assert "Trần Hưng Đạo" in persons_all
    assert "Bạch Đằng" not in persons_all


def test_normalize_rejects_vague():
    """Test normalize rejects vague text."""
    vague_texts = [
        "Năm 1945, một thời kỳ đầy hào hùng đã bắt đầu.",
        "Năm 1802, triều đại mới có nhiều sự thay đổi.",
    ]
    for t in vague_texts:
        assert not normalize(t)


# =========================================================
# TONE AND NATURE CLASSIFICATION
# =========================================================

def test_classify_tone_heroic():
    """Test heroic tone detection."""
    text = "Chiến thắng vang dội, đập tan quân thù"
    tones = classify_tone(text)
    
    assert "heroic" in tones


def test_classify_tone_somber():
    """Test somber tone detection."""
    text = "Nhân dân rơi vào cảnh lầm than, mất mát"
    tones = classify_tone(text)
    
    assert "somber" in tones


def test_classify_nature_military():
    """Test military nature detection."""
    text = "Năm 938, Ngô Quyền đại phá quân Nam Hán"
    natures = classify_nature(text)
    
    assert "historical_event" in natures or "military" in natures


def test_classify_nature_institutional():
    """Test institutional nature detection."""
    text = "Năm 1483, ban hành Luật Hồng Đức."
    natures = classify_nature(text)
    
    assert "institutional" in natures


# =========================================================
# EDGE CASES
# =========================================================

@pytest.mark.parametrize("name", [
    "Bạch Đằng", "Chi Lăng", "Đống Đa", "Điện Biên Phủ",
])
def test_place_not_recognized_as_person(name):
    """Test that famous battle places are not persons."""
    assert not is_valid_person(name)
    assert classify_entity(name) == "place"


@pytest.mark.parametrize("text", [
    "Nhà Trần đánh bại quân Nguyên",
    "Quân Thanh tiến vào Thăng Long",
])
def test_no_false_persons(text):
    """Test that collective nouns are not persons."""
    persons = extract_all_persons(text)
    assert persons == set()
