"""
E2E API Tests for Vietnam History AI Service.
Tests the /api/chat endpoint with real queries and verifies response format.
"""

import pytest
from fastapi.testclient import TestClient

# Import app for testing
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai-service'))

from app.main import app


client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_returns_200_immediately(self):
        """Health endpoint should return 200 even if model not fully loaded."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_health_detailed_returns_structure(self):
        """Detailed health should return proper structure."""
        response = client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "faiss" in data
        assert "documents" in data
        assert "ready" in data


class TestChatAPI:
    """Test /api/chat endpoint."""
    
    def test_chat_with_year_query(self):
        """Query with year should return events for that year."""
        response = client.post("/api/chat", json={"query": "năm 1945"})
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "query" in data
        assert "intent" in data
        assert "answer" in data
        assert "events" in data
        assert "no_data" in data
    
    def test_chat_with_identity_query(self):
        """Identity query should return identity response."""
        response = client.post("/api/chat", json={"query": "bạn là ai"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["intent"] == "identity"
        assert "History Mind" in data["answer"] or "HistoryMind" in data["answer"].replace(" ", "")
    
    def test_chat_no_duplicate_events(self):
        """Events in response should not be duplicated."""
        response = client.post("/api/chat", json={"query": "năm 1911"})
        assert response.status_code == 200
        data = response.json()
        
        events = data.get("events", [])
        if len(events) > 1:
            # Check no duplicate event texts
            event_texts = [e.get("event", "") for e in events]
            unique_texts = set(event_texts)
            assert len(unique_texts) == len(event_texts), f"Found duplicate events: {event_texts}"
    
    def test_chat_max_events_limit(self):
        """Should not return more than MAX_TOTAL_EVENTS."""
        response = client.post("/api/chat", json={"query": "lịch sử việt nam"})
        assert response.status_code == 200
        data = response.json()
        
        events = data.get("events", [])
        # MAX_TOTAL_EVENTS is 5 according to engine.py
        assert len(events) <= 5, f"Too many events returned: {len(events)}"
    
    def test_chat_empty_query(self):
        """Empty query should be handled gracefully."""
        response = client.post("/api/chat", json={"query": ""})
        # Should not crash
        assert response.status_code in [200, 422]


class TestAPIEdgeCases:
    """Test edge cases and error handling."""
    
    def test_missing_query_field(self):
        """Request without query field should return 422."""
        response = client.post("/api/chat", json={})
        assert response.status_code == 422
    
    def test_invalid_json(self):
        """Invalid JSON should return 422."""
        response = client.post(
            "/api/chat",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_special_characters_in_query(self):
        """Query with special characters should be handled."""
        response = client.post("/api/chat", json={"query": "năm 1945!@#$%"})
        # Should not crash
        assert response.status_code == 200
