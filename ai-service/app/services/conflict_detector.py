"""
conflict_detector.py — Temporal Conflict Detector (Phase 1)

PURPOSE:
    Phát hiện mâu thuẫn thời gian trong câu hỏi TRƯỚC KHI search.
    VD: "Năm 1945 Trần Hưng Đạo làm gì?" → Trần Hưng Đạo mất năm 1300 → CONFLICT.

DESIGN:
    - Chỉ detect 3 loại deterministic conflict:
      A. Person lifespan vs required_year
      B. Dynasty range vs required_year
      C. Entity range vs required_year_range (non-intersecting)
    - KHÔNG detect: ngữ nghĩa phức tạp, logic sâu, fact-check.

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


# ===================================================================
# ENTITY TEMPORAL METADATA
# Source: entity_registry.py PERSON_ALIASES + dynasty periods
# NOTE: Chỉ cần major historical figures — không cần toàn bộ dataset.
# Key = lowercase normalized name (khớp với resolved entities)
# ===================================================================

ENTITY_TEMPORAL_METADATA: Dict[str, dict] = {
    # ========================
    # PERSONS — (birth_year, death_year)
    # ========================
    "hùng vương": {
        "type": "person",
        "lifespan": (-2879, -258),  # Legendary period
    },
    "an dương vương": {
        "type": "person",
        "lifespan": (-257, -207),
    },
    "hai bà trưng": {
        "type": "person",
        "lifespan": (14, 43),
    },
    "trưng trắc": {
        "type": "person",
        "lifespan": (14, 43),
    },
    "trưng nhị": {
        "type": "person",
        "lifespan": (14, 43),
    },
    "lý bí": {
        "type": "person",
        "lifespan": (503, 548),
    },
    "ngô quyền": {
        "type": "person",
        "lifespan": (898, 944),
    },
    "đinh bộ lĩnh": {
        "type": "person",
        "lifespan": (924, 979),
    },
    "đinh tiên hoàng": {
        "type": "person",
        "lifespan": (924, 979),
    },
    "lê hoàn": {
        "type": "person",
        "lifespan": (941, 1005),
    },
    "lý thái tổ": {
        "type": "person",
        "lifespan": (974, 1028),
    },
    "lý công uẩn": {
        "type": "person",
        "lifespan": (974, 1028),
    },
    "lý thường kiệt": {
        "type": "person",
        "lifespan": (1019, 1105),
    },
    "trần hưng đạo": {
        "type": "person",
        "lifespan": (1228, 1300),
    },
    "trần quốc tuấn": {
        "type": "person",
        "lifespan": (1228, 1300),
    },
    "trần nhân tông": {
        "type": "person",
        "lifespan": (1258, 1308),
    },
    "hồ quý ly": {
        "type": "person",
        "lifespan": (1336, 1407),
    },
    "lê lợi": {
        "type": "person",
        "lifespan": (1385, 1433),
    },
    "lê thái tổ": {
        "type": "person",
        "lifespan": (1385, 1433),
    },
    "nguyễn trãi": {
        "type": "person",
        "lifespan": (1380, 1442),
    },
    "lê thánh tông": {
        "type": "person",
        "lifespan": (1442, 1497),
    },
    "nguyễn huệ": {
        "type": "person",
        "lifespan": (1753, 1792),
    },
    "quang trung": {
        "type": "person",
        "lifespan": (1753, 1792),
    },
    "nguyễn ánh": {
        "type": "person",
        "lifespan": (1762, 1820),
    },
    "gia long": {
        "type": "person",
        "lifespan": (1762, 1820),
    },
    "phan bội châu": {
        "type": "person",
        "lifespan": (1867, 1940),
    },
    "phan châu trinh": {
        "type": "person",
        "lifespan": (1872, 1926),
    },
    "hồ chí minh": {
        "type": "person",
        "lifespan": (1890, 1969),
    },
    "nguyễn ái quốc": {
        "type": "person",
        "lifespan": (1890, 1969),
    },
    "nguyễn tất thành": {
        "type": "person",
        "lifespan": (1890, 1969),
    },
    "bác hồ": {
        "type": "person",
        "lifespan": (1890, 1969),
    },
    "võ nguyên giáp": {
        "type": "person",
        "lifespan": (1911, 2013),
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
    "lê": "lê sơ",  # Default "Lê" → Lê sơ
    "nguyễn": "nhà nguyễn",
    "mạc": "nhà mạc",
    "hồ": "nhà hồ",
    "đinh": "nhà đinh",
    "ngô": "nhà ngô",
}


class ConflictDetector:
    """
    Phát hiện mâu thuẫn thời gian (temporal conflict) trong câu hỏi.

    Chỉ detect: thời gian không giao nhau (deterministic).
    KHÔNG detect: ngữ nghĩa phức tạp, logic sâu.
    """

    def __init__(self, entity_metadata: Optional[Dict[str, dict]] = None):
        self.entity_metadata = entity_metadata or ENTITY_TEMPORAL_METADATA

    def detect(self, query_info: QueryInfo) -> QueryInfo:
        """
        Check query constraints for temporal conflicts.

        Checks:
            0. Self-conflict: required_year vs required_year_range
            A. Person lifespan vs required_year
            B. Dynasty range vs required_year
            C. Entity range vs required_year_range (non-intersecting)

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

        # No temporal constraint → no temporal conflict possible
        if query_info.required_year is None and query_info.required_year_range is None:
            return query_info

        # Check each required person/dynasty against temporal metadata
        # NOTE: Only required_persons (hard entities) — topics are soft, no temporal check
        for entity in query_info.required_persons:
            entity_lower = entity.lower().strip()

            # Try direct lookup
            meta = self.entity_metadata.get(entity_lower)

            # Try short dynasty name fallback
            if not meta and entity_lower in _DYNASTY_SHORT_NAMES:
                full_name = _DYNASTY_SHORT_NAMES[entity_lower]
                meta = self.entity_metadata.get(full_name)

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

        return query_info

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
