"""
timeline_resolver.py — Temporal filtering: before, after, overlap.

Answers queries like:
  - "Sự kiện nào trước khởi nghĩa Lam Sơn?" → before(entities, 1418)
  - "Ai cùng thời với Trần Hưng Đạo?"         → overlap(entities, 1228, 1300)
  - "Sự kiện nào sau 1945?"                   → after(entities, 1945)

Pure deterministic logic — no embedding, no reranker.
"""

from typing import Any, Dict, List, Optional


class TimelineResolver:
    """Filter entities by temporal relationships."""

    @staticmethod
    def before(
        entities: List[Dict[str, Any]],
        reference_year: int,
        year_key: str = "start_year",
    ) -> List[Dict[str, Any]]:
        """
        Find entities occurring BEFORE reference_year.

        Returns entities sorted by year descending (closest first).
        """
        result = [
            e for e in entities
            if e.get(year_key) is not None and e[year_key] < reference_year
        ]
        return sorted(result, key=lambda e: e[year_key], reverse=True)

    @staticmethod
    def after(
        entities: List[Dict[str, Any]],
        reference_year: int,
        year_key: str = "start_year",
    ) -> List[Dict[str, Any]]:
        """
        Find entities occurring AFTER reference_year.

        Returns entities sorted by year ascending (closest first).
        """
        result = [
            e for e in entities
            if e.get(year_key) is not None and e[year_key] > reference_year
        ]
        return sorted(result, key=lambda e: e[year_key])

    @staticmethod
    def overlap(
        entities: List[Dict[str, Any]],
        start: int,
        end: int,
        start_key: str = "start_year",
        end_key: str = "end_year",
    ) -> List[Dict[str, Any]]:
        """
        Find entities whose timespan overlaps with [start, end].

        An entity overlaps if: entity.start <= end AND entity.end >= start.
        Entities with missing start/end are excluded.
        """
        result = []
        for e in entities:
            e_start = e.get(start_key)
            e_end = e.get(end_key)
            if e_start is None or e_end is None:
                continue
            if e_start <= end and e_end >= start:
                result.append(e)
        return sorted(result, key=lambda e: e[start_key])

    @staticmethod
    def at_year(
        entities: List[Dict[str, Any]],
        year: int,
        start_key: str = "start_year",
        end_key: str = "end_year",
    ) -> List[Dict[str, Any]]:
        """
        Find entities active at a specific year.

        Shortcut for overlap(entities, year, year).
        """
        return TimelineResolver.overlap(entities, year, year, start_key, end_key)
