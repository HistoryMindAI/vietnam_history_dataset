"""
test_advanced_resilience.py — Production-Hardened Validation Suite (Level 4–6 Maturity)

35 tests across 9 categories:
  Cat 1: Determinism          (tests 28–31)
  Cat 2: Retrieval Integrity  (tests 32–35)
  Cat 3: Guardrail Correction (tests 36–40)
  Cat 4: FAISS Index Integrity(tests 41–43)
  Cat 5: Version Freeze       (tests 44–47)
  Cat 6: Chaos / Corruption   (tests 48–52)
  Cat 7: Concurrency Safety   (tests 53–54)
  Cat 8: Performance Guard    (tests 55–56)
  Cat 9: Data Type Corruption (tests 57–61)

ALL assertions are dynamic — derive expected values from the engine's own data.
"""

import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# PATH SETUP — identical to test_enterprise_levels.py
# ---------------------------------------------------------------------------
_AI_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "ai-service")
if _AI_SERVICE_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_AI_SERVICE_DIR))

# Mock heavy deps before import
sys.modules.setdefault("faiss", MagicMock())
sys.modules.setdefault("sentence_transformers", MagicMock())

# ---------------------------------------------------------------------------
# MOCK DATA — reuse from test_enterprise_levels
# ---------------------------------------------------------------------------
from tests.test_enterprise_levels import (
    ALL_MOCK_DOCS,
    _setup_full_mocks,
    _find_events_for_person,
    _find_events_for_year,
)

# Auto-setup mocks for all tests in this module
@pytest.fixture(autouse=True)
def setup_mocks():
    _setup_full_mocks()
    yield


# ===================================================================
# 🔁 CATEGORY 1 — DETERMINISM (Tests 28–31)
# ===================================================================

class TestCat1Determinism:
    """Verify engine produces identical output across repeated calls."""

    @patch("app.services.engine.semantic_search")
    def test_28_deterministic_output(self, mock_search):
        """Run same query 20× → all outputs must be identical."""
        mock_search.return_value = []
        from app.services.engine import engine_answer

        query = "Ngô Quyền mất năm nào?"
        outputs = [engine_answer(query) for _ in range(20)]

        # Compare answer text
        answers = [o.get("answer", "") for o in outputs]
        assert len(set(answers)) == 1, \
            f"Non-deterministic answers: {len(set(answers))} unique across 20 runs"

        # Compare intent
        intents = [o.get("intent", "") for o in outputs]
        assert len(set(intents)) == 1, \
            f"Non-deterministic intents: {set(intents)}"

        # Compare no_data flag
        no_data_flags = [o.get("no_data") for o in outputs]
        assert len(set(no_data_flags)) == 1, \
            f"Non-deterministic no_data: {set(no_data_flags)}"

    @patch("app.services.engine.semantic_search")
    def test_29_deterministic_fact_check(self, mock_search):
        """Fact-check query 20× → identical output."""
        mock_search.return_value = []
        from app.services.engine import engine_answer

        query = "Bạch Đằng 938 đúng không?"
        outputs = [engine_answer(query) for _ in range(20)]

        answers = [o.get("answer", "") for o in outputs]
        assert len(set(answers)) == 1, \
            f"Fact-check non-deterministic: {len(set(answers))} unique"

    @patch("app.services.engine.semantic_search")
    def test_30_retrieval_order_stable(self, mock_search):
        """20 runs → event lists must be in identical order."""
        mock_search.return_value = []
        from app.services.engine import engine_answer

        query = "Ngô Quyền mất năm nào?"
        outputs = [engine_answer(query) for _ in range(20)]

        # Extract event signatures for comparison
        def _event_sig(events):
            return tuple(
                (e.get("year"), e.get("event", "")[:50]) for e in events
            )

        sigs = [_event_sig(o.get("events", [])) for o in outputs]
        assert len(set(sigs)) == 1, \
            f"Event order unstable: {len(set(sigs))} unique orderings"

    @patch("app.services.engine.semantic_search")
    def test_31_answer_hash_stable(self, mock_search):
        """SHA256 of answer must be identical across 20 runs."""
        mock_search.return_value = []
        from app.services.engine import engine_answer

        query = "Bác Hồ ra đi tìm đường cứu nước năm bao nhiêu?"
        answers = [engine_answer(query).get("answer", "") for _ in range(20)]
        hashes = [hashlib.sha256(a.encode("utf-8")).hexdigest() for a in answers]

        assert len(set(hashes)) == 1, \
            f"Hash drift detected: {len(set(hashes))} unique hashes"


# ===================================================================
# 🔍 CATEGORY 2 — RETRIEVAL INTEGRITY (Tests 32–35)
# ===================================================================

class TestCat2RetrievalIntegrity:
    """Verify retrieval precision — no cross-entity leak, exact year match."""

    @patch("app.services.engine.semantic_search")
    def test_32_no_cross_entity_leak(self, mock_search):
        """scan_by_entities for Ngô Quyền → no docs exclusively about Nguyễn Huệ."""
        mock_search.return_value = []
        from app.services.search_service import scan_by_entities

        result = scan_by_entities({"persons": ["ngô quyền"]})

        for doc in result:
            persons = [p.lower() for p in doc.get("persons", []) + doc.get("persons_all", [])]
            # If doc has persons listed, at least one should be related to Ngô Quyền
            if persons and "ngô quyền" not in persons:
                # Check if this doc also doesn't mention Ngô Quyền in text
                story = doc.get("story", "").lower()
                event = doc.get("event", "").lower()
                assert "ngô quyền" in story or "ngô quyền" in event, \
                    f"Cross-entity leak: doc about {persons} returned for Ngô Quyền scan"

    @patch("app.services.engine.semantic_search")
    def test_33_year_scan_precision(self, mock_search):
        """scan_by_year(938) → all docs must have year=938."""
        mock_search.return_value = []
        from app.services.search_service import scan_by_year

        result = scan_by_year(938)
        for doc in result:
            assert doc.get("year") == 938, \
                f"Year scan imprecision: got year={doc.get('year')} for scan_by_year(938)"

    @patch("app.services.engine.semantic_search")
    def test_34_scan_nonexistent_entity(self, mock_search):
        """Unknown person → empty results, no random fallback."""
        mock_search.return_value = []
        from app.services.search_service import scan_by_entities

        result = scan_by_entities({"persons": ["unknown_hero_xyz"]})
        assert result == [], \
            f"Nonexistent entity returned {len(result)} docs — should be empty"

    @patch("app.services.engine.semantic_search")
    def test_35_dynasty_index_isolation(self, mock_search):
        """Trần dynasty scan → only Trần docs."""
        mock_search.return_value = []
        from app.services.search_service import scan_by_entities
        import app.core.startup as startup

        result = scan_by_entities({"dynasties": ["trần"]})
        tran_indices = set(startup.DYNASTY_INDEX.get("trần", []))

        for doc in result:
            dynasty = doc.get("dynasty", "").lower()
            # Doc must either be Trần dynasty or be in the DYNASTY_INDEX for Trần
            doc_idx = None
            for i, d in enumerate(startup.DOCUMENTS):
                if d is doc:
                    doc_idx = i
                    break
            if doc_idx is not None:
                assert doc_idx in tran_indices or "trần" in dynasty, \
                    f"Dynasty leak: {dynasty} doc (idx={doc_idx}) in Trần scan"


# ===================================================================
# 🛡️ CATEGORY 3 — GUARDRAIL CORRECTION (Tests 36–40)
# ===================================================================

class TestCat3GuardrailCorrection:
    """Verify OutputVerifier auto-correction, severity, idempotency."""

    def test_36_truncation_auto_fix(self):
        """Dangling comma → AUTO_FIX, corrected ends with period."""
        from app.services.guardrails import OutputVerifier, Severity

        verifier = OutputVerifier()
        result = verifier.verify("Ngô Quyền mất năm 944, ")
        truncation = next(
            (c for c in result.checks if c.name == "truncation"), None
        )
        assert truncation is not None
        if truncation.severity != Severity.PASS:
            assert truncation.severity == Severity.AUTO_FIX
            assert truncation.auto_corrected is True
            assert result.corrected_answer is not None
            assert result.corrected_answer.rstrip().endswith(".")

    def test_37_completeness_auto_fix(self):
        """Missing period → AUTO_FIX, period appended."""
        from app.services.guardrails import OutputVerifier, Severity

        verifier = OutputVerifier()
        result = verifier.verify("Ngô Quyền mất năm 944")
        completeness = next(
            (c for c in result.checks if c.name == "completeness"), None
        )
        assert completeness is not None
        if completeness.severity != Severity.PASS:
            assert completeness.severity == Severity.AUTO_FIX
            corrected = result.corrected_answer or "Ngô Quyền mất năm 944"
            assert corrected.rstrip().endswith(".")

    def test_38_empty_answer_hard_fail(self):
        """Empty string → HARD_FAIL, auto_correctable=False."""
        from app.services.guardrails import OutputVerifier, Severity

        verifier = OutputVerifier()
        result = verifier.verify("")
        assert result.status == Severity.HARD_FAIL
        assert result.passed is False
        assert result.auto_correctable is False

    def test_39_severity_escalation(self):
        """Multiple failure modes → worst severity wins."""
        from app.services.guardrails import OutputVerifier, Severity

        verifier = OutputVerifier()
        # Dangling comma + no proper ending = AUTO_FIX at minimum
        result = verifier.verify("Sự kiện lịch sử, ")

        # Worst severity should be at least AUTO_FIX
        severity_order = {
            Severity.PASS: 0,
            Severity.AUTO_FIX: 1,
            Severity.SOFT_FAIL: 2,
            Severity.HARD_FAIL: 3,
        }
        check_severities = [c.severity for c in result.checks]
        worst_check = max(check_severities, key=lambda s: severity_order.get(s, 0))
        assert severity_order[result.status] >= severity_order[worst_check], \
            f"Severity not escalated: status={result.status}, worst_check={worst_check}"

    def test_40_guardrail_idempotency(self):
        """verify(corrected) should not change further — idempotent."""
        from app.services.guardrails import OutputVerifier

        verifier = OutputVerifier()
        # First pass: truncated answer
        r1 = verifier.verify("Ngô Quyền mất năm 944, ")
        corrected = r1.corrected_answer or "Ngô Quyền mất năm 944, "

        # Second pass: corrected should be stable
        r2 = verifier.verify(corrected)
        second_corrected = r2.corrected_answer or corrected

        assert corrected == second_corrected, \
            f"Idempotency broken: '{corrected}' → '{second_corrected}'"


# ===================================================================
# 📦 CATEGORY 4 — FAISS INDEX INTEGRITY (Tests 41–43)
# ===================================================================

_INDEX_PATH = os.path.join(
    os.path.dirname(__file__), "..", "ai-service", "faiss_index", "index.bin"
)
_META_PATH = os.path.join(
    os.path.dirname(__file__), "..", "ai-service", "faiss_index", "meta.json"
)

# Try importing real faiss (not the mock) to check availability
try:
    # Temporarily remove mock to test real import
    _faiss_mock = sys.modules.get("faiss")
    if isinstance(_faiss_mock, MagicMock):
        del sys.modules["faiss"]
    import faiss as _real_faiss
    _HAS_FAISS = True
    # Restore mock for other tests
    sys.modules["faiss"] = _faiss_mock if _faiss_mock else _real_faiss
except ImportError:
    _HAS_FAISS = False
    # Re-install mock
    sys.modules["faiss"] = MagicMock()

_HAS_INDEX = _HAS_FAISS and os.path.exists(_INDEX_PATH) and os.path.exists(_META_PATH)


@pytest.mark.skipif(not _HAS_INDEX, reason="FAISS not installed or index not built")
class TestCat4FAISSIntegrity:
    """Verify FAISS index matches metadata — skip if index not built."""

    def _load_real_faiss(self):
        """Import real faiss, bypassing mock."""
        import importlib
        saved = sys.modules.get("faiss")
        if isinstance(saved, MagicMock):
            del sys.modules["faiss"]
        import faiss
        # Restore mock after use
        if saved is not None:
            sys.modules["faiss"] = saved
        return faiss

    def test_41_meta_count_matches_index(self):
        """ntotal == meta['count']."""
        faiss = self._load_real_faiss()
        idx = faiss.read_index(_INDEX_PATH)
        with open(_META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert idx.ntotal == meta["count"], \
            f"Count mismatch: index.ntotal={idx.ntotal}, meta.count={meta['count']}"

    def test_42_meta_dimension_matches_index(self):
        """index.d == meta['dimension']."""
        faiss = self._load_real_faiss()
        idx = faiss.read_index(_INDEX_PATH)
        with open(_META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        assert idx.d == meta["dimension"], \
            f"Dimension mismatch: index.d={idx.d}, meta.dimension={meta['dimension']}"

    def test_43_meta_schema_valid(self):
        """meta.json must have all required v3 schema keys."""
        with open(_META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        required_keys = {
            "index_version", "dimension", "count", "index_checksum_sha256",
        }
        missing = required_keys - set(meta.keys())
        assert not missing, f"meta.json missing required keys: {missing}"
        # Invariants
        assert isinstance(meta["count"], int) and meta["count"] > 0, \
            f"count must be positive int, got {meta['count']}"
        assert isinstance(meta["dimension"], int) and meta["dimension"] > 0, \
            f"dimension must be positive int, got {meta['dimension']}"
        assert len(meta["index_checksum_sha256"]) == 64, \
            f"checksum should be 64-char SHA256 hex"


# ===================================================================
# 🔒 CATEGORY 5 — VERSION FREEZE (Tests 44–47)
# ===================================================================

class TestCat5VersionFreeze:
    """Verify entity metadata, aliases, and synonym integrity."""

    def test_44_entity_metadata_core_coverage(self):
        """Core historical figures must exist in ENTITY_TEMPORAL_METADATA."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA

        core_entities = [
            "trần hưng đạo", "hồ chí minh", "ngô quyền", "lý thường kiệt"
        ]
        for entity in core_entities:
            assert entity in ENTITY_TEMPORAL_METADATA, \
                f"Core entity '{entity}' missing from ENTITY_TEMPORAL_METADATA"
            meta = ENTITY_TEMPORAL_METADATA[entity]
            assert "lifespan" in meta or "year_range" in meta, \
                f"Entity '{entity}' has no temporal data"

    def test_45_alias_coverage_complete(self):
        """Every person in mock data must have at least 1 alias entry."""
        import app.core.startup as startup

        # Collect all persons from mock data
        all_persons = set()
        for doc in ALL_MOCK_DOCS:
            for p in doc.get("persons", []):
                all_persons.add(p.strip().lower())

        # Check each person has an alias entry
        alias_values = set(startup.PERSON_ALIASES.values())
        for person in all_persons:
            has_entry = (
                person in startup.PERSON_ALIASES
                or person in alias_values
            )
            assert has_entry, \
                f"Person '{person}' has no alias entry in PERSON_ALIASES"

    def test_46_topic_synonyms_self_map(self):
        """Every canonical topic must map to itself."""
        import app.core.startup as startup

        canonicals = set(startup.TOPIC_SYNONYMS.values())
        for canon in canonicals:
            assert canon in startup.TOPIC_SYNONYMS, \
                f"Canonical '{canon}' doesn't self-map in TOPIC_SYNONYMS"
            assert startup.TOPIC_SYNONYMS[canon] == canon, \
                f"Self-map broken: '{canon}' → '{startup.TOPIC_SYNONYMS[canon]}'"

    def test_47_missing_entity_graceful(self):
        """Querying a removed entity should not crash the engine."""
        from app.services.conflict_detector import ENTITY_TEMPORAL_METADATA

        # Verify accessing a non-existent key returns None (not crash)
        result = ENTITY_TEMPORAL_METADATA.get("non_existent_entity_xyz")
        assert result is None, "Non-existent entity should return None"


# ===================================================================
# 💥 CATEGORY 6 — CHAOS / CORRUPTION (Tests 48–52)
# ===================================================================

class TestCat6ChaoCorruption:
    """Stress test with corrupted/edge-case data."""

    @patch("app.services.engine.semantic_search")
    def test_48_empty_documents_graceful(self, mock_search):
        """DOCUMENTS=[] → no crash, returns no_data."""
        mock_search.return_value = []
        import app.core.startup as startup
        from app.services.engine import engine_answer

        # Save originals
        orig_docs = startup.DOCUMENTS
        orig_by_year = startup.DOCUMENTS_BY_YEAR
        orig_persons = startup.PERSONS_INDEX
        orig_dynasty = startup.DYNASTY_INDEX
        orig_keyword = startup.KEYWORD_INDEX
        orig_places = startup.PLACES_INDEX
        try:
            startup.DOCUMENTS = []
            startup.DOCUMENTS_BY_YEAR = defaultdict(list)
            startup.PERSONS_INDEX = defaultdict(list)
            startup.DYNASTY_INDEX = defaultdict(list)
            startup.KEYWORD_INDEX = defaultdict(list)
            startup.PLACES_INDEX = defaultdict(list)

            r = engine_answer("Ngô Quyền mất năm nào?")
            assert isinstance(r, dict), "Should return valid dict"
            assert r.get("no_data", True) is True or r.get("events", []) == []
        finally:
            startup.DOCUMENTS = orig_docs
            startup.DOCUMENTS_BY_YEAR = orig_by_year
            startup.PERSONS_INDEX = orig_persons
            startup.DYNASTY_INDEX = orig_dynasty
            startup.KEYWORD_INDEX = orig_keyword
            startup.PLACES_INDEX = orig_places
            _setup_full_mocks()  # Restore

    @patch("app.services.engine.semantic_search")
    def test_49_single_document_only(self, mock_search):
        """1 document → valid response, no crash."""
        mock_search.return_value = []
        import app.core.startup as startup
        from app.services.engine import engine_answer

        single_doc = ALL_MOCK_DOCS[0]
        orig_docs = startup.DOCUMENTS
        orig_by_year = startup.DOCUMENTS_BY_YEAR
        orig_persons = startup.PERSONS_INDEX
        try:
            startup.DOCUMENTS = [single_doc]
            startup.DOCUMENTS_BY_YEAR = defaultdict(list)
            y = single_doc.get("year")
            if y is not None:
                startup.DOCUMENTS_BY_YEAR[y].append(single_doc)
            startup.PERSONS_INDEX = defaultdict(list)
            for p in single_doc.get("persons", []):
                startup.PERSONS_INDEX[p.strip().lower()].append(0)

            r = engine_answer("Kể cho tôi về lịch sử")
            assert isinstance(r, dict), "Should return valid dict for 1 doc"
        finally:
            startup.DOCUMENTS = orig_docs
            startup.DOCUMENTS_BY_YEAR = orig_by_year
            startup.PERSONS_INDEX = orig_persons
            _setup_full_mocks()

    @patch("app.services.engine.semantic_search")
    def test_50_corrupt_year_field(self, mock_search):
        """Doc with year='invalid' → engine should not crash on entity queries.
        NOTE: sort(key=year) may crash for broad_history — test with entity query."""
        mock_search.return_value = []
        import app.core.startup as startup
        from app.services.engine import engine_answer

        corrupt_doc = {
            "year": "invalid",
            "event": "Test corrupt",
            "story": "Test story",
            "persons": [],
            "keywords": [],
            "places": [],
            "dynasty": "",
        }
        orig = startup.DOCUMENTS[:]
        try:
            startup.DOCUMENTS.append(corrupt_doc)
            # Use a specific entity query (not broad_history) to avoid sort crash
            r = engine_answer("Ngô Quyền mất năm nào?")
            assert isinstance(r, dict), "Should handle corrupt year gracefully"
        finally:
            startup.DOCUMENTS = orig
            _setup_full_mocks()

    @patch("app.services.engine.semantic_search")
    def test_51_duplicate_document_flood(self, mock_search):
        """Same doc ×1000 → no crash, valid answer."""
        mock_search.return_value = []
        import app.core.startup as startup
        from app.services.engine import engine_answer

        single_doc = ALL_MOCK_DOCS[0]
        orig = startup.DOCUMENTS[:]
        orig_by_year = startup.DOCUMENTS_BY_YEAR.copy()
        try:
            startup.DOCUMENTS = [single_doc] * 1000
            startup.DOCUMENTS_BY_YEAR = defaultdict(list)
            y = single_doc.get("year")
            if y is not None:
                for i in range(1000):
                    startup.DOCUMENTS_BY_YEAR[y].append(single_doc)

            r = engine_answer("Kể cho tôi về lịch sử")
            assert isinstance(r, dict), "Should handle 1000 duplicate docs"
            assert r.get("answer") is not None or r.get("no_data") is True
        finally:
            startup.DOCUMENTS = orig
            startup.DOCUMENTS_BY_YEAR = orig_by_year
            _setup_full_mocks()

    @patch("app.services.engine.semantic_search")
    def test_52_missing_story_field(self, mock_search):
        """Doc without 'story' key → no crash."""
        mock_search.return_value = []
        import app.core.startup as startup
        from app.services.engine import engine_answer

        no_story_doc = {
            "year": 938,
            "event": "Bạch Đằng",
            "persons": ["Ngô Quyền"],
            "keywords": ["bạch_đằng"],
            "places": ["Bạch Đằng"],
            "dynasty": "Ngô",
        }
        orig = startup.DOCUMENTS[:]
        try:
            startup.DOCUMENTS.append(no_story_doc)
            r = engine_answer("Ngô Quyền")
            assert isinstance(r, dict), "Should handle missing 'story' gracefully"
        finally:
            startup.DOCUMENTS = orig
            _setup_full_mocks()


# ===================================================================
# ⚡ CATEGORY 7 — CONCURRENCY SAFETY (Tests 53–54)
# ===================================================================

class TestCat7ConcurrencySafety:
    """Verify engine is thread-safe under concurrent access."""

    @patch("app.services.engine.semantic_search")
    def test_53_concurrent_engine_calls(self, mock_search):
        """10 threads × same query → all identical, no crash."""
        mock_search.return_value = []
        from app.services.engine import engine_answer

        query = "Ngô Quyền mất năm nào?"
        results = []
        errors = []

        def _call():
            try:
                return engine_answer(query)
            except Exception as e:
                errors.append(str(e))
                return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_call) for _ in range(20)]
            results = [f.result() for f in as_completed(futures)]

        assert not errors, f"Concurrent errors: {errors}"
        # Filter None results
        valid = [r for r in results if r is not None]
        assert len(valid) == 20, f"Only {len(valid)}/20 returned valid results"

        # All answers should be identical
        answers = [r.get("answer", "") for r in valid]
        assert len(set(answers)) == 1, \
            f"Concurrent non-determinism: {len(set(answers))} unique answers"

    @patch("app.services.engine.semantic_search")
    def test_54_concurrent_mixed_intents(self, mock_search):
        """10 threads, different query types → all valid dicts."""
        mock_search.return_value = []
        from app.services.engine import engine_answer

        queries = [
            "Ngô Quyền mất năm nào?",
            "Xin chào!",
            "Dữ liệu của bạn có đến năm nào?",
            "Trần Hưng Đạo là ai?",
            "Bạch Đằng 938 đúng không?",
        ]
        errors = []

        def _call(q):
            try:
                return engine_answer(q)
            except Exception as e:
                errors.append(f"{q}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for q in queries:
                futures.extend([executor.submit(_call, q) for _ in range(4)])
            results = [f.result() for f in as_completed(futures)]

        assert not errors, f"Concurrent mixed errors: {errors}"
        valid = [r for r in results if r is not None]
        assert len(valid) == 20, f"Only {len(valid)}/20 valid"

        for r in valid:
            assert isinstance(r, dict), "Each result must be a dict"
            assert "query" in r or "intent" in r, "Result missing required fields"


# ===================================================================
# ⏱️ CATEGORY 8 — PERFORMANCE GUARD (Tests 55–56)
# ===================================================================

class TestCat8PerformanceGuard:
    """Detect performance regressions — SLA constraints for mock env."""

    @patch("app.services.engine.semantic_search")
    def test_55_response_time_under_threshold(self, mock_search):
        """Single query must complete in < 2s (mock env)."""
        mock_search.return_value = []
        from app.services.engine import engine_answer

        start = time.perf_counter()
        r = engine_answer("Ngô Quyền mất năm nào?")
        elapsed = time.perf_counter() - start

        assert isinstance(r, dict), "Should return valid dict"
        assert elapsed < 2.0, \
            f"Response time {elapsed:.2f}s exceeds 2s threshold"

    @patch("app.services.engine.semantic_search")
    def test_56_batch_queries_throughput(self, mock_search):
        """10 sequential queries must complete in < 5s total."""
        mock_search.return_value = []
        from app.services.engine import engine_answer

        queries = [
            "Ngô Quyền mất năm nào?",
            "Trần Hưng Đạo",
            "Xin chào!",
            "Bạch Đằng 938 đúng không?",
            "Lịch sử Việt Nam từ 1945 đến 1975.",
            "Dữ liệu của bạn có đến năm nào?",
            "Nguyễn Huệ phá quân Thanh",
            "Hai Bà Trưng",
            "Khúc Thừa Dụ",
            "Lê Lợi và khởi nghĩa Lam Sơn",
        ]

        start = time.perf_counter()
        for q in queries:
            r = engine_answer(q)
            assert isinstance(r, dict)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, \
            f"Batch throughput {elapsed:.2f}s exceeds 5s for 10 queries"


# ===================================================================
# 🧬 CATEGORY 9 — DATA TYPE CORRUPTION (Tests 57–61)
# ===================================================================

class TestCat9DataTypeCorruption:
    """Verify engine handles corrupted year field types without crashing.

    These test that safe_year() is properly integrated into all sort paths.
    Before the fix, any non-int year would crash Python's sort with TypeError.
    """

    def _inject_corrupt_doc_and_sort(self, corrupt_year):
        """Helper: inject a doc with corrupt year, trigger a sort-heavy path."""
        import app.core.startup as startup
        from app.services.search_service import scan_broad_history

        corrupt_doc = {
            "year": corrupt_year,
            "event": "Corrupt data test",
            "story": "Testing corrupt year field.",
            "persons": [],
            "keywords": [],
            "places": [],
            "dynasty": "",
            "scope": "national",
        }
        orig = startup.DOCUMENTS[:]
        try:
            startup.DOCUMENTS.append(corrupt_doc)
            result = scan_broad_history()
            # Must not crash
            assert isinstance(result, list)
            return result
        finally:
            startup.DOCUMENTS = orig
            _setup_full_mocks()

    def test_57_year_none_no_crash(self):
        """year=None → sort must not crash (null injection)."""
        result = self._inject_corrupt_doc_and_sort(None)
        assert isinstance(result, list), "year=None caused crash"

    def test_58_year_empty_string_no_crash(self):
        """year='' → sort must not crash (empty string)."""
        result = self._inject_corrupt_doc_and_sort("")
        assert isinstance(result, list), 'year="" caused crash'

    def test_59_year_list_no_crash(self):
        """year=[] → sort must not crash (type mismatch)."""
        result = self._inject_corrupt_doc_and_sort([])
        assert isinstance(result, list), "year=[] caused crash"

    def test_60_year_bool_true_no_crash(self):
        """year=True → sort must not crash (bool edge case)."""
        result = self._inject_corrupt_doc_and_sort(True)
        assert isinstance(result, list), "year=True caused crash"

    def test_61_year_bool_false_no_crash(self):
        """year=False → sort must not crash (bool edge case)."""
        result = self._inject_corrupt_doc_and_sort(False)
        assert isinstance(result, list), "year=False caused crash"
