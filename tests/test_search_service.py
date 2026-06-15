import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def clean_startup():
    """Fixture to ensure a clean state before and after tests."""
    import app.core.startup as startup
    # Save original state
    orig_documents = getattr(startup, "DOCUMENTS", [])
    orig_documents_by_year = getattr(startup, "DOCUMENTS_BY_YEAR", {})
    orig_index = getattr(startup, "index", None)
    orig_session = getattr(startup, "session", None)

    yield startup

    # Restore state
    startup.DOCUMENTS = orig_documents
    startup.DOCUMENTS_BY_YEAR = orig_documents_by_year
    startup.index = orig_index
    startup.session = orig_session

def test_search_service_dynasty(clean_startup):
    from app.services.search_service import detect_dynasty_from_query, scan_by_dynasty_timeline, scan_national_resistance, scan_territorial_conflicts, scan_civil_wars, scan_broad_history

    if not clean_startup.DYNASTY_ALIASES:
        clean_startup._load_knowledge_base()
        clean_startup._build_historical_phrases()

    assert detect_dynasty_from_query("nhà trần") == "trần" # Fix assertion

    clean_startup.DOCUMENTS = [
        {"year": 1010, "dynasty": "nhà Lý", "story": "Dời đô", "persons": [], "event": "dời đô"},
        {"year": 1288, "dynasty": "nhà Trần", "story": "Bạch Đằng", "persons": [], "event": "bạch đằng"}
    ]

    res = scan_by_dynasty_timeline()
    assert isinstance(res, list)

    res = scan_national_resistance()
    assert isinstance(res, list)

    res = scan_territorial_conflicts()
    assert isinstance(res, list)

    res = scan_civil_wars()
    assert isinstance(res, list)

    res = scan_broad_history()
    assert isinstance(res, list)

def test_semantic_search_with_mock(clean_startup):
    from app.services.search_service import semantic_search

    clean_startup.index = MagicMock()
    clean_startup.session = MagicMock()

    with patch('app.services.search_service.get_cached_embedding') as mock_embed:
        import numpy as np
        mock_embed.return_value = np.array([[0.1, 0.2]])

        clean_startup.index.search.return_value = (np.array([[0.9]]), np.array([[0]]))
        clean_startup.DOCUMENTS = [{"year": 1288, "story": "Bạch Đằng", "persons": []}]

        res = semantic_search("Bạch đằng")
        assert len(res) == 1
        assert res[0]["year"] == 1288

def test_scan_by_year_range(clean_startup):
    from app.services.search_service import scan_by_year_range

    clean_startup.DOCUMENTS_BY_YEAR = {
        1010: [{"year": 1010, "story": "A"}],
        1288: [{"year": 1288, "story": "B"}],
        1427: [{"year": 1427, "story": "C"}]
    }

    res = scan_by_year_range(1000, 1300)
    assert len(res) == 2

def test_scan_by_entities(clean_startup):
    from app.services.search_service import scan_by_entities

    clean_startup._load_knowledge_base()
    clean_startup._build_historical_phrases()

    # Needs to match the internal normalization mapping!
    clean_startup.DOCUMENTS = [
        {"year": 1010, "story": "Lý Thái Tổ dời đô", "persons": ["lý thái tổ"]},
        {"year": 1288, "story": "Trần Hưng Đạo chống quân Nguyên", "persons": ["trần hưng đạo"]}
    ]
    clean_startup._build_inverted_indexes()

    resolved = {"persons": ["lý thái tổ"]}
    res = scan_by_entities(resolved)
    assert len(res) == 1
    assert res[0]["year"] == 1010

    # Test fallback text search
    resolved = {"persons": ["ngô quyền"]}
    clean_startup.DOCUMENTS.append({"year": 938, "story": "Ngô Quyền đánh Nam Hán", "persons": [], "event": "ngô quyền"})
    res = scan_by_entities(resolved)
    assert len(res) == 1
    assert res[0]["year"] == 938

def test_check_query_relevance():
    from app.services.search_service import check_query_relevance

    doc = {"title": "Lý Thái Tổ dời đô", "dynasty": "nhà Lý"}

    # Keyword match
    assert check_query_relevance("dời đô", doc) == True
    assert check_query_relevance("không liên quan", doc) == False

    # Dynasty filter match
    assert check_query_relevance("không liên quan", doc, dynasty_filter="lý") == True

def test_dynasty_sort_key():
    from app.services.search_service import _dynasty_sort_key

    assert _dynasty_sort_key({"year": 1010})[1] == 1010
    assert int(_dynasty_sort_key({"year": "1010"})[1]) == 1010
    assert _dynasty_sort_key({})[1] == 9999

def test_semantic_search_empty_index(clean_startup):
    from app.services.search_service import semantic_search

    # Mock to trigger early return
    clean_startup.index = None
    assert semantic_search("Bạch Đằng") == []

def test_semantic_search_empty_session(clean_startup):
    from app.services.search_service import semantic_search

    # Mock to trigger early return
    clean_startup.index = MagicMock()
    clean_startup.session = None
    assert semantic_search("Bạch Đằng") == []

@patch('app.services.search_service.generate_phonetic_variants')
def test_resolve_query_entities_phonetic_fallback(mock_generate_phonetic_variants):
    from app.services.search_service import resolve_query_entities
    import app.core.startup as startup

    # Store original values
    orig_person_aliases = startup.PERSON_ALIASES.copy()
    orig_dynasty_aliases = startup.DYNASTY_ALIASES.copy()
    orig_topic_synonyms = startup.TOPIC_SYNONYMS.copy()
    orig_places_index = startup.PLACES_INDEX.copy()

    try:
        # Override to short terms to be matched
        startup.PERSON_ALIASES = {"zxy": "nguyễn chí thanh"}
        startup.DYNASTY_ALIASES = {"qwerty": "nhà trần"}
        startup.TOPIC_SYNONYMS = {"asdf": "chiến dịch"}
        startup.PLACES_INDEX = {"hjkl": [1]}

        mock_generate_phonetic_variants.return_value = ["zxy qwerty asdf hjkl", "variant2"]

        result = resolve_query_entities("querywithnotmatch")

        assert "nguyễn chí thanh" in result["persons"]
        assert "nhà trần" in result["dynasties"]
        assert "chiến dịch" in result["topics"]
        assert "hjkl" in result["places"]

        # Ensure it breaks after first variant
        mock_generate_phonetic_variants.assert_called_once()

    finally:
        startup.PERSON_ALIASES = orig_person_aliases
        startup.DYNASTY_ALIASES = orig_dynasty_aliases
        startup.TOPIC_SYNONYMS = orig_topic_synonyms
        startup.PLACES_INDEX = orig_places_index

def test_detect_place_from_query(clean_startup):
    from app.services.search_service import detect_place_from_query

    clean_startup.PLACES_INDEX = {
        "hà nội": [1, 2],
        "hải phòng": [3]
    }

    assert detect_place_from_query("tôi muốn tìm hà nội") == "hà nội"
    assert detect_place_from_query("tôi muốn tìm thái bình") is None

def test_extract_important_keywords():
    from app.services.search_service import extract_important_keywords

    assert "tôi" not in extract_important_keywords("tôi muốn tìm hà nội")
    assert "nội" in extract_important_keywords("tôi muốn tìm hà nội")

def test_scan_by_year(clean_startup):
    from app.services.search_service import scan_by_year

    clean_startup.DOCUMENTS_BY_YEAR = {
        1010: [{"year": 1010, "story": "Dời đô"}],
        1288: [{"year": 1288, "story": "Bạch Đằng"}]
    }

    assert len(scan_by_year(1010)) == 1
    assert scan_by_year(1010)[0]["story"] == "Dời đô"
    assert len(scan_by_year(9999)) == 0

def test_resolve_query_entities_dynasty_guard(clean_startup):
    from app.services.search_service import resolve_query_entities

    clean_startup.PERSON_ALIASES = {"nguyễn huệ": "nguyễn huệ"}
    clean_startup.DYNASTY_ALIASES = {"nhà nguyễn": "nguyễn"}
    clean_startup.TOPIC_SYNONYMS = {}
    clean_startup.PLACES_INDEX = {}
    clean_startup.PERSONS_INDEX = {}
    clean_startup.DYNASTY_INDEX = {}

    res = resolve_query_entities("vua nguyễn huệ nhà nguyễn")
    assert "nguyễn huệ" in res["persons"]
    assert "nguyễn" in res["dynasties"]

    # False match prevention for alias
    res = resolve_query_entities("vua nguyễn huệ")
    assert "nguyễn huệ" in res["persons"]
    assert "nguyễn" not in res["dynasties"]

@patch('app.core.startup.session')
@patch('app.core.startup.tokenizer')
def test_get_cached_embedding(mock_tokenizer, mock_session):
    from app.services.search_service import get_cached_embedding

    import numpy as np
    from unittest.mock import MagicMock

    mock_tokenizer.return_value = {"input_ids": np.array([[1]]), "attention_mask": np.array([[1]])}
    mock_session.return_value = MagicMock()
    mock_session.get_inputs.return_value = []
    mock_session.run.return_value = [np.array([[[0.1, 0.2]]])]

    emb1 = get_cached_embedding("test query")
    emb2 = get_cached_embedding("test query")

    assert emb1 is emb2 # Should be cached
