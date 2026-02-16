"""
duration_calculator.py — Calculate entity/dynasty durations.

Pure function: no embedding, no rerank, no NLI.
Works directly on start_year / end_year metadata.
"""

from typing import Any, Dict, Optional


class DurationCalculator:
    """Calculate time spans for dynasties, reigns, events."""

    @staticmethod
    def calculate(start_year: Optional[int], end_year: Optional[int]) -> int:
        """
        Calculate duration in years.

        Args:
            start_year: Beginning year (required).
            end_year:   Ending year (required).

        Returns:
            Duration in years (end - start).

        Raises:
            ValueError: If start or end year is None.
        """
        if start_year is None:
            raise ValueError("start_year is None — cannot calculate duration")
        if end_year is None:
            raise ValueError("end_year is None — cannot calculate duration")
        return end_year - start_year

    @staticmethod
    def calculate_safe(
        start_year: Optional[int],
        end_year: Optional[int],
        default: int = 0,
    ) -> int:
        """
        Safe duration calculation — returns default on error.

        Use this in sort/compare contexts where None values
        should not crash the system.
        """
        try:
            if start_year is None or end_year is None:
                return default
            return end_year - start_year
        except (TypeError, ValueError):
            return default

    @staticmethod
    def enrich_entities(
        entities: list,
        start_key: str = "start_year",
        end_key: str = "end_year",
    ) -> list:
        """
        Add 'duration' field to each entity dict.

        Modifies entities in-place and returns the list.
        Entities with missing years get duration=0.
        """
        for entity in entities:
            entity["duration"] = DurationCalculator.calculate_safe(
                entity.get(start_key),
                entity.get(end_key),
            )
        return entities
