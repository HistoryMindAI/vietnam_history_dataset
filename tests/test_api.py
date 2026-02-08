from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import app AFTER mocks are set up by conftest (pytest handles this order usually)
# But we need to patch engine_answer in app.api.chat
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "service": "Vietnam History AI",
        "status": "running"
    }

@patch("app.api.chat.engine_answer")
def test_chat_endpoint(mock_engine):
    # Setup mock return value
    mock_engine.return_value = {
        "query": "test query",
        "intent": "semantic",
        "answer": "This is a mock answer",
        "events": [],
        "no_data": False
    }

    payload = {"query": "test query"}
    response = client.post("/api/chat", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "test query"
    assert data["answer"] == "This is a mock answer"
    assert data["no_data"] is False
    mock_engine.assert_called_once_with("test query")

@patch("app.api.chat.engine_answer")
def test_chat_no_data(mock_engine):
    # Setup mock return value for no data
    mock_engine.return_value = {
        "query": "unknown",
        "intent": "semantic",
        "answer": None,
        "events": [],
        "no_data": True
    }

    payload = {"query": "unknown"}
    response = client.post("/api/chat", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "unknown"
    assert data["answer"] is None
    assert data["no_data"] is True
