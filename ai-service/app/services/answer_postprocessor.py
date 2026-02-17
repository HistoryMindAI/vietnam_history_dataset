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


def _dedup_intra_line(line: str, threshold: float = 0.75) -> str:
    """
    Remove duplicate clauses WITHIN a single line.

    Catches patterns like:
    - "Title; subtitle. (năm 2010): Title; subtitle."
    - "Event description. Event description."
    - "Clause A, clause B. Clause A, clause B."

    Strategy:
    1. Split by year markers like "(năm XXXX):" or "Năm XXXX:"
    2. Split by sentence boundaries (periods followed by space + uppercase)
    3. Fuzzy-check each segment against previous segments
    """
    if not line or len(line) < 20:
        return line

    # --- Strategy 1: Year marker split ---
    # Pattern: "content (năm YYYY): content" or "content. Năm YYYY: content"
    year_split = re.split(
        r'[.;]\s*(?:\(năm\s+\d{1,4}\)|Năm\s+\d{1,4})[,:;]?\s*',
        line,
        flags=re.IGNORECASE
    )
    if len(year_split) >= 2:
        # Check if content before and after the year marker are similar
        before = normalize_for_dedup(year_split[0])
        after = normalize_for_dedup(year_split[-1])
        if before and after and len(before) > 10 and len(after) > 10:
            sim = SequenceMatcher(None, before, after).ratio()
            if sim >= threshold:
                # Keep the part with the year marker (reconstruct)
                # Find the year marker itself
                year_match = re.search(
                    r'(\(năm\s+\d{1,4}\)|Năm\s+\**\d{1,4}\**)[,:;]?\s*',
                    line,
                    flags=re.IGNORECASE
                )
                if year_match:
                    # Keep from year marker onward
                    from_year = line[year_match.start():]
                    # Clean up leading punctuation
                    from_year = re.sub(r'^[.;,]\s*', '', from_year)
                    return from_year

    # --- Strategy 2: Sentence-level dedup within line ---
    # Split on "." followed by space (but not inside abbreviations)
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZĐÀ-Ỹ\*])', line)
    if len(sentences) >= 2:
        kept: List[str] = []
        kept_norm: List[str] = []
        for sent in sentences:
            snorm = normalize_for_dedup(sent)
            if len(snorm) < 5:
                kept.append(sent)
                continue
            is_dup = False
            for prev in kept_norm:
                if snorm == prev or snorm in prev or prev in snorm:
                    is_dup = True
                    break
                if SequenceMatcher(None, snorm, prev).ratio() >= threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(sent)
                kept_norm.append(snorm)
        result = ' '.join(kept)
        if len(result) < len(line):
            return result

    return line


def deduplicate_answer(text: str, threshold: float = 0.75) -> str:
    """
    Remove duplicate or near-duplicate content from formatted answer text.

    Two-phase deduplication:
    1. Intra-line: detect repeated clauses within a single line
    2. Inter-line: detect duplicate lines across the answer

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

    # Phase 1: Intra-line dedup (even for single-line answers)
    lines = [_dedup_intra_line(line, threshold) for line in lines]

    if len(lines) <= 1:
        return '\n'.join(lines)

    # Phase 2: Inter-line dedup
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
