"""
answer_validator.py — Hard Constraint Filter + Answer-Type Gate (Phase 1 / Giai đoạn 11)

PURPOSE:
    Lọc candidates sau Cross-Encoder Rerank + NLI.
    Chỉ giữ events thỏa mãn ràng buộc cứng (năm, entity, answer_type).
    ĐÂY LÀ LỚP BẢO VỆ QUAN TRỌNG NHẤT chống trả lời lệch.

CONTEXT:
    - TRƯỚC ĐÂY: Không có hard filter — semantic có thể override year/entity constraints
    - BÂY GIỜ: Sau NLI, mọi candidate PHẢI qua validate trước khi build answer

RELATED OLD FILES:
    - engine.py → _filter_by_query_keywords() (soft keyword filter — vẫn giữ)
    - nli_validator_service.py → validate_events_nli() (NLI filter — chạy TRƯỚC module này)
    - cross_encoder_service.py → rerank_events() (rerank — chạy TRƯỚC module này)

PIPELINE POSITION:
    Search → Cross-Encoder Rerank → NLI Validate → **Hard Constraint Filter** → Answer Build

DESIGN DECISIONS:
    1. Year constraint: STRICT — event.year MUST match required_year (±0 tolerance)
       Fallback: nếu event không có year nhưng có year_range → check in range
    2. Entity constraint: SOFT — entity name phải xuất hiện trong event text/persons
    3. Answer-type gate: SEMI-STRICT — reject nếu thiếu thông tin bắt buộc
    4. NO safety fallback: filter loại hết → trả empty → để safe_fallback xử lý
       (production system KHÔNG tự nới lỏng constraint)
"""

import logging
from typing import List, Dict, Any, Optional

from app.core.query_schema import QueryInfo

logger = logging.getLogger(__name__)


class AnswerValidator:
    """
    Hard Constraint Filter + Answer-Type Gate.

    Methods:
        validate_candidate(): Kiểm tra 1 event có thỏa constraints không
        filter_events(): Lọc danh sách events, giữ valid + safety fallback
    """

    # RULE: Any entity temporal conflict in entity-scan intents still gets
    # temporal check. Only entity text-matching is skipped for these intents.
    _ENTITY_SCAN_INTENTS = {
        "person_query", "event_query", "dynasty_query",
        "person", "topic", "place", "multi_entity",
        "definition", "relationship",
    }

    def validate_candidate(
        self, query_info: QueryInfo, event: Dict[str, Any]
    ) -> bool:
        """
        Production-safe candidate validation.

        Applies:
            1. Temporal constraints (ALWAYS enforced — never skipped)
            2. Entity constraints (conditionally — skipped for entity-scan intents)
            3. Answer type gate

        Returns:
            True nếu event PASS tất cả checks
        """
        # 1️⃣ TEMPORAL — always enforced, never bypassed
        if not self._validate_temporal(event, query_info):
            return False

        # 2️⃣ ENTITY — skip for entity-scan intents (already matched structurally)
        if not self._should_skip_entity_check(query_info):
            if not self._validate_person_constraints(event, query_info):
                return False

        # 3️⃣ ANSWER TYPE gate
        if query_info.answer_type_required:
            if not self._check_answer_type(query_info.answer_type_required, event):
                return False

        return True

    def _validate_temporal(
        self, event: Dict[str, Any], query_info: QueryInfo
    ) -> bool:
        """
        Temporal constraint validation — NEVER skipped.

        Handles both event.year and event.year_range for:
        - required_year (strict equality or range containment)
        - required_year_range (overlap check)
        """
        event_year = event.get("year")
        event_range = event.get("year_range")

        # 🔸 required_year check
        if query_info.required_year is not None:
            req_yr = query_info.required_year

            if event_year is not None:
                # Case A: Event has exact year → strict equality
                if int(event_year) != req_yr:
                    return False
            elif event_range and len(event_range) == 2:
                # Case B: Event has year_range → check containment
                e_start, e_end = int(event_range[0]), int(event_range[1])
                if not (e_start <= req_yr <= e_end):
                    return False
            else:
                # No year, no year_range → reject
                return False

        # 🔸 required_year_range check (overlap with event)
        if query_info.required_year_range is not None:
            q_start, q_end = query_info.required_year_range

            if event_year is not None:
                # Event has exact year → must fall within query range
                if not (q_start <= int(event_year) <= q_end):
                    return False
            elif event_range and len(event_range) == 2:
                # Event has year_range → check overlap (intersection ≠ ∅)
                e_start, e_end = int(event_range[0]), int(event_range[1])
                if q_end < e_start or q_start > e_end:
                    return False  # No overlap
            else:
                # No year, no year_range → reject
                return False

        return True

    def _should_skip_entity_check(self, query_info: QueryInfo) -> bool:
        """
        Entity-scan intents already matched events via entity resolution.
        Skip redundant entity text-matching for these intents.
        DOES NOT skip temporal checks — those are always enforced.
        """
        return query_info.intent in self._ENTITY_SCAN_INTENTS

    def _validate_person_constraints(
        self, event: Dict[str, Any], query_info: QueryInfo
    ) -> bool:
        """
        Person/dynasty constraint — ANY-match (ít nhất 1 person phải xuất hiện).
        Chỉ check required_persons (HARD). Topics KHÔNG check ở đây.
        """
        if not query_info.required_persons:
            return True

        event_text = self._get_event_searchable_text(event)
        return any(
            self._entity_present(entity, event_text, event)
            for entity in query_info.required_persons
        )

    def filter_events(
        self,
        query_info: QueryInfo,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Lọc danh sách events bằng hard constraints.

        DETERMINISTIC: Nếu filter loại HẾT events → trả empty list.
        Để confidence_scorer.safe_fallback() xử lý → không tự nới lỏng constraint.

        Args:
            query_info: Ràng buộc từ ConstraintExtractor
            events: Events đã qua rerank + NLI

        Returns:
            Filtered events list (có thể empty)
        """
        if not events:
            return events

        # Skip filtering only for truly broad intents WITHOUT explicit constraints.
        # This keeps broad narrative queries flexible, while still enforcing
        # who/when/where gates for semantic fallbacks.
        if (
            query_info.intent in (
                "data_scope", "broad_history", "dynasty_timeline",
                "resistance_national", "semantic",
            )
            and not self._has_explicit_constraints(query_info)
        ):
            return events

        # Skip for fact_check — has its own specialized validation
        if query_info.is_fact_check:
            return events

        valid = [e for e in events if self.validate_candidate(query_info, e)]

        if valid:
            logger.info(
                f"[HARD_FILTER] {len(valid)}/{len(events)} events passed "
                f"(intent={query_info.intent}, "
                f"year={query_info.required_year}, "
                f"type={query_info.answer_type_required})"
            )
            return valid

        # DETERMINISTIC: filter loại hết → trả empty
        # Downstream safe_fallback sẽ xử lý — KHÔNG tự nới lỏng constraint
        logger.warning(
            f"[HARD_FILTER] All {len(events)} events filtered out → empty. "
            f"(intent={query_info.intent}, "
            f"year={query_info.required_year}, "
            f"entities={query_info.required_persons})"
        )
        return []

    # ===============================================================
    # PRIVATE HELPERS
    # ===============================================================

    def _get_event_searchable_text(self, event: Dict[str, Any]) -> str:
        """Gom tất cả text fields của event thành 1 string để search."""
        parts = [
            event.get("story", "") or "",
            event.get("event", "") or "",
            event.get("title", "") or "",
            event.get("location", "") or "",
            " ".join(event.get("places", []) or []),
            " ".join(event.get("persons", []) or []),
            " ".join(event.get("persons_all", []) or []),
            " ".join(event.get("keywords", []) or []),
            event.get("dynasty", "") or "",
        ]
        return " ".join(parts).lower()

    def _has_explicit_constraints(self, query_info: QueryInfo) -> bool:
        """
        Return True when the query carries constraints that should still be
        enforced even if the classifier fell back to a broad/semantic intent.
        """
        return any((
            query_info.required_year is not None,
            query_info.required_year_range is not None,
            bool(query_info.required_persons),
            query_info.answer_type_required in {"person", "year", "location", "dynasty"},
        ))

    def _entity_present(
        self, entity: str, event_text: str, event: Dict[str, Any]
    ) -> bool:
        """
        Kiểm tra entity có xuất hiện trong event không.

        Strategy:
            1. Exact match trong combined text
            2. Word-by-word match (tên nhiều từ — "trần hưng đạo" → check từng từ)
            3. Check trong persons metadata array
        """
        entity_lower = entity.lower().strip()

        # Strategy 1: Full name match
        if entity_lower in event_text:
            return True

        # Strategy 2: Word-by-word (for multi-word names)
        words = entity_lower.split()
        if len(words) >= 2 and all(w in event_text for w in words):
            return True

        # Strategy 3: Check persons metadata
        event_persons = [p.lower() for p in (event.get("persons", []) or [])]
        event_persons.extend(p.lower() for p in (event.get("persons_all", []) or []))
        for person in event_persons:
            if entity_lower in person or person in entity_lower:
                return True

        return False

    def _check_answer_type(
        self, required_type: str, event: Dict[str, Any]
    ) -> bool:
        """
        Answer-Type Gate: kiểm tra event có chứa đúng loại thông tin yêu cầu.

        Gate rules:
            "person" → event phải mention ít nhất 1 person
            "year"   → event phải có year field
            "location" → event phải mention địa điểm
            "event"  → relaxed, chỉ cần có story/event text
            "dynasty" → event phải có dynasty field
            "list"   → relaxed (nhiều events — handled ở mức filter list)
        """
        if required_type == "person":
            # Must have persons in metadata OR mention in text
            persons = event.get("persons", []) or event.get("persons_all", [])
            return bool(persons)

        elif required_type == "year":
            return event.get("year") is not None

        elif required_type == "location":
            places = event.get("places", []) or []
            if places:
                return True
            if event.get("location"):
                return True
            return False

        elif required_type == "event":
            # Must have story or event text
            return bool(event.get("story") or event.get("event"))

        elif required_type == "dynasty":
            return bool(event.get("dynasty"))

        # Default: pass (no strict requirement)
        return True
