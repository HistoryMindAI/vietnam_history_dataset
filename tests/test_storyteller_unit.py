"""
test_storyteller_unit.py - Unit tests for storyteller.py functions.

Tests:
1. Year extraction from text
2. Tone classification (heroic/somber/neutral)
3. Person validation
"""
import pytest
import sys
from pathlib import Path

# Add pipeline directory to path (portable)
PROJECT_DIR = Path(__file__).parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


class TestExtractYear:
    """Test year extraction from text."""
    
    def test_extract_year_simple(self):
        from pipeline.storyteller import extract_year
        
        result = extract_year("Năm 1945, Việt Nam giành độc lập")
        assert result == "1945"
    
    def test_extract_year_with_date(self):
        from pipeline.storyteller import extract_year
        
        result = extract_year("Ngày 2/9/1945, Bác Hồ đọc tuyên ngôn")
        assert result == "1945"
    
    def test_extract_year_no_year(self):
        from pipeline.storyteller import extract_year
        
        result = extract_year("Việt Nam là một quốc gia đẹp")
        assert result is None
    
    def test_extract_year_ancient(self):
        from pipeline.storyteller import extract_year
        
        result = extract_year("Năm 938, Ngô Quyền đánh tan quân Nam Hán")
        assert result == "938"


class TestClassifyTone:
    """Test tone classification."""
    
    def test_heroic_tone(self):
        from pipeline.storyteller import classify_tone
        
        result = classify_tone("Chiến thắng lừng lẫy Điện Biên Phủ")
        assert "heroic" in result
    
    def test_somber_tone(self):
        from pipeline.storyteller import classify_tone
        
        result = classify_tone("Đất nước bị xâm lược, nhân dân lầm than")
        assert "somber" in result or "tragic" in result
    
    def test_neutral_tone(self):
        from pipeline.storyteller import classify_tone
        
        result = classify_tone("Lý Công Uẩn dời đô về Thăng Long")
        assert isinstance(result, set)
    
    def test_heroic_by_year(self):
        from pipeline.storyteller import classify_tone
        
        # 1945 is in HEROIC_YEARS
        result = classify_tone("Sự kiện quan trọng", "1945")
        assert "heroic" in result


class TestIsValidPerson:
    """Test person validation."""
    
    def test_valid_person(self):
        from pipeline.storyteller import is_valid_person
        
        assert is_valid_person("Nguyễn Tất Thành") == True
        assert is_valid_person("Hồ Chí Minh") == True
    
    def test_invalid_short_name(self):
        from pipeline.storyteller import is_valid_person
        
        assert is_valid_person("Hà") == False
    
    def test_invalid_place(self):
        from pipeline.storyteller import is_valid_person
        
        assert is_valid_person("Thăng Long") == False
        assert is_valid_person("Điện Biên Phủ") == False
    
    def test_invalid_collective(self):
        from pipeline.storyteller import is_valid_person
        
        assert is_valid_person("Quân Thanh") == False
        assert is_valid_person("Nhà Trần") == False


class TestCanonicalPerson:
    """Test person name normalization."""
    
    def test_alias_mapping(self):
        from pipeline.storyteller import canonical_person
        
        assert canonical_person("Quang Trung") == "Nguyễn Huệ"
        assert canonical_person("Bắc Bình Vương") == "Nguyễn Huệ"
    
    def test_title_stripping(self):
        from pipeline.storyteller import canonical_person
        
        result = canonical_person("Vua Lý Thái Tổ")
        assert "Vua" not in result
    
    def test_direct_name(self):
        from pipeline.storyteller import canonical_person
        
        assert canonical_person("Trần Hưng Đạo") == "Trần Hưng Đạo"


class TestClassifyNature:
    """Test event nature classification."""
    
    def test_military_nature(self):
        from pipeline.storyteller import classify_nature
        
        result = classify_nature("Đánh bại quân xâm lược")
        assert "military" in result
    
    def test_institutional_nature(self):
        from pipeline.storyteller import classify_nature
        
        result = classify_nature("Ban hành luật Hồng Đức")
        assert "institutional" in result
    
    def test_general_nature(self):
        from pipeline.storyteller import classify_nature
        
        result = classify_nature("Một sự kiện bình thường")
        assert "general" in result
