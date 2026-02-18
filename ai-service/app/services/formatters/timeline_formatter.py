"""
timeline_formatter.py — Centralized Timeline Formatting (Single Source of Truth)

Architecture:
    Builder (raw content) → Formatter (year format) → Postprocessor (enforce) → Guardrail (validate)

This module is the ONLY place that applies "Năm XXXX, content" format.
No other module should format year prefixes.

Functions:
    extract_year     — Extract year from event dict or fallback from story text
    format_timeline_entry — Apply canonical format: "Năm {year}, {content}"
    enforce_timeline_format — Per-line enforcement on final answer text
    strip_bold       — Remove all ** bold markers from text
"""

import re
from typing import Optional


# ── Year extraction regex ────────────────────────────────────────
_YEAR_IN_TEXT_RE = re.compile(
    r'\b(?:[Nn]ăm\s+)?\*{0,2}(\d{3,4})\*{0,2}\b'
)

# ── Cleanup patterns — strip existing year prefixes ──────────────
_BOLD_YEAR_PREFIX_RE = re.compile(
    r'^\*{0,2}[Nn]ăm\s+\*{0,2}\d{3,4}\*{0,2}[,:;.]?\*{0,2}\s*'
)
_STANDALONE_YEAR_RE = re.compile(
    r'^\*{0,2}\d{3,4}\*{0,2}\s*$'
)
_BULLET_PREFIX_RE = re.compile(
    r'^[-•]\s*'
)

# Lines to skip during enforcement (headers, intros, short lines)
_SKIP_PATTERNS = (
    'đây là', 'trong lịch sử', 'lịch sử việt nam',
    'tóm lại', 'như vậy', 'kết luận',
    '✅', '❌',
)


def strip_bold(text: str) -> str:
    """Remove all ** bold markers from text."""
    return text.replace('**', '') if text else text


def extract_year(event: dict, story: str = "") -> Optional[int]:
    """
    Extract year from event dict, with fallback from story text.

    Priority:
    1. event["year"] (if truthy and valid)
    2. First valid year (40–2025) found in story text

    Returns:
        Year as int, or None if no valid year found.
    """
    year = event.get("year") if isinstance(event, dict) else None

    # Validate year from event
    if year:
        try:
            y = int(year)
            if 40 <= y <= 2025:
                return y
        except (ValueError, TypeError):
            pass

    # Fallback: extract from story text
    if story:
        for m in _YEAR_IN_TEXT_RE.finditer(story):
            y = int(m.group(1))
            if 40 <= y <= 2025:
                return y

    return None


def format_timeline_entry(year: Optional[int], story: str) -> str:
    """
    Apply canonical timeline format: "Năm {year}, {content}"

    This is the SINGLE SOURCE OF TRUTH for year prefix formatting.

    Steps:
    0. Strip all ** bold markers
    1. Strip any existing year prefix from story (bold, plain, standalone)
    2. Strip duplicate "Năm XXXX" inside story text
    3. Apply canonical format

    Args:
        year: Year to prefix (or None for no prefix)
        story: Raw event content text

    Returns:
        Formatted string: "Năm {year}, {content}" or raw content if no year.
    """
    if not story:
        return story or ""

    # Step 0: Strip all bold markers FIRST
    story = strip_bold(story).strip()

    if not year:
        return story

    # Step 1: Remove any existing year prefix at start of story
    story = _BOLD_YEAR_PREFIX_RE.sub('', story).strip()

    # Step 2: Remove "Năm {year}" at start of story (exact year match)
    story = re.sub(
        rf'^[Nn]ăm\s+{year}[,:;]?\s*',
        '',
        story
    ).strip()

    # Step 3: Remove standalone year number at start
    story = re.sub(
        rf'^{year}[,:;]?\s*',
        '',
        story
    ).strip()

    # Step 4: Remove mid-text "năm {year}" to avoid duplication
    story = re.sub(
        rf'\s+[Nn]ăm\s+{year}[,:;]?\s*',
        ' ',
        story
    ).strip()

    if not story:
        return f"Năm {year}."

    # Capitalize first letter of content
    story = story[0].upper() + story[1:] if len(story) > 1 else story.upper()

    return f"Năm {year}, {story}"


def enforce_timeline_format(answer_text: str) -> str:
    """
    Final enforcement pass: strip ** bold markers and ensure
    every content line has year prefix.

    Scans the full answer text line-by-line:
    1. Strips ** bold markers from every line
    2. Applies format_timeline_entry to lines missing a year prefix

    Skips year enforcement for:
    - Empty lines
    - Headers (###, ##, #)
    - Short lines (< 30 chars — likely formatting)
    - Intro/context lines ("Đây là", "✅", "❌")

    This runs AFTER all formatting and dedup, as the absolute last step.
    """
    if not answer_text:
        return answer_text

    lines = answer_text.split('\n')
    result = []

    for line in lines:
        stripped = line.strip()

        # Keep empty lines as-is
        if not stripped:
            result.append(line)
            continue

        # Strip bold markers from ALL lines
        stripped = strip_bold(stripped)

        # Keep headers (# / ## / ###) as-is (already bold-stripped)
        if stripped.startswith('#'):
            result.append(stripped)
            continue

        # Keep short lines as-is (already bold-stripped)
        if len(stripped) < 30:
            result.append(stripped)
            continue

        # Skip intro/context patterns (already bold-stripped)
        lower = stripped.lower()
        if any(lower.startswith(p) for p in _SKIP_PATTERNS):
            result.append(stripped)
            continue

        # Already has year marker at START → keep (already bold-stripped)
        if re.match(r'(?:[-•]\s*)?[Nn]ăm\s+\d{3,4}[,.]', stripped):
            result.append(stripped)
            continue

        # Try to extract year from the line and apply format
        bullet = ''
        content = stripped
        bullet_match = _BULLET_PREFIX_RE.match(content)
        if bullet_match:
            bullet = bullet_match.group(0)
            content = content[len(bullet):]

        year = None
        for m in _YEAR_IN_TEXT_RE.finditer(content):
            y = int(m.group(1))
            if 40 <= y <= 2025:
                year = y
                break

        if year:
            formatted = format_timeline_entry(year, content)
            result.append(f"{bullet}{formatted}")
        else:
            # No year found — keep bold-stripped line
            result.append(stripped)

    return '\n'.join(result)
