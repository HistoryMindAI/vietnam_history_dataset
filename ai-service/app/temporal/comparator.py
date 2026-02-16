"""
comparator.py — Entity comparison utilities.

Pure deterministic logic for max/min/compare operations.
No embedding, no probabilistic scoring.
"""

from typing import Any, Callable, Dict, List, Optional, Union


class Comparator:
    """Compare entities by numeric metrics (duration, year, etc.)."""

    @staticmethod
    def max_entity(
        entities: List[Dict[str, Any]],
        metric_key: str,
        default: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find entity with maximum value for metric_key.

        Args:
            entities:   List of entity dicts.
            metric_key: Key to compare (e.g. "duration", "start_year").
            default:    Return value if entities is empty.

        Returns:
            Entity dict with highest metric value, or default.
        """
        valid = [e for e in entities if e.get(metric_key) is not None]
        if not valid:
            return default
        return max(valid, key=lambda x: x[metric_key])

    @staticmethod
    def min_entity(
        entities: List[Dict[str, Any]],
        metric_key: str,
        default: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find entity with minimum value for metric_key.

        Args:
            entities:   List of entity dicts.
            metric_key: Key to compare (e.g. "duration", "start_year").
            default:    Return value if entities is empty.

        Returns:
            Entity dict with lowest metric value, or default.
        """
        valid = [e for e in entities if e.get(metric_key) is not None]
        if not valid:
            return default
        return min(valid, key=lambda x: x[metric_key])

    @staticmethod
    def compare(
        entity_a: Dict[str, Any],
        entity_b: Dict[str, Any],
        metric_key: str,
    ) -> int:
        """
        Compare two entities by metric.

        Returns:
            1  if a > b
            -1 if a < b
            0  if equal
        """
        val_a = entity_a.get(metric_key, 0)
        val_b = entity_b.get(metric_key, 0)

        if val_a > val_b:
            return 1
        if val_a < val_b:
            return -1
        return 0

    @staticmethod
    def rank(
        entities: List[Dict[str, Any]],
        metric_key: str,
        descending: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Rank entities by metric value.

        Args:
            entities:   List of entity dicts.
            metric_key: Key to rank by.
            descending: True for largest first.

        Returns:
            Sorted copy of entities list.
        """
        valid = [e for e in entities if e.get(metric_key) is not None]
        return sorted(valid, key=lambda x: x[metric_key], reverse=descending)
