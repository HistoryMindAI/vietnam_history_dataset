"""
conflict_detector.py — Temporal Conflict Detector (Phase 1 + 2 + 3)

PURPOSE:
    Phát hiện mâu thuẫn thời gian trong câu hỏi TRƯỚC KHI search.
    VD: "Năm 1945 Trần Hưng Đạo làm gì?" → Trần Hưng Đạo mất năm 1300 → CONFLICT.

TEMPORAL CONSISTENCY INVARIANTS (FROZEN):
    0. Query self-consistency:
       required_year must lie within required_year_range.
    1. Entity vs Query consistency:
       Every entity must overlap required_year / required_year_range.
    2. Cross-entity consistency (Phase 2):
       All entities must share a non-empty global temporal intersection.
    3. Era-membership consistency (Phase 3):
       If query contains ≥1 person with era AND ≥1 dynasty,
       then dynasty ∈ person.era.

    These rules MUST NOT be relaxed without updating benchmark tests.

INTEGRATION:
    Intent Classify → Constraint Extract → 🔥 Conflict Detect → Search

USAGE:
    detector = ConflictDetector()
    query_info = detector.detect(query_info)
    if query_info.has_conflict:
        return safe_fallback()
"""

import logging
from typing import Dict, Tuple, Optional
from app.core.query_schema import QueryInfo

logger = logging.getLogger(__name__)


ENTITY_TEMPORAL_METADATA_VERSION = "v2.1"

# ===================================================================
# ENTITY TEMPORAL METADATA
# Source: entity_registry.py PERSON_ALIASES + dynasty periods
# NOTE: Chỉ cần major historical figures — không cần toàn bộ dataset.
# Key = lowercase normalized name (khớp với resolved entities)
# ===================================================================

ENTITY_TEMPORAL_METADATA: Dict[str, dict] = {
    # ========================
    # PERSONS — (birth_year, death_year)
    # era: list of dynasty/era canonical names person ACTUALLY served
    # ========================
    "hùng vương": {
        "type": "person",
        "lifespan": (-2879, -258),
        "era": ["hùng vương / an dương vương"],
    },
    "an dương vương": {
        "type": "person",
        "lifespan": (-257, -207),
        "era": ["hùng vương / an dương vương"],
    },
    "hai bà trưng": {
        "type": "person",
        "lifespan": (14, 43),
        "era": ["bắc thuộc"],
    },
    "trưng trắc": {
        "type": "person",
        "lifespan": (14, 43),
        "era": ["bắc thuộc"],
    },
    "trưng nhị": {
        "type": "person",
        "lifespan": (14, 43),
        "era": ["bắc thuộc"],
    },
    "lý bí": {
        "type": "person",
        "lifespan": (503, 548),
        "era": ["bắc thuộc"],
    },
    "ngô quyền": {
        "type": "person",
        "lifespan": (898, 944),
        "era": ["nhà ngô"],
    },
    "đinh bộ lĩnh": {
        "type": "person",
        "lifespan": (924, 979),
        "era": ["nhà đinh"],
    },
    "đinh tiên hoàng": {
        "type": "person",
        "lifespan": (924, 979),
        "era": ["nhà đinh"],
    },
    "lê hoàn": {
        "type": "person",
        "lifespan": (941, 1005),
        "era": ["tiền lê"],
    },
    "lý thái tổ": {
        "type": "person",
        "lifespan": (974, 1028),
        "era": ["nhà lý"],
    },
    "lý công uẩn": {
        "type": "person",
        "lifespan": (974, 1028),
        "era": ["nhà lý"],
    },
    "lý thường kiệt": {
        "type": "person",
        "lifespan": (1019, 1105),
        "era": ["nhà lý"],
    },
    "trần hưng đạo": {
        "type": "person",
        "lifespan": (1228, 1300),
        "era": ["nhà trần"],
    },
    "trần quốc tuấn": {
        "type": "person",
        "lifespan": (1228, 1300),
        "era": ["nhà trần"],
    },
    "trần nhân tông": {
        "type": "person",
        "lifespan": (1258, 1308),
        "era": ["nhà trần"],
    },
    "hồ quý ly": {
        "type": "person",
        "lifespan": (1336, 1407),
        "era": ["nhà trần", "nhà hồ"],
    },
    "lê lợi": {
        "type": "person",
        "lifespan": (1385, 1433),
        "era": ["lê sơ"],
    },
    "lê thái tổ": {
        "type": "person",
        "lifespan": (1385, 1433),
        "era": ["lê sơ"],
    },
    "nguyễn trãi": {
        "type": "person",
        "lifespan": (1380, 1442),
        "era": ["lê sơ"],
    },
    "lê thánh tông": {
        "type": "person",
        "lifespan": (1442, 1497),
        "era": ["lê sơ"],
    },
    "nguyễn kim": {
        "type": "person",
        "lifespan": (1468, 1545),
        "era": ["lê trung hưng"],
    },
    "nguyễn huệ": {
        "type": "person",
        "lifespan": (1753, 1792),
        "era": ["tây sơn"],
    },
    "quang trung": {
        "type": "person",
        "lifespan": (1753, 1792),
        "era": ["tây sơn"],
    },
    "nguyễn ánh": {
        "type": "person",
        "lifespan": (1762, 1820),
        "era": ["nhà nguyễn"],
    },
    "gia long": {
        "type": "person",
        "lifespan": (1762, 1820),
        "era": ["nhà nguyễn"],
    },
    "phan bội châu": {
        "type": "person",
        "lifespan": (1867, 1940),
        "era": ["pháp thuộc"],
    },
    "phan châu trinh": {
        "type": "person",
        "lifespan": (1872, 1926),
        "era": ["pháp thuộc"],
    },
    "hồ chí minh": {
        "type": "person",
        "lifespan": (1890, 1969),
        "era": ["pháp thuộc"],
    },
    "nguyễn ái quốc": {
        "type": "person",
        "lifespan": (1890, 1969),
        "era": ["pháp thuộc"],
    },
    "nguyễn tất thành": {
        "type": "person",
        "lifespan": (1890, 1969),
        "era": ["pháp thuộc"],
    },
    "bác hồ": {
        "type": "person",
        "lifespan": (1890, 1969),
        "era": ["pháp thuộc"],
    },
    "võ nguyên giáp": {
        "type": "person",
        "lifespan": (1911, 2013),
        "era": ["pháp thuộc"],
    },

    # ========================
    # DYNASTIES — (start_year, end_year)
    # Source: entity_registry.py extract_dynasty() periods
    # ========================
    "hùng vương / an dương vương": {
        "type": "dynasty",
        "year_range": (-2879, -207),
    },
    "bắc thuộc": {
        "type": "dynasty",
        "year_range": (179, 938),
    },
    "nhà ngô": {
        "type": "dynasty",
        "year_range": (939, 967),
    },
    "nhà đinh": {
        "type": "dynasty",
        "year_range": (968, 980),
    },
    "tiền lê": {
        "type": "dynasty",
        "year_range": (980, 1009),
    },
    "nhà lý": {
        "type": "dynasty",
        "year_range": (1009, 1225),
    },
    "nhà trần": {
        "type": "dynasty",
        "year_range": (1225, 1400),
    },
    "nhà hồ": {
        "type": "dynasty",
        "year_range": (1400, 1407),
    },
    "minh thuộc": {
        "type": "dynasty",
        "year_range": (1407, 1427),
    },
    "lê sơ": {
        "type": "dynasty",
        "year_range": (1428, 1527),
    },
    "nhà mạc": {
        "type": "dynasty",
        "year_range": (1527, 1592),
    },
    "lê trung hưng": {
        "type": "dynasty",
        "year_range": (1533, 1789),
    },
    "hậu lê": {
        "type": "dynasty",
        "year_range": (1428, 1789),  # Composite: lê sơ + lê trung hưng
    },
    "nhà lê": {
        "type": "dynasty",
        "year_range": (1428, 1789),  # Composite: lê sơ + lê trung hưng
    },
    "tây sơn": {
        "type": "dynasty",
        "year_range": (1778, 1802),
    },
    "nhà nguyễn": {
        "type": "dynasty",
        "year_range": (1802, 1945),
    },
    "triều nguyễn": {
        "type": "dynasty",
        "year_range": (1802, 1945),
    },
    "pháp thuộc": {
        "type": "dynasty",
        "year_range": (1858, 1945),
    },
}

# Also index by short dynasty names (without "nhà/triều" prefix)
_DYNASTY_SHORT_NAMES = {
    "lý": "nhà lý",
    "trần": "nhà trần",
    "lê": "lê sơ",  # Default "Lê" → Lê sơ for metadata lookup
    "nguyễn": "nhà nguyễn",
    "mạc": "nhà mạc",
    "hồ": "nhà hồ",
    "đinh": "nhà đinh",
    "ngô": "nhà ngô",
    # nhà lê & hậu lê now have their own metadata entries
}

# Dynasty normalization for era-membership check (Phase 3)
# Rule: normalize ONCE, canonical names must match era field values exactly.
# Fallback: if not in map, name passes through unchanged.
_DYNASTY_NORMALIZATION_MAP = {
    # Short names → canonical
    "trần": "nhà trần",
    "lý": "nhà lý",
    "lê": ["lê sơ", "lê trung hưng"],  # Ambiguous → both candidates
    "nguyễn": "nhà nguyễn",
    "mạc": "nhà mạc",
    "hồ": "nhà hồ",
    "đinh": "nhà đinh",
    "ngô": "nhà ngô",
    # Full names → canonical (identity or disambiguation)
    "nhà trần": "nhà trần",
    "nhà lý": "nhà lý",
    "nhà lê": ["lê sơ", "lê trung hưng"],  # Ambiguous → both candidates
    "lê sơ": "lê sơ",
    "lê trung hưng": "lê trung hưng",
    "hậu lê": ["lê sơ", "lê trung hưng"],  # Composite: cả hai
    "nhà nguyễn": "nhà nguyễn",
    "triều nguyễn": "nhà nguyễn",
    "nhà mạc": "nhà mạc",
    "nhà hồ": "nhà hồ",
    "nhà đinh": "nhà đinh",
    "nhà ngô": "nhà ngô",
    "tây sơn": "tây sơn",
    "pháp thuộc": "pháp thuộc",
    "bắc thuộc": "bắc thuộc",
    "tiền lê": "tiền lê",
    "minh thuộc": "minh thuộc",
    "hùng vương / an dương vương": "hùng vương / an dương vương",
}


class ConflictDetector:
    """
    Phát hiện mâu thuẫn thời gian (temporal conflict) trong câu hỏi.

    Phase 1: Entity vs query year (single entity check)
    Phase 2: Cross-entity global temporal intersection
    Phase 3: Era-membership consistency (person ∈ dynasty?)
    KHÔNG detect: ngữ nghĩa phức tạp, logic sâu.
    """

    def __init__(self, entity_metadata: Optional[Dict[str, dict]] = None):
        self.entity_metadata = entity_metadata or ENTITY_TEMPORAL_METADATA

    def _lookup_metadata(self, entity_name: str) -> Optional[dict]:
        """Lookup entity temporal metadata with short dynasty name fallback."""
        entity_lower = entity_name.lower().strip()
        meta = self.entity_metadata.get(entity_lower)
        if not meta and entity_lower in _DYNASTY_SHORT_NAMES:
            full_name = _DYNASTY_SHORT_NAMES[entity_lower]
            meta = self.entity_metadata.get(full_name)
        return meta

    def detect(self, query_info: QueryInfo) -> QueryInfo:
        """
        Check query constraints for temporal conflicts.

        Invariants (FROZEN v2.1):
            0. Self-consistency: required_year ∈ required_year_range
            1. Entity vs query: each entity overlaps required_year / required_year_range
            2. Cross-entity: all entities share non-empty global temporal intersection
            3. Era-membership: person.era ∋ dynasty (only if relation_type == belong_to)

        Mutates query_info in-place:
          - query_info.has_conflict = True if conflict found
          - query_info.conflict_reasons = list of reasons

        Returns: query_info (for chaining)
        """
        # 0️⃣ Self-conflict: required_year vs required_year_range
        if query_info.required_year is not None and query_info.required_year_range is not None:
            q_start, q_end = query_info.required_year_range
            if not (q_start <= query_info.required_year <= q_end):
                query_info.has_conflict = True
                query_info.conflict_reasons.append(
                    f"Query self-conflict: year {query_info.required_year} "
                    f"not in stated range {q_start}–{q_end}"
                )
                logger.warning(
                    f"[CONFLICT] {query_info.conflict_reasons[-1]} "
                    f"(query='{query_info.original_query}')"
                )
                return query_info  # No need to check entities

        # 1️⃣ Entity vs query year/range (Phase 1)
        # NOTE: Only required_persons (hard entities) — topics are soft, no temporal check
        has_temporal = (
            query_info.required_year is not None
            or query_info.required_year_range is not None
        )

        if has_temporal:
            for entity in query_info.required_persons:
                meta = self._lookup_metadata(entity)
                if not meta:
                    continue  # Unknown entity → no conflict (safe default)

                entity_range = self._extract_entity_range(meta)
                if not entity_range:
                    continue

                if not self._has_intersection(query_info, entity_range):
                    query_info.has_conflict = True
                    entity_type = meta.get("type", "entity")
                    range_str = f"{entity_range[0]}–{entity_range[1]}"
                    if query_info.required_year is not None:
                        query_info.conflict_reasons.append(
                            f"Temporal conflict: {entity_type} '{entity}' "
                            f"({range_str}) does not include year {query_info.required_year}"
                        )
                    else:
                        yr = query_info.required_year_range
                        query_info.conflict_reasons.append(
                            f"Temporal conflict: {entity_type} '{entity}' "
                            f"({range_str}) does not intersect with year range {yr[0]}–{yr[1]}"
                        )

                    logger.warning(
                        f"[CONFLICT] {query_info.conflict_reasons[-1]} "
                        f"(query='{query_info.original_query}')"
                    )

        # 2️⃣ Cross-entity global temporal intersection (Phase 2)
        if not query_info.has_conflict:
            self._detect_cross_entity_conflicts(query_info)

        # 3️⃣ Era-membership consistency (Phase 3)
        if not query_info.has_conflict:
            self._detect_era_membership_conflicts(query_info)

        return query_info

    def _detect_cross_entity_conflicts(self, query_info: QueryInfo) -> None:
        """
        Phase 2: Global temporal intersection check.

        Rule:
            If >= 2 entities have temporal metadata,
            all must share at least one overlapping year.

        Invariant:
            ∃ t such that every entity existed at time t.

        Complexity: O(n) — single pass max/min.
        """
        entity_ranges = []

        for name in query_info.required_persons:
            meta = self._lookup_metadata(name)
            if not meta:
                continue  # safe default: skip unknown metadata

            entity_range = self._extract_entity_range(meta)
            if not entity_range:
                continue

            entity_ranges.append((name, entity_range[0], entity_range[1]))

        # Need at least 2 valid ranges to check intersection
        if len(entity_ranges) < 2:
            return

        # Global intersection: ∃ t ∈ [global_start, global_end]
        global_start = max(start for _, start, _ in entity_ranges)
        global_end = min(end for _, _, end in entity_ranges)

        if global_start > global_end:
            names = [name for name, _, _ in entity_ranges]
            query_info.has_conflict = True
            query_info.conflict_reasons.append(
                f"Cross-entity temporal conflict: "
                f"{', '.join(names)} share no overlapping lifespan/era."
            )
            logger.warning(
                f"[CONFLICT] {query_info.conflict_reasons[-1]} "
                f"(query='{query_info.original_query}')"
            )

    def _extract_entity_range(self, meta: dict) -> Optional[Tuple[int, int]]:
        """Extract temporal range from metadata entry."""
        if meta.get("type") == "person":
            return meta.get("lifespan")
        if meta.get("type") in ("dynasty", "era"):
            return meta.get("year_range")
        return None

    def _has_intersection(
        self, query_info: QueryInfo, entity_range: Tuple[int, int]
    ) -> bool:
        """Check if query's temporal constraint intersects with entity's range."""
        start, end = entity_range

        if query_info.required_year is not None:
            return start <= query_info.required_year <= end

        if query_info.required_year_range is not None:
            q_start, q_end = query_info.required_year_range
            return not (q_end < start or q_start > end)

        return True  # No temporal constraint → no conflict

    def _detect_era_membership_conflicts(self, query_info: QueryInfo) -> None:
        """
        Phase 3 (v2.1): Era-membership consistency — STRICT but context-aware HARD rule.

        Reject ONLY when:
        - relation_type == "belong_to"
        - Query contains ≥1 person with era metadata
        - Query contains ≥1 dynasty
        - No normalized dynasty candidate matches person's era list

        Safety guarantees:
        - No over-rejection for live_during / compare relations
        - Ambiguous dynasty names handled via multi-candidate normalization
        - Deterministic, O(p × d × k) but tiny constants
        """
        if query_info.has_conflict:
            return  # short-circuit safety

        # Context-aware guard: only fire for explicit membership claims
        if getattr(query_info, "relation_type", None) != "belong_to":
            return

        persons_with_era = []
        dynasties = []
        seen_persons = set()  # deduplicate

        for name in query_info.required_persons:
            meta = self._lookup_metadata(name)
            if not meta:
                continue

            entity_type = meta.get("type")

            if entity_type == "person" and "era" in meta:
                person_key = name.lower().strip()
                if person_key not in seen_persons:
                    seen_persons.add(person_key)
                    persons_with_era.append((name, meta["era"]))
            elif entity_type in ("dynasty", "era"):
                dynasties.append(self._normalize_dynasty_name(name))

        # Need both sides
        if not persons_with_era or not dynasties:
            return

        # HARD RULE: each person must match each dynasty
        for person_name, person_eras in persons_with_era:
            for dynasty_candidates in dynasties:
                # dynasty_candidates is List[str] — check if ANY candidate matches
                match_found = any(
                    candidate in person_eras
                    for candidate in dynasty_candidates
                )

                if not match_found:
                    query_info.has_conflict = True
                    query_info.conflict_reasons.append(
                        f"Era-membership conflict: "
                        f"'{person_name}' belongs to {person_eras}, not {dynasty_candidates}."
                    )
                    logger.warning(
                        f"[CONFLICT] {query_info.conflict_reasons[-1]} "
                        f"(query='{query_info.original_query}')"
                    )
                    return  # early exit (deterministic reject)

    def _normalize_dynasty_name(self, name: str) -> list:
        """
        Normalize dynasty name to canonical form(s) for era-membership lookup.

        Returns List[str] — always a list.
        For ambiguous names (e.g., 'nhà lê'), returns multiple candidates.
        """
        normalized = name.lower().strip()
        result = _DYNASTY_NORMALIZATION_MAP.get(normalized, normalized)
        if isinstance(result, list):
            return result
        return [result]
