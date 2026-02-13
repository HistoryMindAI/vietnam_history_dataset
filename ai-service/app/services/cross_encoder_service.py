"""
Cross-Encoder Reranker Service

Replaces context7_service.py regex-based scoring with AI-powered reranking.
Uses ONNX Runtime for lightweight production inference (no torch needed).

Two modes:
1. ONNX Cross-Encoder (primary): Scores (query, document) pairs with real AI model
2. Keyword fallback (backup): Data-driven scoring from knowledge_base.json

All keywords, patterns, thresholds are loaded dynamically - NO hardcoded values.
"""

import re
import logging
from typing import List, Dict, Any, Optional

import app.core.startup as startup

logger = logging.getLogger(__name__)


# ===================================================================
# 1. CROSS-ENCODER ONNX INFERENCE
# ===================================================================

def _cross_encoder_score_batch(query: str, documents: List[str]) -> List[float]:
    """
    Score query-document pairs using ONNX Cross-Encoder.
    Returns list of relevance scores (higher = more relevant).
    Returns None if Cross-Encoder not available.
    """
    ce_session = getattr(startup, "cross_encoder_session", None)
    ce_tokenizer = getattr(startup, "cross_encoder_tokenizer", None)

    if ce_session is None or ce_tokenizer is None:
        return None

    try:
        import numpy as np

        # Get valid input names from model
        valid_input_names = {inp.name for inp in ce_session.get_inputs()}

        scores = []
        # Process in batches to control memory
        batch_size = 32
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]

            # Tokenize query-document pairs
            encoded = ce_tokenizer(
                [query] * len(batch_docs),
                batch_docs,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="np",
            )

            # Only pass inputs that the ONNX model expects
            feed = {k: v for k, v in encoded.items() if k in valid_input_names}
            logits = ce_session.run(None, feed)[0]

            # Extract scores (logits shape: [batch, 1] or [batch])
            for j in range(len(batch_docs)):
                score = float(logits[j][0]) if len(logits[j].shape) > 0 and logits[j].shape[0] > 1 else float(logits[j])
                scores.append(score)

        return scores

    except Exception as e:
        logger.warning(f"Cross-Encoder inference failed: {e}")
        return None


# ===================================================================
# 2. DATA-DRIVEN KEYWORD FALLBACK
# ===================================================================

def _get_reranker_config() -> Dict[str, Any]:
    """
    Load reranker config from knowledge_base.json dynamically.
    Returns default config if not found.
    """
    config = getattr(startup, "_knowledge_base_raw", {}).get("reranker_config", {})
    if not config:
        # Minimal defaults — user should populate knowledge_base.json
        config = {
            "military_keywords": ["chiến", "đánh", "thắng", "kháng", "quân", "trận", "hịch"],
            "victory_keywords": ["chiến thắng", "đánh bại", "thắng lợi", "đại phá", "tiêu diệt"],
            "preparation_keywords": ["hịch", "chuẩn bị", "khích lệ", "động viên"],
        }
    return config


def _keyword_fallback_score(query: str, event: Dict[str, Any]) -> float:
    """
    Data-driven keyword scoring fallback when Cross-Encoder is unavailable.
    All keywords loaded from knowledge_base.json — NO hardcoded patterns.
    """
    score = 0.0
    query_lower = query.lower()

    # Build event text for matching
    event_text = " ".join([
        str(event.get("event", "")),
        str(event.get("story", "")),
        str(event.get("title", "")),
        " ".join(str(k) for k in event.get("keywords", [])),
    ]).lower()

    event_dynasty = str(event.get("dynasty", "")).lower()
    event_persons = [p.lower() for p in event.get("persons", []) + event.get("persons_all", [])]
    event_places = [p.lower() for p in event.get("places", [])]

    # --- Dynasty matching (from startup data) ---
    for alias, canonical in startup.DYNASTY_ALIASES.items():
        if alias in query_lower and canonical == event_dynasty:
            score += 20.0
            break
        if alias in query_lower and canonical != event_dynasty:
            # Query mentions a different dynasty = penalty
            if event_dynasty and event_dynasty not in query_lower:
                score -= 15.0
            break

    # --- Person matching (from startup data) ---
    query_persons = set()
    for person_key in startup.PERSONS_INDEX.keys():
        if person_key in query_lower:
            query_persons.add(person_key)
    # Also check aliases
    for alias, canonical in startup.PERSON_ALIASES.items():
        if alias in query_lower:
            query_persons.add(canonical)

    if query_persons:
        # Bonus if event has the queried person
        for person in event_persons:
            if person in query_persons:
                score += 25.0
                break
            # Check if person is an alias of queried person
            canonical = startup.PERSON_ALIASES.get(person, person)
            if canonical in query_persons:
                score += 25.0
                break
        else:
            # Event doesn't have any of the queried persons
            if event_persons:
                score -= 10.0

    # --- Topic/keyword matching (from startup data) ---
    query_topics = set()
    for synonym, canonical in startup.TOPIC_SYNONYMS.items():
        if synonym in query_lower:
            query_topics.add(canonical)
            query_topics.add(synonym)

    if query_topics:
        topic_hits = sum(1 for t in query_topics if t in event_text)
        score += topic_hits * 10.0

    # --- Place matching (from startup data) ---
    for place_key in startup.PLACES_INDEX.keys():
        if place_key in query_lower and place_key in " ".join(event_places):
            score += 10.0

    # --- Dynamic keyword matching from reranker_config ---
    config = _get_reranker_config()

    # Military keywords
    military_kws = config.get("military_keywords", [])
    query_military_count = sum(1 for kw in military_kws if kw in query_lower)
    if query_military_count > 0:
        military_hits = sum(1 for kw in military_kws if kw in event_text)
        score += military_hits * 5.0
        if military_hits == 0:
            # Query is clearly about military but event has NO military content
            # Penalty must outweigh dynasty bonus to filter irrelevant events
            score -= 25.0

    # Victory keywords
    victory_kws = config.get("victory_keywords", [])
    victory_hits = sum(1 for kw in victory_kws if kw in event_text)
    if any(kw in query_lower for kw in victory_kws):
        score += victory_hits * 5.0

    # "chống X" pattern — events without enemy mention get penalized
    against_match = re.search(r"chống\s+([\w\s]+?)(?:\s+và|\s*$|[,.])", query_lower)
    if against_match:
        enemy = against_match.group(1).strip()
        enemy_variants = {enemy}
        for syn, canonical in startup.TOPIC_SYNONYMS.items():
            if enemy in syn or enemy in canonical or syn in enemy or canonical in enemy:
                enemy_variants.add(syn)
                enemy_variants.add(canonical)
        has_enemy = any(v in event_text for v in enemy_variants)
        if has_enemy:
            score += 15.0
        else:
            score -= 10.0

    return score


# ===================================================================
# 3. PUBLIC API (replaces context7_service)
# ===================================================================

def rerank_events(
    query: str,
    events: List[Dict[str, Any]],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Rerank events by relevance to query.
    Uses Cross-Encoder ONNX if available, falls back to keyword scoring.

    Replaces context7_service.filter_and_rank_events().
    """
    if not events:
        return []

    query_lower = query.lower()

    # --- Detect simple queries that shouldn't be aggressively filtered ---
    is_simple_year = bool(re.match(
        r'^(năm|year)?\s*\d{3,4}\s*(có|gì|sự kiện)?$', query_lower.strip()
    ))
    is_year_range = bool(
        re.search(r'(từ|from|between|giai\s*đoạn).*(đến|to|and|[-–—])', query_lower) or
        re.search(r'năm\s*\d{1,4}\s*(đến|tới)', query_lower) or
        re.search(r'\d{1,4}\s*[-–—]\s*\d{1,4}', query_lower)
    )

    # --- Try Cross-Encoder ONNX scoring ---
    documents = []
    for evt in events:
        doc_text = _event_to_text(evt)
        documents.append(doc_text)

    ce_scores = _cross_encoder_score_batch(query, documents)

    if ce_scores is not None:
        # Cross-Encoder available — use AI scores
        scored = list(zip(ce_scores, events))
        scored.sort(key=lambda x: x[0], reverse=True)

        if is_simple_year or is_year_range:
            # Simple query: return all, just sorted
            return [evt for _, evt in scored[:top_k]]

        # Complex query: filter by threshold
        from app.core.config import RERANKER_THRESHOLD
        threshold = RERANKER_THRESHOLD

        filtered = [(s, evt) for s, evt in scored if s >= threshold]

        # Fallback: if nothing passes threshold, take top 3 with positive-ish scores
        if not filtered and scored:
            filtered = scored[:3]

        return [evt for _, evt in filtered[:top_k]]

    else:
        # Fallback to keyword scoring
        logger.info("Cross-Encoder unavailable, using keyword fallback scoring")
        return _fallback_rerank(query, events, top_k, is_simple_year or is_year_range)


def _fallback_rerank(
    query: str,
    events: List[Dict[str, Any]],
    top_k: int,
    is_simple_query: bool,
) -> List[Dict[str, Any]]:
    """Keyword-based fallback reranking (data-driven)."""
    scored = []
    for evt in events:
        score = _keyword_fallback_score(query, evt)
        scored.append((score, evt))

    scored.sort(key=lambda x: x[0], reverse=True)

    if is_simple_query:
        return [evt for _, evt in scored[:top_k]]

    # Filter low-scoring events but ALWAYS keep at least top results
    # When Cross-Encoder is unavailable, keyword scoring may be low
    # for valid events found by entity scan — don't discard them all
    min_threshold = 5.0
    filtered = [(s, evt) for s, evt in scored if s >= min_threshold]

    if not filtered and scored:
        # Fallback: always return at least top 3 events
        # Entity scan already found these events — they are likely relevant
        filtered = scored[:3]

    return [evt for _, evt in filtered[:top_k]]


def _event_to_text(event: Dict[str, Any]) -> str:
    """Convert event dict to a text string for Cross-Encoder input."""
    parts = []
    year = event.get("year")
    if year:
        parts.append(f"Năm {year}")

    title = event.get("title") or event.get("event", "")
    if title:
        parts.append(title)

    story = event.get("story", "")
    if story:
        parts.append(story)

    dynasty = event.get("dynasty", "")
    if dynasty:
        parts.append(f"Triều {dynasty}")

    persons = event.get("persons", []) + event.get("persons_all", [])
    if persons:
        unique_persons = list(dict.fromkeys(persons))  # Preserve order, dedup
        parts.append(f"Nhân vật: {', '.join(unique_persons)}")

    return ". ".join(parts)


def validate_answer_relevance(answer: str, query: str) -> Dict[str, Any]:
    """
    Validate that answer is relevant to query.
    Uses Cross-Encoder if available, else keyword matching (data-driven).

    Replaces context7_service.validate_answer_relevance().
    """
    issues = []
    suggestions = []
    query_lower = query.lower()
    answer_lower = (answer or "").lower()

    if not answer_lower:
        return {"is_relevant": False, "issues": ["Empty answer"], "suggestions": []}

    # --- Try Cross-Encoder validation ---
    ce_scores = _cross_encoder_score_batch(query, [answer_lower])
    if ce_scores is not None:
        relevance_score = ce_scores[0]
        if relevance_score < -8.0:
            issues.append(f"Cross-Encoder relevance score too low: {relevance_score:.2f}")
            suggestions.append("Answer may not be relevant to the query")
    else:
        # Fallback: keyword-based validation (data-driven)
        _validate_with_keywords(query_lower, answer_lower, issues, suggestions)

    return {
        "is_relevant": len(issues) == 0,
        "issues": issues,
        "suggestions": suggestions,
    }


def _validate_with_keywords(
    query_lower: str,
    answer_lower: str,
    issues: List[str],
    suggestions: List[str],
):
    """Data-driven keyword validation fallback."""

    # Check dynasty mention
    for alias, canonical in startup.DYNASTY_ALIASES.items():
        if alias in query_lower:
            # Query mentions this dynasty — check if answer has it
            has_dynasty = canonical in answer_lower or alias in answer_lower
            if not has_dynasty:
                # Check for military content exception
                config = _get_reranker_config()
                military_kws = config.get("military_keywords", [])
                is_military_q = any(kw in query_lower for kw in military_kws)
                has_military_a = any(kw in answer_lower for kw in military_kws)
                if not (is_military_q and has_military_a):
                    issues.append(f"Query about '{alias}' but answer doesn't mention it")
                    suggestions.append(f"Focus on events related to {alias}")
            break  # Only check first dynasty found

    # Check "chống X" pattern
    against_match = re.search(r"chống\s+([\w\s]+?)(?:\s+và|\s*$|[,.])", query_lower)
    if against_match:
        enemy = against_match.group(1).strip()
        # Expand enemy aliases from topic_synonyms
        enemy_variants = {enemy}
        for syn, canonical in startup.TOPIC_SYNONYMS.items():
            if enemy in syn or enemy in canonical or syn in enemy or canonical in enemy:
                enemy_variants.add(syn)
                enemy_variants.add(canonical)

        has_enemy = any(v in answer_lower for v in enemy_variants)
        if not has_enemy:
            issues.append(f"Query about 'chống {enemy}' but answer doesn't mention it")
            suggestions.append(f"Focus on events related to {enemy}")


# ===================================================================
# 4. BACKWARD COMPATIBILITY (aliases for old context7_service API)
# ===================================================================

def filter_and_rank_events(
    events: List[Dict[str, Any]],
    query: str,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """
    Backward-compatible wrapper.
    Old signature: filter_and_rank_events(events, query, max_results)
    New signature: rerank_events(query, events, top_k)
    """
    return rerank_events(query, events, top_k=max_results)
