"""
semantic_layer.py — Phase 4: Soft Semantic Interpretation Layer (v4.0)

PURPOSE:
    Non-blocking, friendly analysis layer that runs AFTER Phase 1-3 hard validators.
    Provides contextual notes, warnings, and alias expansions WITHOUT setting conflicts.

INVARIANTS:
    - NEVER sets has_conflict = True
    - NEVER mutates entity_metadata
    - NEVER overrides relation_type or normalization
    - Deterministic and order-independent
    - Only runs when has_conflict == False (skipped on HARD conflict)

TONE:
    Thân thiện kiểu "Tớ và Mình" — không dạy đời, không quyền lực.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ==============================================================================
# DATA MODEL
# ==============================================================================

@dataclass
class SemanticResult:
    """Output of semantic analysis — notes, warnings, and alias expansions."""
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    expansions: Dict[str, List[str]] = field(default_factory=dict)


# ==============================================================================
# FRIENDLY FORMATTER (Tớ + Mình tone)
# ==============================================================================

class FriendlyHistoryAssistant:
    """Static formatters producing friendly Vietnamese explanations."""

    @staticmethod
    def explain_soft_mismatch(person: str, dynasty: str) -> str:
        return (
            f"🤔 Mình thấy {person} không trực tiếp thuộc {dynasty} đâu, "
            f"nhưng có thể có liên hệ thời kỳ lân cận đó."
        )

    @staticmethod
    def explain_overlap(person1: str, person2: str) -> str:
        return (
            f"📚 Tớ nhận thấy {person1} và {person2} "
            f"có giai đoạn sống trùng nhau nhé!"
        )

    @staticmethod
    def explain_alias(alias: str, canonical: str) -> str:
        return (
            f"✨ '{alias}' thường được hiểu là '{canonical}'. "
            f"Mình đã mở rộng giúp cậu cho rõ nghĩa hơn."
        )

    @staticmethod
    def explain_person_era_difference(p1: str, p2: str) -> str:
        return (
            f"⚠ Tớ để ý thấy {p1} và {p2} thuộc hai triều đại khác nhau đó. "
            f"Mình kiểm tra lại ngữ cảnh một chút nhé!"
        )


# ==============================================================================
# ALIAS MAP (Immutable)
# ==============================================================================

_ALIAS_MAP: Dict[str, str] = {
    "đàng ngoài": "Trịnh",
    "đàng trong": "Nguyễn",
    "nam triều": "Lê Trung Hưng",
    "bắc triều": "Mạc",
}


# ==============================================================================
# SEMANTIC ANALYZER (Production-Safe)
# ==============================================================================

class SemanticAnalyzer:
    """
    Soft semantic analysis — non-blocking, friendly.

    Runs AFTER Phase 1-3 hard validators.
    Never sets has_conflict. Never mutates metadata.
    """

    def __init__(self, metadata: dict):
        # Read-only reference — never mutate
        self._metadata = metadata

    def analyze(self, query_info) -> SemanticResult:
        """
        Run all soft semantic checks.
        Returns SemanticResult with notes, warnings, expansions.

        NOTE: Caller (detect()) is responsible for skipping when has_conflict.
        This keeps the analyzer pure — no conflict-state awareness.
        """
        result = SemanticResult()

        self._expand_aliases(query_info, result)
        self._soft_person_overlap(query_info, result)
        self._soft_person_alignment(query_info, result)

        return result

    def _expand_aliases(self, query_info, result: SemanticResult) -> None:
        """Expand known historical aliases (non-mutating)."""
        for entity in query_info.required_persons:
            key = entity.lower().strip()

            if key in _ALIAS_MAP:
                canonical = _ALIAS_MAP[key]

                # Do NOT mutate entity list — only record expansion
                result.expansions[entity] = [canonical]

                result.notes.append(
                    FriendlyHistoryAssistant.explain_alias(entity, canonical)
                )

    def _soft_person_overlap(self, query_info, result: SemanticResult) -> None:
        """Note when multiple persons share temporal overlap (all pairs)."""
        # Deduplicate by lowercase key to avoid duplicate notes for repeated entities
        seen_keys: set = set()
        persons = []
        for e in query_info.required_persons:
            key = e.lower().strip()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            meta = self._metadata.get(key)
            if meta and meta.get("type") == "person":
                lifespan = meta.get("lifespan")
                if lifespan:
                    persons.append((e, lifespan))

        if len(persons) < 2:
            return

        # Check ALL pairs — not just the first two
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                p1_name, p1_span = persons[i]
                p2_name, p2_span = persons[j]
                pair_start = max(p1_span[0], p2_span[0])
                pair_end = min(p1_span[1], p2_span[1])
                if pair_start <= pair_end:
                    result.notes.append(
                        FriendlyHistoryAssistant.explain_overlap(p1_name, p2_name)
                    )

    def _soft_person_alignment(self, query_info, result: SemanticResult) -> None:
        """Warn when two persons belong to different eras."""
        persons = []
        for e in query_info.required_persons:
            key = e.lower().strip()
            meta = self._metadata.get(key)
            if meta and meta.get("type") == "person":
                persons.append((e, meta))

        if len(persons) != 2:
            return

        p1_name, p1_meta = persons[0]
        p2_name, p2_meta = persons[1]

        era1 = p1_meta.get("era", [])
        era2 = p2_meta.get("era", [])

        if era1 and era2:
            if not any(e in era2 for e in era1):
                result.warnings.append(
                    FriendlyHistoryAssistant.explain_person_era_difference(
                        p1_name, p2_name
                    )
                )
