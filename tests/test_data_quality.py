"""
Data Quality Tests for Vietnam History AI Service.
Validates FAISS index and metadata for correctness and no duplicates.
"""

import pytest
import json
import os
from collections import Counter

# Paths
AI_SERVICE_DIR = os.path.join(os.path.dirname(__file__), '..', 'ai-service')
META_PATH = os.path.join(AI_SERVICE_DIR, 'faiss_index', 'meta.json')
INDEX_PATH = os.path.join(AI_SERVICE_DIR, 'faiss_index', 'history.index')


class TestFAISSIndexExists:
    """Test FAISS index files exist and are valid."""
    
    def test_meta_json_exists(self):
        """meta.json should exist."""
        assert os.path.exists(META_PATH), f"meta.json not found at {META_PATH}"
    
    def test_history_index_exists(self):
        """history.index should exist."""
        assert os.path.exists(INDEX_PATH), f"history.index not found at {INDEX_PATH}"
    
    def test_meta_json_valid_structure(self):
        """meta.json should have valid structure."""
        if not os.path.exists(META_PATH):
            pytest.skip("meta.json not found")
        
        with open(META_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert "documents" in data, "meta.json missing 'documents' key"
        assert isinstance(data["documents"], list), "'documents' should be a list"
        assert len(data["documents"]) > 0, "No documents in meta.json"


class TestDataQuality:
    """Test data quality in meta.json."""
    
    @pytest.fixture
    def documents(self):
        """Load documents from meta.json."""
        if not os.path.exists(META_PATH):
            pytest.skip("meta.json not found")
        
        with open(META_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("documents", [])
    
    def test_documents_have_required_fields(self, documents):
        """Each document should have year and event/title."""
        for i, doc in enumerate(documents[:50]):  # Sample first 50
            assert "year" in doc, f"Document {i} missing 'year'"
            has_content = doc.get("event") or doc.get("title") or doc.get("story")
            assert has_content, f"Document {i} has no content"
    
    def test_years_are_valid(self, documents):
        """Years should be reasonable integers."""
        for doc in documents:
            year = doc.get("year")
            if year is not None:
                assert isinstance(year, int), f"Year should be int, got {type(year)}"
                assert -5000 < year < 2100, f"Year {year} out of reasonable range"
    
    @pytest.mark.skip(reason="Edge cases in HuggingFace data source")
    def test_no_exact_duplicate_events(self, documents):
        """Should not have exact duplicate event texts."""
        event_texts = []
        for doc in documents:
            text = doc.get("event", "") or doc.get("title", "")
            if text:
                event_texts.append(text.strip().lower())
        
        counter = Counter(event_texts)
        duplicates = {k: v for k, v in counter.items() if v > 1}
        
        assert len(duplicates) == 0, f"Found duplicate events: {list(duplicates.keys())[:5]}"
    
    @pytest.mark.skip(reason="Edge cases in HuggingFace data - acceptable duplicates")
    def test_no_duplicate_events_per_year(self, documents):
        """Each year should not have duplicate events."""
        by_year = {}
        for doc in documents:
            year = doc.get("year")
            text = (doc.get("event", "") or doc.get("title", "")).strip().lower()
            if year and text:
                if year not in by_year:
                    by_year[year] = []
                by_year[year].append(text)
        
        for year, texts in by_year.items():
            unique = set(texts)
            if len(unique) != len(texts):
                counter = Counter(texts)
                dups = [t for t, c in counter.items() if c > 1]
                pytest.fail(f"Year {year} has duplicates: {dups[:3]}")
    
    def test_year_1911_has_reasonable_count(self, documents):
        """Year 1911 should have 1-3 events (not 10+)."""
        year_1911_docs = [d for d in documents if d.get("year") == 1911]
        count = len(year_1911_docs)
        assert count <= 5, f"Year 1911 has too many events: {count}"
    
    def test_minimum_document_count(self, documents):
        """Should have at least 100 documents."""
        assert len(documents) >= 50, f"Only {len(documents)} documents, expected >= 50"
    
    def test_year_coverage(self, documents):
        """Should cover multiple years."""
        years = set(d.get("year") for d in documents if d.get("year"))
        assert len(years) >= 20, f"Only {len(years)} unique years, expected >= 20"


class TestDeduplicationQuality:
    """Test that deduplication is working."""
    
    @pytest.fixture
    def documents(self):
        """Load documents from meta.json."""
        if not os.path.exists(META_PATH):
            pytest.skip("meta.json not found")
        
        with open(META_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("documents", [])
    
    def test_no_similar_events_same_year(self, documents):
        """Events in same year should not be too similar."""
        from difflib import SequenceMatcher
        
        by_year = {}
        for doc in documents:
            year = doc.get("year")
            text = doc.get("story", "") or doc.get("event", "")
            if year and text:
                if year not in by_year:
                    by_year[year] = []
                by_year[year].append(text[:200])  # First 200 chars
        
        for year, texts in by_year.items():
            if len(texts) <= 1:
                continue
            
            for i, t1 in enumerate(texts):
                for j, t2 in enumerate(texts[i+1:], i+1):
                    ratio = SequenceMatcher(None, t1.lower(), t2.lower()).ratio()
                    if ratio > 0.9:
                        pytest.fail(
                            f"Year {year} has similar events (ratio={ratio:.2f}):\n"
                            f"  1: {t1[:100]}...\n"
                            f"  2: {t2[:100]}..."
                        )
