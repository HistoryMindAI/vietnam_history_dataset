"""
entity_normalizer.py — Output-Level Entity Normalization

Fixes three classes of entity bugs in answer text:
1. Truncated names: "Hồ C." → "Hồ Chí Minh"
2. Alias inconsistency: ensures first-mention canonical annotation
3. Redundant pronouns: "của Bác" when "Hồ Chí Minh" already used

Uses PERSON_ALIASES from startup (already loaded from knowledge_base.json).
Applied AFTER answer synthesis, BEFORE guardrails.
"""

import re
from collections import defaultdict
from typing import Dict, Optional

import app.core.startup as startup


# ===================================================================
# TRUNCATED NAME DETECTION
# ===================================================================

# Pattern: Vietnamese proper noun followed by single initial + period
# Matches: "Hồ C.", "Nguyễn T.", "Trần H."
# Does NOT match: "v.v.", "Tr.CN"
_TRUNCATED_NAME_RE = re.compile(
    r'\b([A-ZĐÀ-Ỹ][a-zà-ỹ]+)\s+([A-ZĐÀ-Ỹ])\.'
)


def _build_reverse_aliases() -> Dict[str, list]:
    """
    Build canonical → [all aliases] reverse mapping from PERSON_ALIASES.
    PERSON_ALIASES is alias_lower → canonical_lower.
    We need canonical → [alias1, alias2, ...] including title-cased forms.
    """
    reverse: Dict[str, list] = defaultdict(list)
    for alias, canonical in startup.PERSON_ALIASES.items():
        if alias != canonical:
            reverse[canonical].append(alias)
    return dict(reverse)


def expand_truncated_names(text: str) -> str:
    """
    Detect and expand truncated names like "Hồ C." → "Hồ Chí Minh".

    Strategy:
    1. Find truncated pattern: "FirstName X."
    2. Search PERSON_ALIASES for canonical names starting with "FirstName X"
    3. Replace with full canonical name
    """
    if not text:
        return text

    aliases = startup.PERSON_ALIASES

    def _expand_match(m: re.Match) -> str:
        first_part = m.group(1)   # e.g. "Hồ"
        initial = m.group(2)      # e.g. "C"
        prefix = f"{first_part.lower()} {initial.lower()}"

        # Search for canonical name matching this prefix
        for alias, canonical in aliases.items():
            if alias.startswith(prefix) and len(alias) > len(prefix):
                # Return title-cased canonical
                return canonical.title()
            if canonical.startswith(prefix) and len(canonical) > len(prefix):
                return canonical.title()

        # No match found — return original
        return m.group(0)

    return _TRUNCATED_NAME_RE.sub(_expand_match, text)


# ===================================================================
# REDUNDANT PRONOUN REMOVAL
# ===================================================================

# Common Vietnamese informal pronouns/titles used for historical figures
_INFORMAL_REFS = [
    (re.compile(r'\bcủa\s+Bác\b'), 'của Người'),
    (re.compile(r'\bBác\s+Hồ\b'), 'Hồ Chí Minh'),
    (re.compile(r'\bcủa\s+Bác\s+Hồ\b'), 'của Hồ Chí Minh'),
]

# Pattern to detect if canonical name already mentioned in same paragraph
_PARAGRAPH_SPLIT = re.compile(r'\n\n+')


def _remove_redundant_pronouns(text: str) -> str:
    """
    Replace informal pronoun references when the canonical name
    is already mentioned in the same paragraph.

    Example:
        "Hồ Chí Minh ra đi ... của Bác" → "Hồ Chí Minh ra đi ... của Người"

    NOTE: Only replaces when canonical name is already present,
    to avoid incorrectly expanding in contexts where "Bác" is appropriate.
    """
    if not text:
        return text

    paragraphs = _PARAGRAPH_SPLIT.split(text)
    result_paragraphs = []

    for para in paragraphs:
        para_lower = para.lower()

        # Check if "hồ chí minh" or "nguyễn tất thành" is already in this paragraph
        has_canonical = (
            "hồ chí minh" in para_lower
            or "nguyễn tất thành" in para_lower
            or "nguyễn ái quốc" in para_lower
        )

        if has_canonical:
            for pattern, replacement in _INFORMAL_REFS:
                para = pattern.sub(replacement, para)

        result_paragraphs.append(para)

    return "\n\n".join(result_paragraphs)


# ===================================================================
# FIRST-MENTION ALIAS ANNOTATION
# ===================================================================

def _annotate_first_mention(text: str) -> str:
    """
    On the first mention of a historical figure known by multiple names,
    add the canonical name in parentheses.

    Example: "Nguyễn Tất Thành rời Bến Nhà Rồng"
           → "Nguyễn Tất Thành (Hồ Chí Minh) rời Bến Nhà Rồng"

    Only annotates if:
    - The name is an alias (not canonical)
    - The canonical name is NOT already in the text
    - Only on the first occurrence
    """
    if not text:
        return text

    aliases = startup.PERSON_ALIASES
    text_lower = text.lower()
    annotated_aliases = set()

    # Sort aliases by length (longest first) to avoid partial matches
    sorted_aliases = sorted(aliases.keys(), key=len, reverse=True)

    for alias in sorted_aliases:
        canonical = aliases[alias]
        # Skip if alias IS the canonical form
        if alias == canonical:
            continue
        # Skip if already annotated
        if alias in annotated_aliases:
            continue
        # Skip if canonical is already in text (no need to annotate)
        if canonical in text_lower:
            continue
        # Skip if alias not in text
        if alias not in text_lower:
            continue

        # Find the alias in original text (case-preserving)
        pattern = re.compile(re.escape(alias), re.IGNORECASE)
        match = pattern.search(text)
        if match:
            original_name = match.group(0)
            canonical_title = canonical.title()
            # Insert annotation after first occurrence only
            annotated = f"{original_name} ({canonical_title})"
            text = text[:match.start()] + annotated + text[match.end():]
            annotated_aliases.add(alias)

    return text


# ===================================================================
# MAIN ENTRY POINT
# ===================================================================

def normalize_entity_names(text: str) -> str:
    """
    Full entity normalization pipeline for answer text.

    Applied in order:
    1. Expand truncated names ("Hồ C." → "Hồ Chí Minh")
    2. Annotate first-mention aliases (add canonical in parentheses)
    3. Remove redundant pronouns ("của Bác" when canonical already present)

    Args:
        text: Answer text from synthesis pipeline

    Returns:
        Normalized text with consistent entity references
    """
    if not text:
        return text

    text = expand_truncated_names(text)
    text = _annotate_first_mention(text)
    text = _remove_redundant_pronouns(text)

    return text
