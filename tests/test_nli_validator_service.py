import pytest
from unittest.mock import patch, MagicMock
from app.services.nli_validator_service import _nli_score_batch, validate_events_nli, validate_answer_with_nli, _event_to_premise
import app.core.startup as startup

def test_nli_score_batch_success():
    with patch("app.services.nli_validator_service.startup.nli_session") as mock_nli, \
         patch("app.services.nli_validator_service.startup.nli_tokenizer") as mock_tokenizer:

        mock_tokenizer.return_value = {"input_ids": [[1]], "attention_mask": [[1]]}
        mock_nli.get_inputs.return_value = [MagicMock(name="input_ids"), MagicMock(name="attention_mask")]
        import numpy as np
        # Logits for entailment, neutral, contradiction
        mock_nli.run.return_value = [np.array([[2.0, 0.5, 0.1], [1.0, 1.0, 1.0]])]

        premises = ["Premise 1", "Premise 2"]
        hypotheses = ["Hyp 1", "Hyp 2"]

        res = _nli_score_batch(premises, hypotheses)
        assert res is not None
        assert len(res) == 2
        # Check softmax applied

def test_nli_score_batch_error():
    with patch("app.services.nli_validator_service.startup.nli_session", side_effect=Exception("Test Error")):
        res = _nli_score_batch(["a"], ["b"])
        assert res is None

def test_validate_events_empty():
    assert validate_events_nli("query", []) == []

def test_validate_events_no_valid_premises():
    # Pass event without content
    events = [{"year": 1911}]
    assert validate_events_nli("query", events) == events

def test_validate_events_nli_not_available():
    events = [{"story": "Loc 1", "title": "T1", "year": 1911}]
    with patch("app.services.nli_validator_service._nli_score_batch", return_value=None):
        ans = validate_events_nli("query", events)
        assert len(ans) == 1

def test_validate_events_filter():
    events = [{"story": "Good"}, {"story": "Bad"}]
    # First is entail, second is contradict
    with patch("app.services.nli_validator_service._nli_score_batch", return_value=[(0.9, 0.05, 0.05), (0.1, 0.1, 0.8)]):
        ans = validate_events_nli("query", events)
        assert len(ans) == 1
        assert ans[0]["story"] == "Good"

def test_validate_answer_empty():
    ans = validate_answer_with_nli("", "query")
    assert ans["is_relevant"] is False

def test_validate_answer_nli_not_available():
    with patch("app.services.nli_validator_service._nli_score_batch", return_value=None):
        ans = validate_answer_with_nli("query", "Answer")
        assert ans["is_relevant"] is True
        assert ans["entailment"] is None

def test_validate_answer_nli_success():
    with patch("app.services.nli_validator_service._nli_score_batch", return_value=[(0.8, 0.1, 0.1)]):
        ans = validate_answer_with_nli("query", "Answer")
        assert ans["is_relevant"] is True
        assert ans["entailment"] == 0.8

def test_nli_score_batch_exception():
    with patch("app.services.nli_validator_service.startup.nli_session") as mock_nli, \
         patch("app.services.nli_validator_service.startup.nli_tokenizer") as mock_tokenizer:
        mock_nli.get_inputs.side_effect = Exception("Test Exception")
        res = _nli_score_batch(["a"], ["b"])
        assert res is None

def test_validate_events_all_filtered():
    events = [{"story": "Bad 1"}, {"story": "Bad 2"}]
    with patch("app.services.nli_validator_service._nli_score_batch", return_value=[(0.01, 0.01, 0.98), (0.01, 0.01, 0.98)]):
        ans = validate_events_nli("query", events)
        assert len(ans) == 2 # Top N returned if all filtered
def test_validate_events_no_valid_texts():
    events = [{"year": 1911}]
    ans = validate_events_nli("query", events)
    assert len(ans) == 1

def test_validate_events_no_valid_premises():
    events = [{"year": 1911, "title": ""}] # empty string will evaluate to false in _event_to_premise
    ans = validate_events_nli("query", events)
    assert len(ans) == 1

def test_validate_events_no_valid_premises_2():
    events = [{"something_else": 1911}]
    ans = validate_events_nli("query", events)
    assert len(ans) == 1
