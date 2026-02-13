"""
NLI Answer Validator Service — Multilingual Natural Language Inference.

Uses a lightweight multilingual NLI ONNX model to verify that retrieved
events actually answer the user's question (entailment check).

Pipeline position:
  Query → Search → Cross-Encoder Rerank → **NLI Validate** → Format Answer

Model: MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli
Labels: entailment (0), neutral (1), contradiction (2)
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from app.core import startup

logger = logging.getLogger(__name__)

# Label indices from model config
ENTAILMENT_IDX = 0
NEUTRAL_IDX = 1
CONTRADICTION_IDX = 2


def _nli_score_batch(
    premises: List[str], hypotheses: List[str]
) -> Optional[List[Tuple[float, float, float]]]:
    """
    Score premise-hypothesis pairs using NLI ONNX model.
    Returns list of (entailment, neutral, contradiction) probability tuples,
    or None if NLI model is not available.
    """
    nli_session = getattr(startup, "nli_session", None)
    nli_tokenizer = getattr(startup, "nli_tokenizer", None)

    if nli_session is None or nli_tokenizer is None:
        return None

    try:
        import numpy as np

        valid_input_names = {inp.name for inp in nli_session.get_inputs()}
        results = []
        batch_size = 16

        for i in range(0, len(premises), batch_size):
            batch_premises = premises[i : i + batch_size]
            batch_hypotheses = hypotheses[i : i + batch_size]

            encoded = nli_tokenizer(
                batch_premises,
                batch_hypotheses,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="np",
            )

            feed = {k: v for k, v in encoded.items() if k in valid_input_names}
            logits = nli_session.run(None, feed)[0]  # shape: (batch, 3)

            # Softmax to get probabilities
            for j in range(len(batch_premises)):
                row = logits[j]
                exp_row = np.exp(row - np.max(row))
                probs = exp_row / exp_row.sum()
                results.append(
                    (float(probs[ENTAILMENT_IDX]),
                     float(probs[NEUTRAL_IDX]),
                     float(probs[CONTRADICTION_IDX]))
                )

        return results

    except Exception as e:
        logger.warning(f"NLI inference failed: {e}")
        return None


def _event_to_premise(event: Dict[str, Any]) -> str:
    """Convert event dict to a text string for NLI premise."""
    parts = []
    year = event.get("year")
    if year:
        parts.append(f"Năm {year}")

    title = event.get("title") or event.get("event", "")
    if title:
        parts.append(title)

    story = event.get("story", "")
    if story:
        # Truncate long stories to fit model context
        parts.append(story[:300])

    return ". ".join(parts) if parts else ""


def validate_events_nli(
    query: str,
    events: List[Dict[str, Any]],
    threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Filter events using NLI: keep only events where the event text
    ENTAILS (supports) the user's question.

    Args:
        query: User's question (used as hypothesis)
        events: List of event dicts from search/reranking
        threshold: Minimum entailment probability to keep an event

    Returns:
        Filtered list of events (with NLI scores attached)
    """
    if not events:
        return events

    # Convert events to premise texts
    premises = []
    valid_indices = []
    for idx, event in enumerate(events):
        text = _event_to_premise(event)
        if text:
            premises.append(text)
            valid_indices.append(idx)

    if not premises:
        return events

    # Build hypotheses: the question is what we want events to entail
    # NLI convention: premise = evidence, hypothesis = claim
    # "Does the event (premise) support answering the question (hypothesis)?"
    hypotheses = [query] * len(premises)

    # Get NLI scores
    nli_results = _nli_score_batch(premises, hypotheses)
    if nli_results is None:
        # NLI not available — pass through unchanged
        return events

    # Filter by entailment threshold
    filtered = []
    for i, (entail, neutral, contradict) in enumerate(nli_results):
        event_idx = valid_indices[i]
        event = events[event_idx].copy()

        # Store NLI scores for debugging
        event["_nli_entailment"] = round(entail, 4)
        event["_nli_neutral"] = round(neutral, 4)
        event["_nli_contradiction"] = round(contradict, 4)

        # Keep if entailment probability is above threshold
        # OR if entailment > contradiction (weakly relevant is better than nothing)
        if entail >= threshold or (entail > contradict and entail >= 0.2):
            filtered.append(event)

    # Safety: if NLI filters everything out, return top events by entailment score
    # This prevents empty results when the model is too aggressive
    if not filtered and events:
        scored = list(zip(valid_indices, nli_results))
        scored.sort(key=lambda x: x[1][0], reverse=True)  # Sort by entailment
        top_n = min(3, len(scored))
        for idx, (ent, neu, con) in scored[:top_n]:
            event = events[idx].copy()
            event["_nli_entailment"] = round(ent, 4)
            event["_nli_neutral"] = round(neu, 4)
            event["_nli_contradiction"] = round(con, 4)
            filtered.append(event)

    return filtered


def validate_answer_with_nli(answer: str, query: str) -> Dict[str, Any]:
    """
    Validate final answer text against the query using NLI.
    Returns relevance assessment.
    """
    if not answer:
        return {"is_relevant": False, "entailment": 0.0, "reason": "Empty answer"}

    # Truncate answer for NLI model (max ~500 chars)
    answer_truncated = answer[:500]

    nli_results = _nli_score_batch([answer_truncated], [query])
    if nli_results is None:
        return {"is_relevant": True, "entailment": None, "reason": "NLI not available"}

    entail, neutral, contradict = nli_results[0]
    is_relevant = entail >= 0.3 or entail > contradict

    return {
        "is_relevant": is_relevant,
        "entailment": round(entail, 4),
        "neutral": round(neutral, 4),
        "contradiction": round(contradict, 4),
        "reason": "entailment_check",
    }
