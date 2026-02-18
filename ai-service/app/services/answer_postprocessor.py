"""
answer_postprocessor.py — Answer-Level Semantic Deduplication.

Final cleanup layer that removes duplicate sentences from formatted answer text.

Architecture:
    Formatted Answer Text
        ↓
    Phase 1: Intra-line dedup (within each line)
        ↓
    Phase 2: Inter-line dedup (across lines)
        ↓
    Clean Answer

Uses rapidfuzz.fuzz.token_set_ratio for order-agnostic, subset-aware fuzzy matching.
This is 10x faster than difflib.SequenceMatcher and handles token reordering.

This runs AFTER all formatting is done, as a safety net.
"""

import re
from typing import List

from rapidfuzz import fuzz

from app.services.event_aggregator import normalize_for_dedup


# ── Threshold (rapidfuzz uses 0–100 scale) ──────────────────────
DEDUP_THRESHOLD = 80.0  # ~equivalent to SequenceMatcher 0.75


def _is_fuzzy_dup(text_a: str, text_b: str, threshold: float = DEDUP_THRESHOLD) -> bool:
    """
    Check if two normalized texts are near-duplicates using token_set_ratio.

    token_set_ratio is order-agnostic and subset-aware:
      - "Trận Bạch Đằng năm 938" vs "Năm 938 trận Bạch Đằng" → 100.0
      - "A B C" vs "A B C D E" → 100.0 (subset detection)
    """
    if not text_a or not text_b:
        return False
    # Exact match or containment
    if text_a == text_b or text_a in text_b or text_b in text_a:
        return True
    return fuzz.token_set_ratio(text_a, text_b) >= threshold


def _dedup_intra_line(line: str, threshold: float = DEDUP_THRESHOLD) -> str:
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
            if _is_fuzzy_dup(before, after, threshold):
                # Keep the part with the year marker (reconstruct)
                year_match = re.search(
                    r'(\(năm\s+\d{1,4}\)|Năm\s+\**\d{1,4}\**)[,:;]?\s*',
                    line,
                    flags=re.IGNORECASE
                )
                if year_match:
                    from_year = line[year_match.start():]
                    from_year = re.sub(r'^[.;,]\s*', '', from_year)
                    return from_year

    # --- Strategy 2: Sentence-level dedup within line ---
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZĐÀ-Ỹ\*])', line)
    if len(sentences) >= 2:
        kept: List[str] = []
        kept_norm: List[str] = []
        for sent in sentences:
            snorm = normalize_for_dedup(sent)
            if len(snorm) < 5:
                kept.append(sent)
                continue
            is_dup = any(_is_fuzzy_dup(snorm, prev, threshold) for prev in kept_norm)
            if not is_dup:
                kept.append(sent)
                kept_norm.append(snorm)
        result = ' '.join(kept)
        if len(result) < len(line):
            return result

    return line


def deduplicate_answer(text: str, threshold: float = DEDUP_THRESHOLD) -> str:
    """
    Remove duplicate or near-duplicate content from formatted answer text.

    Two-phase deduplication:
    1. Intra-line: detect repeated clauses within a single line
    2. Inter-line: detect duplicate lines across the answer

    Args:
        text: Formatted answer text with newlines.
        threshold: rapidfuzz token_set_ratio threshold (0-100 scale).
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
        result = '\n'.join(lines)
        from app.services.formatters.timeline_formatter import enforce_timeline_format
        return enforce_timeline_format(result)

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

        # Check against all previously kept lines using token_set_ratio
        is_duplicate = any(
            _is_fuzzy_dup(normalized, prev_norm, threshold)
            for prev_norm in kept_normalized
        )

        if not is_duplicate:
            kept_lines.append(line)
            kept_normalized.append(normalized)

    result = '\n'.join(kept_lines)

    # Final enforcement: ensure every content line has year prefix
    from app.services.formatters.timeline_formatter import enforce_timeline_format
    result = enforce_timeline_format(result)

    return result


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
