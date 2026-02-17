"""
event_aggregator.py — Event Aggregation Layer.

Maps raw document list → unique canonical events.

Architecture:
    Raw Docs (may have duplicates)
        ↓
    Normalize event keys (strip year prefixes, punctuation, bullets)
        ↓
    Group by (normalized_key, year)
        ↓
    Merge metadata (persons, places, keywords)
        ↓
    Keep longest story per group
        ↓
    Unique event list

This is the CRITICAL layer that prevents duplication at the source.
All downstream components (synthesis, formatting) receive already-unique events.
"""

import re
from typing import Any, Dict, List, Optional


# ======================================================================
# TEXT NORMALIZATION FOR DEDUP
# ======================================================================

# Year prefix patterns to strip for normalization
_YEAR_PREFIX_PATTERNS = [
    re.compile(r'^\(?năm\s+\d{1,4}\)?[,:;\.\s–—-]*\s*', re.IGNORECASE),
    re.compile(r'^vào\s+năm\s+\d{1,4}[,:;\.\s–—-]*\s*', re.IGNORECASE),
    re.compile(r'^\d{3,4}\s*[,:;\.\s–—-]+\s*', re.IGNORECASE),
    re.compile(r'^\(\d{3,4}\)[,:;\.\s–—-]*\s*', re.IGNORECASE),
]

# Bullet / list marker patterns
_BULLET_PATTERNS = re.compile(r'^[-•*]\s+')

# Structural noise
_STRUCTURAL_NOISE = [
    re.compile(r'\*\*', re.IGNORECASE),  # markdown bold
    re.compile(r'^\s*#+\s+', re.IGNORECASE),  # markdown headers
]


def normalize_for_dedup(text: str) -> str:
    """
    Normalize text for deduplication comparison.

    Strips:
      - Year prefixes: "Năm 2010,", "(năm 2010):", "2010: "
      - Bullets: "- ", "• "
      - Markdown: **bold**, ### headers
      - Punctuation
      - Whitespace normalization
      - Lowercase

    Returns canonical text for comparison.
    """
    if not text:
        return ""

    result = text.strip()

    # Strip structural noise FIRST (before year prefixes, so **Năm 2010:** works)
    for pattern in _STRUCTURAL_NOISE:
        result = pattern.sub('', result)

    # Strip bullets
    result = _BULLET_PATTERNS.sub('', result)

    # Re-strip after removing markdown (may have leading whitespace)
    result = result.strip()

    # Strip year prefixes
    for pattern in _YEAR_PREFIX_PATTERNS:
        result = pattern.sub('', result)

    # Lowercase
    result = result.lower()

    # Remove punctuation (keep alphanumeric + Vietnamese chars + spaces)
    result = re.sub(r'[^\w\s]', ' ', result)

    # Collapse whitespace
    result = re.sub(r'\s+', ' ', result).strip()

    return result


# ======================================================================
# EVENT KEY EXTRACTION
# ======================================================================

def _extract_event_key(doc: Dict[str, Any]) -> str:
    """
    Extract a canonical event key from a document.

    Priority: story > event > title.
    Normalized for dedup comparison.
    """
    story = doc.get("story") or doc.get("event") or doc.get("title") or ""
    if not isinstance(story, str):
        story = str(story)
    return normalize_for_dedup(story)


def _get_year(doc: Dict[str, Any]) -> int:
    """Extract normalized year from document. Returns 0 if missing."""
    year = doc.get("year")
    if year is None:
        return 0
    if isinstance(year, (int, float)):
        return int(year)
    try:
        return int(year)
    except (ValueError, TypeError):
        return 0


# ======================================================================
# AGGREGATION
# ======================================================================

def aggregate_events(
    docs: List[Dict[str, Any]],
    similarity_threshold: float = 0.75,
) -> List[Dict[str, Any]]:
    """
    Aggregate raw documents into unique canonical events.

    Groups documents by (normalized_event_key, year).
    For each group, merges metadata and keeps the longest story.

    Args:
        docs: Raw document list (may contain duplicates).
        similarity_threshold: SequenceMatcher threshold for fuzzy matching.

    Returns:
        List of unique events with merged metadata.
    """
    if not docs:
        return []

    from difflib import SequenceMatcher

    # Each cluster: {"doc": best_doc, "key": normalized, "year": int,
    #                "persons": set, "places": set, "story_len": int}
    clusters: List[Dict[str, Any]] = []

    for doc in docs:
        event_key = _extract_event_key(doc)
        year = _get_year(doc)
        story = doc.get("story") or doc.get("event") or ""
        if not isinstance(story, str):
            story = str(story)
        story_len = len(story)

        if not event_key or len(event_key) < 5:
            continue

        # Try to find matching cluster
        matched = False
        for cluster in clusters:
            # Same year (or both zero) AND similar text
            year_match = (
                cluster["year"] == year
                or cluster["year"] == 0
                or year == 0
            )
            if not year_match:
                # Also match if years are within 1 of each other (data noise)
                if abs(cluster["year"] - year) > 1:
                    continue

            # Text similarity check
            if event_key == cluster["key"]:
                # Exact match
                matched = True
            elif event_key in cluster["key"] or cluster["key"] in event_key:
                # Containment
                matched = True
            else:
                # Fuzzy match
                sim = SequenceMatcher(None, event_key, cluster["key"]).ratio()
                if sim >= similarity_threshold:
                    matched = True

            if matched:
                # Merge metadata into existing cluster
                cluster["persons"].update(doc.get("persons") or [])
                cluster["places"].update(doc.get("places") or [])

                # Keep the longer, more detailed story
                if story_len > cluster["story_len"]:
                    cluster["doc"] = doc
                    cluster["key"] = event_key
                    cluster["story_len"] = story_len

                # Prefer non-zero year
                if cluster["year"] == 0 and year != 0:
                    cluster["year"] = year

                break

        if not matched:
            clusters.append({
                "doc": doc,
                "key": event_key,
                "year": year,
                "persons": set(doc.get("persons") or []),
                "places": set(doc.get("places") or []),
                "story_len": story_len,
            })

    # Build result: merge accumulated metadata back into docs
    result = []
    for cluster in clusters:
        doc = cluster["doc"].copy()  # Don't mutate original
        doc["persons"] = list(cluster["persons"])
        doc["places"] = list(cluster["places"])
        if cluster["year"] and not doc.get("year"):
            doc["year"] = cluster["year"]
        result.append(doc)

    return result
