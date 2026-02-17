"""
answer_postprocessor.py — Answer-Level Semantic Deduplication.

Final cleanup layer that removes duplicate sentences from formatted answer text.

Architecture:
    Formatted Answer Text
        ↓
    Split by newlines
        ↓
    Normalize each line (strip bullets, year prefixes, punctuation)
        ↓
    SequenceMatcher fuzzy check (threshold 0.75)
        ↓
    Keep first occurrence of each unique sentence
        ↓
    Rejoin → Clean Answer

This runs AFTER all formatting is done, as a safety net.
"""

import re
from difflib import SequenceMatcher
from typing import List

from app.services.event_aggregator import normalize_for_dedup


def deduplicate_answer(text: str, threshold: float = 0.75) -> str:
    """
    Remove duplicate or near-duplicate lines from formatted answer text.

    Args:
        text: Formatted answer text with newlines.
        threshold: SequenceMatcher similarity threshold.
                   Lines above this threshold are considered duplicates.

    Returns:
        Deduplicated answer text.
    """
    if not text:
        return text

    lines = text.split('\n')
    if len(lines) <= 1:
        return text

    kept_lines: List[str] = []
    kept_normalized: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Always keep empty lines and section headers (###, ##, #)
        if not stripped or stripped.startswith('#'):
            kept_lines.append(line)
            continue

        # Normalize for comparison
        normalized = normalize_for_dedup(stripped)

        # Skip very short normalized text (likely just formatting)
        if len(normalized) < 5:
            kept_lines.append(line)
            continue

        # Check against all previously kept lines
        is_duplicate = False
        for prev_norm in kept_normalized:
            # Exact match
            if normalized == prev_norm:
                is_duplicate = True
                break

            # Containment check
            if normalized in prev_norm or prev_norm in normalized:
                is_duplicate = True
                break

            # Fuzzy similarity
            sim = SequenceMatcher(None, normalized, prev_norm).ratio()
            if sim >= threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            kept_lines.append(line)
            kept_normalized.append(normalized)

    return '\n'.join(kept_lines)


def canonicalize_year_format(text: str) -> str:
    """
    Normalize year formatting to a canonical form.

    Converts:
      - "(năm 2010):" → "Năm 2010:"
      - "2010 –" → "Năm 2010:"
      - "(2010)" → "năm 2010"

    This prevents visual duplication from different year formats.
    """
    if not text:
        return text

    # "(năm YYYY):" or "(năm YYYY)," → "Năm YYYY:"
    text = re.sub(
        r'\(năm\s+(\d{1,4})\)[,:;]?\s*',
        r'Năm \1: ',
        text,
        flags=re.IGNORECASE
    )

    # Standalone "(YYYY):" at line start → "Năm YYYY:"
    text = re.sub(
        r'^(\s*[-•*]\s*)?\((\d{3,4})\)[,:;]?\s*',
        r'\1Năm \2: ',
        text,
        flags=re.MULTILINE
    )

    return text
