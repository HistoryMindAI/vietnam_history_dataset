import pytest
from app.services.confidence_scorer import score_events, should_answer, safe_fallback, compute_final_score

def test_score_events_empty():
    assert score_events([]) == []

def test_score_events_without_nli():
    events = [{"_rerank_score": 2.0}]
    ans = score_events(events)
    assert "_final_confidence" in ans[0]

def test_score_events_with_nli():
    events = [{"_rerank_score": 2.0, "_nli_entailment": 0.8}]
    ans = score_events(events)
    assert "_final_confidence" in ans[0]

def test_calculate_score():
    assert compute_final_score({}) == -1.0
    ans = compute_final_score({"_rerank_score": 2.0})
    assert ans > 0.5
    ans = compute_final_score({"_nli_entailment": 0.9})
    assert ans == 0.66

def test_confidence_gate_empty():
    assert should_answer([]) is False

def test_confidence_gate_structural_match():
    # Bypass
    events = [{"year": 1911}]
    assert should_answer(events, intent="person_query") is True

def test_confidence_gate_no_scores():
    events = [{"year": 1911, "_final_confidence": -1.0}]
    assert should_answer(events, intent="other") is False

def test_confidence_gate_below_threshold():
    events = [{"year": 1911, "_final_confidence": 0.1}]
    assert should_answer(events, threshold=0.5, intent="other") is False

def test_confidence_gate_above_threshold():
    events = [{"year": 1911, "_final_confidence": 0.9}]
    assert should_answer(events, threshold=0.5, intent="other") is True


def test_safe_fallback():
    res = safe_fallback()
    assert "chưa tìm được thông tin" in res["answer"]
def test_compute_final_score_neutral_rerank():
    ans = compute_final_score({"_rerank_score": 0.0, "_nli_entailment": 0.9})
    assert ans > 0.0
