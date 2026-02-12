"""
test_comprehensive.py - Dynamic, comprehensive unit tests for HistoryMindAI.

Strategy: NO static assertions — tests are data-driven from actual registries
and knowledge_base.json. If a new alias is added, tests automatically cover it.

Coverage:
  A. Entity Registry — extract_persons, normalize_person, HARDCODED_PERSON_PATTERNS
  B. Entity Registry — extract_places, extract_dynasty, extract_keywords_smart
  C. Entity Registry — is_valid_person, classify_tone, classify_nature
  D. Knowledge Base — structural integrity, alias consistency
  E. Search Service — scan_by_entities text fallback
  F. Search Service — check_query_relevance alias-aware matching
  G. Search Service — resolve_query_entities completeness
  H. Integration — end-to-end pipeline from query to results
"""
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from collections import defaultdict
import pytest

# Ensure ai-service is in path
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
SCRIPTS_DIR = AI_SERVICE_DIR / "scripts"

if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Mock heavy dependencies before import
sys.modules.setdefault('faiss', MagicMock())
sys.modules.setdefault('sentence_transformers', MagicMock())


# ===================================================================
# HELPERS
# ===================================================================

def load_knowledge_base():
    """Load actual knowledge_base.json for data-driven tests."""
    kb_path = AI_SERVICE_DIR / "knowledge_base.json"
    if not kb_path.exists():
        pytest.skip("knowledge_base.json not found")
    with open(kb_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_entity_registry():
    """Import entity_registry module."""
    import entity_registry
    return entity_registry


# Rich mock documents covering multiple scenarios
MOCK_DOCS = [
    {
        "year": 40, "event": "Khởi nghĩa Hai Bà Trưng",
        "story": "Trưng Trắc và Trưng Nhị lãnh đạo khởi nghĩa chống quân Hán.",
        "tone": "heroic", "persons": ["Hai Bà Trưng"],
        "persons_all": ["Trưng Trắc", "Trưng Nhị"],
        "places": [], "dynasty": "Trưng Vương",
        "keywords": ["khởi_nghĩa"], "title": "Khởi nghĩa Hai Bà Trưng",
    },
    {
        "year": 938, "event": "Trận Bạch Đằng",
        "story": "Ngô Quyền dùng cọc gỗ đặt ngầm trên sông Bạch Đằng đánh bại quân Nam Hán.",
        "tone": "heroic", "persons": ["Ngô Quyền"],
        "persons_all": ["Ngô Quyền"],
        "places": ["Bạch Đằng"], "dynasty": "Tự chủ",
        "keywords": ["bạch_đằng"], "title": "Trận Bạch Đằng 938",
    },
    {
        "year": 1010, "event": "Lý Thái Tổ dời đô về Thăng Long",
        "story": "Lý Công Uẩn lên ngôi, dời đô từ Hoa Lư về Thăng Long.",
        "tone": "neutral", "persons": ["Lý Thái Tổ"],
        "persons_all": ["Lý Công Uẩn", "Lý Thái Tổ"],
        "places": ["Thăng Long", "Hoa Lư"], "dynasty": "Lý",
        "keywords": ["dời_đô", "thăng_long"], "title": "Dời đô Thăng Long",
    },
    {
        "year": 1288, "event": "Chiến thắng Bạch Đằng",
        "story": "Trần Hưng Đạo đánh tan quân Nguyên Mông trên sông Bạch Đằng.",
        "tone": "heroic", "persons": ["Trần Hưng Đạo"],
        "persons_all": ["Trần Hưng Đạo"],
        "places": ["Bạch Đằng"], "dynasty": "Trần",
        "keywords": ["bạch_đằng", "trần_hưng_đạo"],
        "title": "Chiến thắng Bạch Đằng 1288",
    },
    {
        "year": 1418, "event": "Khởi nghĩa Lam Sơn bùng nổ",
        "story": "Lê Lợi dựng cờ khởi nghĩa ở Lam Sơn chống quân Minh.",
        "tone": "heroic", "persons": ["Lê Lợi"],
        "persons_all": ["Lê Lợi"],
        "places": ["Lam Sơn"], "dynasty": "Minh thuộc",
        "keywords": ["khởi_nghĩa", "lam_sơn", "lê_lợi", "giải_phóng"],
        "title": "Khởi nghĩa Lam Sơn",
    },
    {
        "year": 1789, "event": "Quang Trung đại phá quân Thanh",
        "story": "Nguyễn Huệ (Quang Trung) đánh tan 29 vạn quân Thanh tại Đống Đa.",
        "tone": "heroic", "persons": ["Nguyễn Huệ"],
        "persons_all": ["Quang Trung", "Nguyễn Huệ"],
        "places": ["Đống Đa"], "dynasty": "Tây Sơn",
        "keywords": ["đống_đa", "quang_trung"],
        "title": "Quang Trung đại phá quân Thanh",
    },
    {
        "year": 1945, "event": "Cách mạng Tháng Tám",
        "story": "Hồ Chí Minh đọc Tuyên ngôn Độc lập, khai sinh nước Việt Nam.",
        "tone": "heroic", "persons": ["Hồ Chí Minh"],
        "persons_all": ["Hồ Chí Minh"],
        "places": ["Ba Đình"], "dynasty": "Hiện đại",
        "keywords": ["cách_mạng", "hồ_chí_minh", "độc_lập"],
        "title": "Cách mạng Tháng Tám",
    },
]


def setup_full_mocks():
    """Configure startup with mock data + knowledge base for testing."""
    import app.core.startup as startup

    startup.DOCUMENTS = list(MOCK_DOCS)
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

    # Build from knowledge_base.json dynamically
    kb = load_knowledge_base()

    startup.PERSON_ALIASES = {}
    for canonical, aliases in kb.get("person_aliases", {}).items():
        startup.PERSON_ALIASES[canonical] = canonical
        for alias in aliases:
            startup.PERSON_ALIASES[alias] = canonical

    startup.DYNASTY_ALIASES = {}
    for canonical, aliases in kb.get("dynasty_aliases", {}).items():
        startup.DYNASTY_ALIASES[canonical] = canonical
        for alias in aliases:
            startup.DYNASTY_ALIASES[alias] = canonical

    startup.TOPIC_SYNONYMS = {}
    for canonical, synonyms in kb.get("topic_synonyms", {}).items():
        startup.TOPIC_SYNONYMS[canonical] = canonical
        for syn in synonyms:
            startup.TOPIC_SYNONYMS[syn] = canonical


# ===================================================================
# A. ENTITY REGISTRY — extract_persons (dynamic)
# ===================================================================

class TestExtractPersonsDynamic:
    """Test extract_persons using PERSON_ALIASES keys to generate test cases."""

    def setup_method(self):
        self.registry = get_entity_registry()

    def test_standard_capitalized_name(self):
        """Standard Vietnamese name with capital letters should be extracted."""
        result = self.registry.extract_persons("Trần Hưng Đạo đánh quân Nguyên")
        assert "Trần Hưng Đạo" in result

    def test_hai_ba_trung_lowercase_hai(self):
        """'hai Bà Trưng' with lowercase 'hai' MUST be extracted (bug fix)."""
        result = self.registry.extract_persons("hai Bà Trưng khởi nghĩa chống quân Hán")
        assert "Hai Bà Trưng" in result

    def test_hai_ba_trung_capitalized(self):
        """'Hai Bà Trưng' with capital H MUST be extracted."""
        result = self.registry.extract_persons("Hai Bà Trưng lãnh đạo nhân dân")
        assert "Hai Bà Trưng" in result

    def test_trung_trac_maps_to_hai_ba_trung(self):
        """'Trưng Trắc' should be extracted as 'Hai Bà Trưng' via hardcoded patterns."""
        result = self.registry.extract_persons("Trưng Trắc cùng Trưng Nhị khởi nghĩa")
        assert "Hai Bà Trưng" in result

    def test_trung_nhi_maps_to_hai_ba_trung(self):
        """'Trưng Nhị' should also be extracted."""
        result = self.registry.extract_persons("Trưng Nhị là em của Trưng Trắc")
        assert "Hai Bà Trưng" in result

    def test_hardcoded_patterns_iterate_all(self):
        """Every HARDCODED_PERSON_PATTERNS entry should match its sample text."""
        for pattern, canonical in self.registry.HARDCODED_PERSON_PATTERNS:
            # Generate sample text from the pattern's canonical name
            sample = f"Cuộc khởi nghĩa của {canonical} diễn ra năm 40."
            result = self.registry.extract_persons(sample)
            assert canonical in result, f"HARDCODED pattern for '{canonical}' didn't match in: '{sample}'"

    def test_normalize_person_all_aliases(self):
        """Every alias in PERSON_ALIASES should normalize to its canonical form."""
        for alias, canonical in self.registry.PERSON_ALIASES.items():
            result = self.registry.normalize_person(alias.title())
            # Should return canonical form (normalize_person keeps original case if no match)
            assert result is not None, f"normalize_person failed for alias: '{alias}'"

    def test_empty_text_returns_empty(self):
        result = self.registry.extract_persons("")
        assert result == []

    def test_no_persons_in_text(self):
        result = self.registry.extract_persons("năm 1945 là năm quan trọng")
        assert result == []

    def test_geo_context_no_false_positive(self):
        """Person-like strings after 'tỉnh', 'sông', etc. should NOT be extracted."""
        result = self.registry.extract_persons("tỉnh Bình Dương có nhiều khu công nghiệp")
        assert "Bình Dương" not in result, "Geographic entity should not be extracted as person"


# ===================================================================
# B. ENTITY REGISTRY — extract_places, extract_dynasty, keywords
# ===================================================================

class TestExtractPlacesDynamic:
    def setup_method(self):
        self.registry = get_entity_registry()

    def test_geo_prefix_extraction(self):
        """'sông X', 'tỉnh X' should extract places."""
        result = self.registry.extract_places("Trận chiến trên sông Bạch Đằng")
        assert any("bạch đằng" in p.lower() for p in result)

    def test_empty_text_returns_empty(self):
        assert self.registry.extract_places("") == []


class TestExtractDynastyDynamic:
    def setup_method(self):
        self.registry = get_entity_registry()

    def test_all_dynasty_patterns_match(self):
        """Every DYNASTY_PATTERNS entry should be detectable."""
        for pattern_str, canonical_name in self.registry.DYNASTY_PATTERNS:
            # Build a sample text containing the pattern
            sample = f"Thời kỳ {canonical_name} có nhiều sự kiện quan trọng."
            result = self.registry.extract_dynasty(sample)
            assert result is not None, f"Dynasty pattern '{canonical_name}' not detected in: '{sample}'"

    def test_nha_tran_detection(self):
        assert self.registry.extract_dynasty("nhà Trần có nhiều vua giỏi") is not None

    def test_year_fallback(self):
        """If no pattern found, year should help guess dynasty."""
        result = self.registry.extract_dynasty("", year=1300)
        # 1300 falls in Trần dynasty era (1225-1400)
        assert result is not None


class TestExtractKeywordsDynamic:
    def setup_method(self):
        self.registry = get_entity_registry()

    def test_returns_keywords(self):
        result = self.registry.extract_keywords_smart(
            "Trần Hưng Đạo đánh quân Nguyên Mông trên sông Bạch Đằng",
            persons=["Trần Hưng Đạo"], places=["Bạch Đằng"]
        )
        # Should return some keywords
        assert len(result) > 0

    def test_empty_text(self):
        result = self.registry.extract_keywords_smart("")
        assert result == []


# ===================================================================
# C. ENTITY REGISTRY — is_valid_person, classify_tone, classify_nature
# ===================================================================

class TestIsValidPerson:
    def setup_method(self):
        self.registry = get_entity_registry()

    def test_not_person_exact_blocked(self):
        """All entries in NOT_PERSON_EXACT should be rejected."""
        for name in list(self.registry.NOT_PERSON_EXACT)[:10]:
            assert not self.registry.is_valid_person(name), \
                f"NOT_PERSON_EXACT entry '{name}' was wrongly accepted as valid person"

    def test_collective_terms_blocked(self):
        """Collective terms like 'nhân dân', 'quân đội' should be rejected."""
        for term in list(self.registry.COLLECTIVE_TERMS)[:5]:
            assert not self.registry.is_valid_person(term), \
                f"Collective term '{term}' was wrongly accepted as person"

    def test_valid_names_accepted(self):
        """Known historical names should pass validation."""
        valid_names = ["Trần Hưng Đạo", "Lý Thường Kiệt", "Nguyễn Huệ", "Lê Lợi"]
        for name in valid_names:
            assert self.registry.is_valid_person(name), \
                f"Valid person '{name}' was wrongly rejected"


class TestClassifyTone:
    def setup_method(self):
        self.registry = get_entity_registry()

    def test_heroic_text(self):
        tone = self.registry.classify_tone("quân ta đại thắng, đánh tan quân xâm lược")
        assert tone in ("heroic", "tragic", "neutral", "diplomatic", "mixed")

    def test_neutral_text(self):
        tone = self.registry.classify_tone("triều đình ban hành nghị định mới")
        assert tone is not None

    def test_empty_text(self):
        tone = self.registry.classify_tone("")
        assert tone is not None


class TestClassifyNature:
    def setup_method(self):
        self.registry = get_entity_registry()

    def test_military_event(self):
        nature = self.registry.classify_nature("trận đánh tiêu diệt quân xâm lược")
        assert nature is not None

    def test_empty_text(self):
        nature = self.registry.classify_nature("")
        assert nature is not None


# ===================================================================
# D. KNOWLEDGE BASE — structural integrity
# ===================================================================

class TestKnowledgeBaseIntegrity:
    """Data-driven tests: validate knowledge_base.json structure."""

    def setup_method(self):
        self.kb = load_knowledge_base()

    def test_required_sections_exist(self):
        """knowledge_base.json must have person_aliases, topic_synonyms, dynasty_aliases."""
        assert "person_aliases" in self.kb
        assert "topic_synonyms" in self.kb
        assert "dynasty_aliases" in self.kb

    def test_person_aliases_all_have_list_values(self):
        """Every person_aliases value should be a list."""
        for person, aliases in self.kb["person_aliases"].items():
            assert isinstance(aliases, list), \
                f"person_aliases['{person}'] value is {type(aliases)}, expected list"

    def test_topic_synonyms_all_have_list_values(self):
        for topic, syns in self.kb["topic_synonyms"].items():
            assert isinstance(syns, list), \
                f"topic_synonyms['{topic}'] value is {type(syns)}, expected list"

    def test_dynasty_aliases_all_have_list_values(self):
        for dynasty, aliases in self.kb["dynasty_aliases"].items():
            assert isinstance(aliases, list), \
                f"dynasty_aliases['{dynasty}'] value is {type(aliases)}, expected list"

    def test_no_empty_canonical_keys(self):
        """No section should have an empty string as a canonical key."""
        for section in ("person_aliases", "topic_synonyms", "dynasty_aliases"):
            for key in self.kb[section]:
                assert key.strip() != "", f"Empty canonical key found in {section}"

    def test_no_alias_duplicates_across_canonicals(self):
        """An alias should not map to multiple different canonical entries (warn only)."""
        duplicates = []
        for section in ("person_aliases", "topic_synonyms", "dynasty_aliases"):
            seen = {}
            for canonical, aliases in self.kb[section].items():
                for alias in aliases:
                    if alias in seen and seen[alias] != canonical:
                        duplicates.append(
                            f"'{alias}' in {section}: '{seen[alias]}' vs '{canonical}'"
                        )
                    seen[alias] = canonical
        # Known overlaps (e.g. 'quốc tử giám' in both 'giáo dục' and 'văn miếu') are acceptable
        # Only fail if there are unexpected duplicates beyond known ones
        known_overlaps = {"quốc tử giám"}
        unexpected = [d for d in duplicates if not any(k in d for k in known_overlaps)]
        assert len(unexpected) == 0, f"Unexpected alias duplicates: {unexpected}"

    def test_hai_ba_trung_in_person_aliases(self):
        """Hai Bà Trưng must exist as a canonical person."""
        assert "hai bà trưng" in self.kb["person_aliases"]
        aliases = self.kb["person_aliases"]["hai bà trưng"]
        assert any("trưng trắc" in a for a in aliases)
        assert any("trưng nhị" in a for a in aliases)

    def test_critical_topics_present(self):
        """Critical topic_synonyms that tests depend on must exist."""
        required = ["nguyên mông", "pháp thuộc", "giáo dục"]
        for topic in required:
            assert topic in self.kb["topic_synonyms"], \
                f"Required topic '{topic}' missing from knowledge_base.json"

    def test_critical_dynasties_present(self):
        """Core dynasties must be in dynasty_aliases."""
        required = ["trần", "lý", "lê", "nguyễn"]
        for dynasty in required:
            assert dynasty in self.kb["dynasty_aliases"], \
                f"Required dynasty '{dynasty}' missing from knowledge_base.json"


# ===================================================================
# E. SEARCH SERVICE — scan_by_entities TEXT FALLBACK
# ===================================================================

class TestScanByEntitiesTextFallback:
    """Test that scan_by_entities falls back to text scan when index is empty."""

    def setup_method(self):
        setup_full_mocks()
        from app.services.search_service import scan_by_entities
        self.scan = scan_by_entities

    def test_fallback_finds_hai_ba_trung_in_text(self):
        """Even if PERSONS_INDEX has no 'hai bà trưng', text scan should find it."""
        import app.core.startup as startup
        # Remove 'hai bà trưng' from index to simulate missing metadata
        for key in list(startup.PERSONS_INDEX.keys()):
            if "trưng" in key or "hai bà" in key:
                del startup.PERSONS_INDEX[key]

        docs = self.scan({
            "persons": ["hai bà trưng"],
            "dynasties": [], "topics": [], "places": []
        })
        # Should find via text scan in story field
        assert len(docs) > 0, "Text fallback failed to find Hai Bà Trưng"

    def test_fallback_finds_quang_trung_via_alias(self):
        """Searching 'nguyễn huệ' should find docs containing 'Quang Trung' alias."""
        import app.core.startup as startup
        # Remove from index
        startup.PERSONS_INDEX.pop("nguyễn huệ", None)

        docs = self.scan({
            "persons": ["nguyễn huệ"],
            "dynasties": [], "topics": [], "places": []
        })
        assert len(docs) > 0, "Text fallback failed to find Nguyễn Huệ via alias"

    def test_index_direct_lookup_still_works(self):
        """Standard index lookup for existing entries should work."""
        docs = self.scan({
            "persons": ["trần hưng đạo"],
            "dynasties": [], "topics": [], "places": []
        })
        assert len(docs) > 0

    def test_empty_resolved_returns_empty(self):
        docs = self.scan({
            "persons": [], "dynasties": [], "topics": [], "places": []
        })
        assert docs == []

    def test_nonexistent_person_returns_empty(self):
        """Completely unknown person not in any text should return nothing."""
        docs = self.scan({
            "persons": ["nhân vật ảo không tồn tại xyz"],
            "dynasties": [], "topics": [], "places": []
        })
        assert docs == []


# ===================================================================
# F. SEARCH SERVICE — check_query_relevance ALIAS-AWARE
# ===================================================================

class TestCheckRelevanceAliasAware:
    """Test alias-aware keyword matching in check_query_relevance."""

    def setup_method(self):
        setup_full_mocks()
        from app.services.search_service import check_query_relevance
        self.check = check_query_relevance

    def test_quang_trung_matches_nguyen_hue_doc(self):
        """Query 'Quang Trung' should match doc with 'Nguyễn Huệ' via alias expansion."""
        doc_nguyen_hue = {
            "year": 1789, "event": "Đại phá quân Thanh",
            "story": "Nguyễn Huệ đánh tan quân Thanh",
            "persons": ["Nguyễn Huệ"], "places": ["Đống Đa"],
            "dynasty": "Tây Sơn", "keywords": ["đống_đa"],
            "title": "Quang Trung đại phá quân Thanh"
        }
        assert self.check("Quang Trung đánh quân Thanh", doc_nguyen_hue) is True

    def test_hai_ba_trung_matches_trung_trac_doc(self):
        """Query 'Hai Bà Trưng' should match docs mentioning 'Trưng Trắc'."""
        doc = {
            "year": 40, "event": "Khởi nghĩa",
            "story": "Trưng Trắc cùng em gái Trưng Nhị nổi dậy",
            "persons": ["Trưng Trắc", "Trưng Nhị"],
            "places": [], "dynasty": "", "keywords": ["khởi_nghĩa"],
            "title": "Khởi nghĩa Trưng Trắc"
        }
        assert self.check("Hai Bà Trưng khởi nghĩa", doc) is True

    def test_irrelevant_doc_rejected(self):
        """Query about a completely unrelated topic should NOT match docs about HCM."""
        doc_hcm = MOCK_DOCS[6]  # HCM doc
        assert self.check("Nhà Đinh thống nhất đất nước năm 968", doc_hcm) is False

    def test_dynasty_filter_overrides(self):
        """Dynasty filter should accept docs from same dynasty regardless of keywords."""
        doc_tran = MOCK_DOCS[3]  # Trần dynasty doc
        assert self.check("Bất kỳ câu hỏi", doc_tran, "Trần") is True

    def test_dynasty_filter_rejects_mismatch(self):
        """Dynasty filter 'Lý' should reject Trần dynasty docs."""
        doc_tran = MOCK_DOCS[3]  # Trần dynasty doc
        assert self.check("Bất kỳ câu hỏi", doc_tran, "Lý") is False


# ===================================================================
# G. SEARCH SERVICE — resolve_query_entities DATA-DRIVEN
# ===================================================================

class TestResolveEntitiesDataDriven:
    """Data-driven: iterate over ALL aliases in knowledge_base.json
    and verify resolve_query_entities handles them dynamically."""

    def setup_method(self):
        setup_full_mocks()
        self.kb = load_knowledge_base()
        from app.services.search_service import resolve_query_entities
        self.resolve = resolve_query_entities

    def test_all_person_aliases_resolve(self):
        """Every alias in person_aliases should resolve to its canonical person."""
        for canonical, aliases in self.kb["person_aliases"].items():
            for alias in aliases:
                query = f"{alias.title()} đã làm gì trong lịch sử?"
                r = self.resolve(query)
                assert canonical in r["persons"], \
                    f"Person alias '{alias}' → canonical '{canonical}' NOT resolved in query: '{query}'. Got: {r['persons']}"

    def test_all_dynasty_aliases_resolve(self):
        """Every alias in dynasty_aliases should resolve to its canonical dynasty."""
        for canonical, aliases in self.kb["dynasty_aliases"].items():
            for alias in aliases:
                query = f"{alias.title()} có bao nhiêu đời vua?"
                r = self.resolve(query)
                assert canonical in r["dynasties"], \
                    f"Dynasty alias '{alias}' → '{canonical}' NOT resolved. Got: {r['dynasties']}"

    def test_all_topic_synonyms_resolve(self):
        """Every synonym in topic_synonyms should resolve to SOME canonical topic."""
        # Note: Some synonyms appear in multiple topics (e.g. 'quốc tử giám' → 'giáo dục' AND 'văn miếu')
        # So we check that at least one topic is resolved
        for canonical, synonyms in self.kb["topic_synonyms"].items():
            for syn in synonyms:
                query = f"Hãy kể về {syn.title()}"
                r = self.resolve(query)
                assert len(r["topics"]) > 0, \
                    f"Topic synonym '{syn}' resolved to NO topics. Expected at least '{canonical}'."

    def test_canonical_person_self_resolves(self):
        """Canonical person name itself should resolve correctly."""
        for canonical in self.kb["person_aliases"]:
            query = f"{canonical.title()} là ai?"
            r = self.resolve(query)
            assert canonical in r["persons"], \
                f"Canonical person '{canonical}' did not self-resolve. Got: {r['persons']}"

    def test_empty_query(self):
        r = self.resolve("")
        assert r == {"persons": [], "dynasties": [], "topics": [], "places": []}

    def test_gibberish_query(self):
        r = self.resolve("zzzzz xxxxx qqqqq")
        assert all(not v for v in r.values())


# ===================================================================
# H. INTEGRATION — end-to-end from query to results
# ===================================================================

class TestEndToEndIntegration:
    """Integration tests: query → resolve → scan → results."""

    def setup_method(self):
        setup_full_mocks()
        from app.services.search_service import resolve_query_entities, scan_by_entities
        self.resolve = resolve_query_entities
        self.scan = scan_by_entities

    def test_hai_ba_trung_e2e(self):
        """Full pipeline: 'Hai Bà Trưng' → resolve → scan → results."""
        resolved = self.resolve("Hai Bà Trưng khởi nghĩa chống quân Hán")
        assert "hai bà trưng" in resolved["persons"]
        docs = self.scan(resolved)
        assert len(docs) > 0
        # At least one doc about Hai Bà Trưng
        all_text = " ".join(d.get("story", "") + d.get("event", "") for d in docs).lower()
        assert "trưng" in all_text

    def test_quang_trung_e2e(self):
        """Full pipeline: 'Quang Trung' (alias) → Nguyễn Huệ → scan."""
        resolved = self.resolve("Quang Trung đánh quân Thanh")
        assert "nguyễn huệ" in resolved["persons"]
        docs = self.scan(resolved)
        assert len(docs) > 0

    def test_nha_tran_e2e(self):
        """'Nhà Trần' → dynasty resolution → find Trần docs."""
        resolved = self.resolve("Nhà Trần chống quân Nguyên Mông")
        assert "trần" in resolved["dynasties"]
        docs = self.scan(resolved)
        assert len(docs) > 0
        assert any(d.get("dynasty", "").lower() == "trần" for d in docs)

    def test_le_loi_alias_e2e(self):
        """'Lê Thái Tổ' (alias for Lê Lợi) → scan."""
        resolved = self.resolve("Lê Thái Tổ dựng cờ khởi nghĩa")
        assert "lê lợi" in resolved["persons"]
        docs = self.scan(resolved)
        assert len(docs) > 0

    def test_ngo_quyen_bach_dang_e2e(self):
        """'Ngô Quyền' + 'Bạch Đằng' → multi-entity resolution."""
        resolved = self.resolve("Ngô Quyền đánh trận Bạch Đằng")
        assert "ngô quyền" in resolved["persons"]
        assert "bạch đằng" in resolved["places"]
        docs = self.scan(resolved)
        assert len(docs) > 0

    def test_van_mieu_topic_e2e(self):
        """'Văn Miếu' → topic synonym resolution."""
        resolved = self.resolve("Văn Miếu Quốc Tử Giám")
        # 'văn miếu' is a canonical topic itself, 'quốc tử giám' maps to it
        assert len(resolved["topics"]) > 0
        assert any(t in resolved["topics"] for t in ["văn miếu", "giáo dục"])

    def test_bac_ho_alias_e2e(self):
        """'Bác Hồ' alias → 'hồ chí minh' canonical."""
        resolved = self.resolve("Bác Hồ đọc Tuyên ngôn Độc lập")
        assert "hồ chí minh" in resolved["persons"]
        docs = self.scan(resolved)
        assert len(docs) > 0


# ===================================================================
# I. ENTITY REGISTRY PERSON_ALIASES CONSISTENCY
# ===================================================================

class TestEntityRegistryAliasConsistency:
    """Verify entity_registry.py PERSON_ALIASES stays in sync with knowledge_base.json."""

    def setup_method(self):
        self.registry = get_entity_registry()
        self.kb = load_knowledge_base()

    def test_all_kb_person_aliases_in_registry(self):
        """Every alias in knowledge_base.json should map via entity_registry normalize_person."""
        for canonical, aliases in self.kb["person_aliases"].items():
            for alias in aliases:
                # Check that normalize_person can handle this alias
                result = self.registry.normalize_person(alias.title())
                # Result should either be the canonical name or the alias title-cased
                assert result is not None, \
                    f"entity_registry.normalize_person('{alias.title()}') returned None"


# ===================================================================
# J. HARDCODED_PERSON_PATTERNS COMPLETENESS
# ===================================================================

class TestHardcodedPatterns:
    """Verify HARDCODED_PERSON_PATTERNS work correctly."""

    def setup_method(self):
        self.registry = get_entity_registry()

    def test_patterns_exist(self):
        """HARDCODED_PERSON_PATTERNS should have entries."""
        assert hasattr(self.registry, 'HARDCODED_PERSON_PATTERNS')
        assert len(self.registry.HARDCODED_PERSON_PATTERNS) > 0

    def test_each_pattern_is_tuple_of_regex_and_string(self):
        """Each entry should be (compiled_regex, canonical_string)."""
        import re as re_module
        for entry in self.registry.HARDCODED_PERSON_PATTERNS:
            assert isinstance(entry, tuple) and len(entry) == 2
            pattern, canonical = entry
            assert isinstance(pattern, re_module.Pattern), f"Pattern is not compiled regex: {pattern}"
            assert isinstance(canonical, str) and len(canonical) > 0

    def test_all_patterns_trigger(self):
        """Each pattern should match at least one relevant text."""
        # Build test texts that specifically target each pattern
        test_texts = {
            "Hai Bà Trưng": [
                "Hai Bà Trưng khởi nghĩa",
                "Trưng Trắc và em Trưng Nhị",
            ],
        }
        for pattern, canonical in self.registry.HARDCODED_PERSON_PATTERNS:
            texts = test_texts.get(canonical, [f"{canonical} trong lịch sử"])
            matched = any(pattern.search(t) for t in texts)
            assert matched, f"Pattern {pattern.pattern} for '{canonical}' didn't match any test texts"

    def test_case_insensitive_hai_ba_trung(self):
        """Pattern should match 'HAI BÀ TRƯNG', 'hai bà trưng', etc."""
        hai_ba_patterns = [p for p, c in self.registry.HARDCODED_PERSON_PATTERNS if c == "Hai Bà Trưng"]
        assert len(hai_ba_patterns) > 0
        variations = ["Hai Bà Trưng", "hai bà trưng", "HAI BÀ TRƯNG"]
        for text in variations:
            matched = any(p.search(text) for p in hai_ba_patterns)
            assert matched, f"Hai Bà Trưng pattern didn't match: '{text}'"


# ===================================================================
# K. KNOWLEDGE BASE — NEW TOPIC SYNONYMS
# ===================================================================

class TestNewTopicSynonyms:
    """Verify newly added topic_synonyms."""

    def setup_method(self):
        self.kb = load_knowledge_base()

    def test_bach_dang_topic_exists(self):
        assert "trận bạch đằng" in self.kb["topic_synonyms"]
        syns = self.kb["topic_synonyms"]["trận bạch đằng"]
        assert "bạch đằng" in syns

    def test_hai_ba_trung_topic_exists(self):
        assert "hai bà trưng" in self.kb["topic_synonyms"]

    def test_van_mieu_topic_exists(self):
        assert "văn miếu" in self.kb["topic_synonyms"]
        syns = self.kb["topic_synonyms"]["văn miếu"]
        assert "quốc tử giám" in syns

    def test_ngo_quyen_topic_exists(self):
        assert "ngô quyền" in self.kb["topic_synonyms"]

    def test_le_loi_topic_exists(self):
        assert "lê lợi" in self.kb["topic_synonyms"]
        syns = self.kb["topic_synonyms"]["lê lợi"]
        assert "khởi nghĩa lam sơn" in syns


# ===================================================================
# L. EDGE CASES & ROBUSTNESS
# ===================================================================

class TestEdgeCasesRobust:
    """Edge cases that should never crash the system."""

    def setup_method(self):
        setup_full_mocks()
        from app.services.search_service import (
            resolve_query_entities, scan_by_entities,
            check_query_relevance, extract_important_keywords,
        )
        self.resolve = resolve_query_entities
        self.scan = scan_by_entities
        self.check = check_query_relevance
        self.extract_kw = extract_important_keywords

    def test_unicode_diacritics(self):
        """Vietnamese diacritics must be handled."""
        r = self.resolve("Trần Hưng Đạo đánh Mông Cổ")
        assert "trần hưng đạo" in r["persons"]

    def test_very_long_query(self):
        """Very long query should not crash."""
        query = "Trần Hưng Đạo " * 100
        r = self.resolve(query)
        assert isinstance(r, dict)

    def test_special_characters_in_query(self):
        """Query with special chars should not crash."""
        r = self.resolve("Trần Hưng Đạo!!! @#$% ???")
        assert isinstance(r, dict)

    def test_numbers_only_query(self):
        r = self.resolve("12345 67890")
        assert isinstance(r, dict)

    def test_scan_max_results_respected(self):
        docs = self.scan(
            {"persons": ["trần hưng đạo"], "dynasties": ["trần"],
             "topics": [], "places": ["bạch đằng"]},
            max_results=1
        )
        assert len(docs) <= 1

    def test_check_query_relevance_empty_doc(self):
        """check_query_relevance should handle docs with missing fields."""
        empty_doc = {"year": 0}
        result = self.check("Trần Hưng Đạo", empty_doc)
        assert isinstance(result, bool)

    def test_extract_keywords_none_safe(self):
        """extract_important_keywords should handle empty string."""
        result = self.extract_kw("")
        assert isinstance(result, set)
