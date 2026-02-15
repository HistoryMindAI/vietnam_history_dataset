"""
confidence_scorer.py — Final Confidence Gate (Phase 1 / Giai đoạn 11)

PURPOSE:
    Tính điểm tin cậy cuối cùng cho các candidate events.
    Nếu score < threshold → từ chối trả lời (trả safe_fallback).
    ĐÂY LÀ CÁCH GIẢM SAI MẠNH NHẤT — không cố trả lời khi không chắc chắn.

CONTEXT:
    - TRƯỚC ĐÂY: Không có confidence gate — engine luôn trả lời dù score thấp
    - BÂY GIỜ: Kết hợp rerank_score + entailment_score → final gate

RELATED OLD FILES:
    - cross_encoder_service.py → rerank_events() gắn _rerank_score vào event
    - nli_validator_service.py → validate_events_nli() gắn _nli_entailment vào event
    - config.py → sẽ thêm CONFIDENCE_THRESHOLD, RERANK_WEIGHT, ENTAILMENT_WEIGHT

PIPELINE POSITION:
    Rerank → NLI → Hard Filter → **Confidence Scoring** → Answer Build

FORMULA:
    final_score = rerank_score * 0.6 + entailment_score * 0.4
    if final_score < threshold → reject (safe_fallback)

SCORING KÊNH (khi thiếu rerank/NLI scores):
    - Event có year match query → cho phép (structural match)
    - Entity-scan/dynasty intent → cho phép (đã qua hard filter)
    - Còn lại: reject (không đủ dữ liệu scoring → an toàn hơn reject)
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default weights (configurable via config.py)
DEFAULT_RERANK_WEIGHT = 0.6
DEFAULT_ENTAILMENT_WEIGHT = 0.4
DEFAULT_CONFIDENCE_THRESHOLD = 0.55

# Intents that bypass confidence gate (đã có structural match mạnh)
# These intents are resolved by entity-scan/year-scan, not semantic search
STRUCTURAL_MATCH_INTENTS = frozenset({
    "year", "year_range", "multi_year",
    "person", "dynasty", "topic", "place", "multi_entity",
    "person_query", "event_query", "dynasty_query",
    "definition", "relationship",
    "dynasty_timeline", "broad_history",
    "resistance_national", "territorial_event", "civil_war",
    "data_scope",
})

# Safe fallback message khi confidence quá thấp
SAFE_FALLBACK_MESSAGE = (
    "Hiện tại tôi chưa tìm được thông tin phù hợp chính xác với câu hỏi này.\n\n"
    "Bạn có thể thử:\n"
    "- **Hỏi cụ thể hơn** — ví dụ: *\"Trận Bạch Đằng năm 1288\"*\n"
    "- **Dùng tên nhân vật** — ví dụ: *\"Trần Hưng Đạo đánh quân Nguyên\"*\n"
    "- **Nêu triều đại** — ví dụ: *\"Nhà Trần có sự kiện gì nổi bật?\"*"
)


def compute_final_score(
    event: Dict[str, Any],
    rerank_weight: float = DEFAULT_RERANK_WEIGHT,
    entailment_weight: float = DEFAULT_ENTAILMENT_WEIGHT,
) -> float:
    """
    Tính điểm tin cậy cuối cùng cho 1 event.

    Formula:
        final = sigmoid(rerank_score) * 0.6 + entailment_score * 0.4

    Scores được gắn vào event dict bởi các service TRƯỚC đó:
        - _rerank_score: từ cross_encoder_service.rerank_events()
        - _nli_entailment: từ nli_validator_service.validate_events_nli()

    Nếu thiếu CẢ HAI score → trả -1.0 (sentinel = "chưa scored").
    Nếu thiếu 1 score → dùng 0.0 cho score thiếu (pessimistic).

    Args:
        event: Event dict (có thể có _rerank_score và _nli_entailment)
        rerank_weight: Trọng số cho rerank score
        entailment_weight: Trọng số cho NLI entailment

    Returns:
        Float final confidence score (0.0 - 1.0), hoặc -1.0 nếu chưa scored
    """
    rerank = event.get("_rerank_score")
    entailment = event.get("_nli_entailment")

    has_rerank = rerank is not None
    has_entailment = entailment is not None

    # SENTINEL: cả hai score đều thiếu → event chưa qua rerank+NLI pipeline
    if not has_rerank and not has_entailment:
        return -1.0  # Sentinel: "unscored" → cần context-aware decision

    # Dùng 0.0 cho score thiếu (pessimistic default)
    rerank_val = float(rerank) if has_rerank else 0.0
    entailment_val = float(entailment) if has_entailment else 0.0

    # Normalize rerank score to [0, 1] range
    # Cross-encoder scores can be arbitrary (e.g., -10 to +10)
    # Sigmoid normalization: 1 / (1 + e^(-x))
    if rerank_val != 0.0:
        import math
        rerank_normalized = 1.0 / (1.0 + math.exp(-rerank_val))
    else:
        rerank_normalized = 0.5  # neutral

    score = rerank_normalized * rerank_weight + entailment_val * entailment_weight
    return round(score, 4)


def score_events(
    events: List[Dict[str, Any]],
    rerank_weight: float = DEFAULT_RERANK_WEIGHT,
    entailment_weight: float = DEFAULT_ENTAILMENT_WEIGHT,
) -> List[Dict[str, Any]]:
    """
    Gắn _final_confidence vào mỗi event và sort theo confidence giảm dần.

    Args:
        events: Events đã qua rerank + NLI + hard filter

    Returns:
        Events sorted by _final_confidence (descending)
    """
    for event in events:
        event["_final_confidence"] = compute_final_score(
            event, rerank_weight, entailment_weight
        )

    # Sort by confidence descending
    events.sort(key=lambda e: e.get("_final_confidence", 0.0), reverse=True)
    return events


def should_answer(
    events: List[Dict[str, Any]],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    intent: Optional[str] = None,
) -> bool:
    """
    Quyết định có nên trả lời hay không — CONTEXT-AWARE.

    Logic:
        1. Không có events → False
        2. Intent có structural match (entity-scan, year-scan) → True (bypass gate)
        3. Tất cả events unscored (-1.0) → reject (an toàn hơn)
        4. Best scored event < threshold → False (trả safe_fallback)
        5. Best scored event >= threshold → True

    Args:
        events: Events đã scored (có _final_confidence)
        threshold: Ngưỡng tin cậy tối thiểu
        intent: Intent từ engine (dùng để bypass gate cho structural matches)

    Returns:
        True nếu nên trả lời, False nếu nên trả safe_fallback
    """
    if not events:
        return False

    # --- CONTEXT-AWARE BYPASS ---
    # Intent đã có structural match mạnh (entity-scan, year-scan, dynasty)
    # → bypass confidence gate vì data đã deterministic
    if intent and intent in STRUCTURAL_MATCH_INTENTS:
        logger.info(
            f"[CONFIDENCE] Intent '{intent}' has structural match → bypassing gate"
        )
        return True

    # --- SCORE-BASED GATE ---
    # Lọc ra events đã scored (exclude sentinel -1.0)
    scored_events = [e for e in events if e.get("_final_confidence", -1.0) >= 0.0]

    if not scored_events:
        # Tất cả events unscored → KHÔNG có data scoring → reject
        logger.warning(
            f"[CONFIDENCE] All {len(events)} events unscored (no rerank/NLI) "
            f"and intent '{intent}' lacks structural match → rejecting"
        )
        return False

    best_score = max(e.get("_final_confidence", 0.0) for e in scored_events)

    if best_score < threshold:
        logger.warning(
            f"[CONFIDENCE] Best score {best_score:.4f} < threshold {threshold} "
            f"→ rejecting answer (safe_fallback)"
        )
        return False

    logger.info(
        f"[CONFIDENCE] Best score {best_score:.4f} >= threshold {threshold} → answering"
    )
    return True


def safe_fallback() -> Dict[str, Any]:
    """
    Trả về response an toàn khi confidence quá thấp.

    Returns:
        Dict với answer = thông báo + confidence = 0.0
    """
    return {
        "answer": SAFE_FALLBACK_MESSAGE,
        "confidence": 0.0,
    }
