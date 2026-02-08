"""
test_api.py - Unit tests for FastAPI endpoints

Tests the health check, root, and chat endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock


# Fixture to create test client
@pytest.fixture(scope="module")
def test_client():
    """Create test client with mocked startup dependencies."""
    # Mock the startup module before importing app
    with patch("app.core.startup.DOCUMENTS", [{"year": 1945, "event": "Test"}]):
        with patch("app.core.startup.DOCUMENTS_BY_YEAR", {1945: [{"year": 1945, "event": "Test"}]}):
            with patch("app.core.startup.index", MagicMock(ntotal=100)):
                with patch("app.core.startup.embedder", MagicMock()):
                    # Import after mocking
                    from fastapi.testclient import TestClient
                    from app.main import app
                    
                    client = TestClient(app)
                    yield client


def test_health(test_client):
    """Test basic health endpoint."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(test_client):
    """Test root endpoint returns service info."""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Vietnam History AI"
    assert data["status"] == "running"


@patch("app.api.chat.engine_answer")
def test_chat_endpoint_success(mock_engine, test_client):
    """Test chat endpoint with valid query."""
    mock_engine.return_value = {
        "query": "test query",
        "intent": "semantic",
        "answer": "This is a mock answer",
        "events": [],
        "no_data": False
    }

    payload = {"query": "test query"}
    response = test_client.post("/api/chat", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "test query"
    assert data["answer"] == "This is a mock answer"
    assert data["no_data"] is False
    mock_engine.assert_called_once_with("test query")


@patch("app.api.chat.engine_answer")
def test_chat_endpoint_no_data(mock_engine, test_client):
    """Test chat endpoint when no data found."""
    mock_engine.return_value = {
        "query": "unknown topic",
        "intent": "semantic",
        "answer": None,
        "events": [],
        "no_data": True
    }

    payload = {"query": "unknown topic"}
    response = test_client.post("/api/chat", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["no_data"] is True


@patch("app.api.chat.engine_answer")
def test_chat_endpoint_empty_query(mock_engine, test_client):
    """Test chat endpoint with empty query."""
    mock_engine.return_value = {
        "query": "",
        "intent": "unknown",
        "answer": None,
        "events": [],
        "no_data": True
    }

    payload = {"query": ""}
    response = test_client.post("/api/chat", json=payload)
    
    # Should still return 200 with no_data=True
    assert response.status_code == 200
