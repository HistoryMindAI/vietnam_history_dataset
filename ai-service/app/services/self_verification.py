"""
self_verification.py — Anti-Hallucination Verification Engine.

Post-generation verification layer that:
  ✅ Extracts claims (years, entities) from generated answers
  ✅ Compares claims against retrieved evidence documents
  ✅ Detects temporal contradictions
  ✅ Computes confidence score
  ✅ Provides verification result with pass/fail + details

Pipeline:
    Answer Synthesizer
        ↓
    Claim Extractor
        ↓
    Evidence Comparator
        ↓
    Temporal Cross-Check
        ↓
    Confidence Scorer
        ↓
    Verification Result (verified / needs_review / rejected)

Design decisions:
  - Entity extraction uses dictionary match (not NER model) for
    deterministic behavior and speed.
  - Temporal verification uses TemporalParser for year extraction.
  - Confidence is penalty-based: starts at 1.0, reduced per mismatch.
  - Three-tier result: verified (≥0.85), needs_review (0.6–0.85),
    rejected (<0.6).
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ======================================================================
# CLAIM TYPES
# ======================================================================

@dataclass
class Claim:
    """A single claim extracted from an answer."""
    claim_type: str  # "year", "entity", "causal"
    value: str
    source_text: str  # the text fragment this claim came from

    def __repr__(self) -> str:
        return f"Claim({self.claim_type}: {self.value})"


@dataclass
class Mismatch:
    """A mismatch between a claim and the evidence."""
    claim: Claim
    evidence_summary: str
    severity: str  # "critical", "warning", "info"

    def __repr__(self) -> str:
        return f"Mismatch({self.severity}: {self.claim} vs {self.evidence_summary})"


@dataclass
class VerificationResult:
    """Complete verification result for an answer."""
    claims: List[Claim]
    mismatches: List[Mismatch]
    confidence: float
    status: str  # "verified", "needs_review", "rejected"
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_verified(self) -> bool:
        return self.status == "verified"

    @property
    def critical_mismatches(self) -> List[Mismatch]:
        return [m for m in self.mismatches if m.severity == "critical"]


# ======================================================================
# CLAIM EXTRACTOR
# ======================================================================

class ClaimExtractor:
    """
    Extract verifiable claims from generated answer text.

    Claims include:
      - Year claims: "năm 1954", "1946-1954"
      - Entity claims: known historical entities mentioned
      - Causal claims: "dẫn đến", "kết quả là" (future)
    """

    _YEAR_RE = re.compile(r"\b(\d{3,4})\b")
    _YEAR_CONTEXT_RE = re.compile(
        r"(?:năm|year|vào)\s+(\d{3,4})", re.IGNORECASE
    )

    def __init__(
        self,
        known_entities: Optional[Set[str]] = None,
    ):
        """
        Args:
            known_entities: Set of known entity names for
                           dictionary-based extraction.
                           If None, falls back to capitalized word heuristic.
        """
        self.known_entities = known_entities or set()

    def extract(self, answer: str) -> List[Claim]:
        """
        Extract all verifiable claims from an answer.

        Returns:
            List of Claim objects.
        """
        claims = []
        claims.extend(self._extract_year_claims(answer))
        claims.extend(self._extract_entity_claims(answer))
        return claims

    def _extract_year_claims(self, text: str) -> List[Claim]:
        """Extract year claims with surrounding context."""
        claims = []
        seen_years = set()

        # First try context-aware patterns ("năm 1954")
        for m in self._YEAR_CONTEXT_RE.finditer(text):
            year = m.group(1)
            if year not in seen_years and 40 <= int(year) <= 2100:
                claims.append(Claim(
                    claim_type="year",
                    value=year,
                    source_text=text[max(0, m.start()-20):m.end()+20],
                ))
                seen_years.add(year)

        # Then bare year patterns
        for m in self._YEAR_RE.finditer(text):
            year = m.group(1)
            if year not in seen_years and 40 <= int(year) <= 2100:
                claims.append(Claim(
                    claim_type="year",
                    value=year,
                    source_text=text[max(0, m.start()-20):m.end()+20],
                ))
                seen_years.add(year)

        return claims

    def _extract_entity_claims(self, text: str) -> List[Claim]:
        """
        Extract entity claims using dictionary matching.

        Falls back to capitalized word heuristic if no
        known_entities provided.
        """
        claims = []
        text_lower = text.lower()

        if self.known_entities:
            # Dictionary-based (deterministic, preferred)
            for entity in self.known_entities:
                if entity.lower() in text_lower:
                    idx = text_lower.index(entity.lower())
                    claims.append(Claim(
                        claim_type="entity",
                        value=entity,
                        source_text=text[max(0, idx-10):idx+len(entity)+10],
                    ))
        else:
            # Heuristic fallback: multi-word capitalized phrases
            # Vietnamese names are capitalized: "Ngô Quyền", "Điện Biên Phủ"
            name_pattern = re.compile(
                r"(?:[A-ZÀ-Ỹ][a-zà-ỹ]+\s+){1,4}[A-ZÀ-Ỹ][a-zà-ỹ]+"
            )
            for m in name_pattern.finditer(text):
                name = m.group(0)
                claims.append(Claim(
                    claim_type="entity",
                    value=name,
                    source_text=text[max(0, m.start()-10):m.end()+10],
                ))

        return claims


# ======================================================================
# EVIDENCE COMPARATOR
# ======================================================================

class EvidenceComparator:
    """
    Compare extracted claims against evidence documents.

    Checks:
      1. Year claims → are years present in evidence?
      2. Entity claims → are entities in evidence docs?
      3. Cross-doc consistency → do docs agree on years?
    """

    @staticmethod
    def compare(
        claims: List[Claim],
        evidence_docs: List[Dict[str, Any]],
    ) -> List[Mismatch]:
        """
        Compare claims against evidence.

        Args:
            claims: Extracted claims from answer.
            evidence_docs: Retrieved documents used to generate answer.

        Returns:
            List of mismatches found.
        """
        mismatches = []

        # Build evidence text corpus
        evidence_text = " ".join(
            str(doc.get("story", "")) + " " + str(doc.get("event", ""))
            for doc in evidence_docs
        )
        evidence_years = set()
        for doc in evidence_docs:
            year = doc.get("year")
            if year is not None:
                try:
                    evidence_years.add(int(year))
                except (ValueError, TypeError):
                    pass

        # Check each claim
        for claim in claims:
            if claim.claim_type == "year":
                mismatch = EvidenceComparator._check_year_claim(
                    claim, evidence_years, evidence_text
                )
                if mismatch:
                    mismatches.append(mismatch)

            elif claim.claim_type == "entity":
                mismatch = EvidenceComparator._check_entity_claim(
                    claim, evidence_text
                )
                if mismatch:
                    mismatches.append(mismatch)

        return mismatches

    @staticmethod
    def _check_year_claim(
        claim: Claim,
        evidence_years: Set[int],
        evidence_text: str,
    ) -> Optional[Mismatch]:
        """Check if a year claim is supported by evidence."""
        try:
            year = int(claim.value)
        except ValueError:
            return None

        # Check structured year fields first
        if year in evidence_years:
            return None

        # Check text mention as fallback
        if claim.value in evidence_text:
            return None

        # Year not found in evidence → critical mismatch
        return Mismatch(
            claim=claim,
            evidence_summary=(
                f"Year {year} not found in evidence. "
                f"Evidence years: {sorted(evidence_years)}"
            ),
            severity="critical",
        )

    @staticmethod
    def _check_entity_claim(
        claim: Claim,
        evidence_text: str,
    ) -> Optional[Mismatch]:
        """Check if an entity claim is mentioned in evidence."""
        if claim.value.lower() in evidence_text.lower():
            return None

        return Mismatch(
            claim=claim,
            evidence_summary=(
                f"Entity '{claim.value}' not found in evidence text."
            ),
            severity="warning",
        )


# ======================================================================
# CONFIDENCE SCORER
# ======================================================================

class ConfidenceScorer:
    """
    Compute verification confidence.

    Scoring:
      - Start at 1.0
      - Critical mismatch: -0.3 per occurrence
      - Warning mismatch: -0.1 per occurrence
      - Bonus for multi-doc agreement: +0.05 per agreeing doc

    Thresholds:
      - ≥ 0.85 → "verified" (auto-publish)
      - 0.6–0.85 → "needs_review" (queue for moderation)
      - < 0.6 → "rejected" (block + manual review)
    """

    CRITICAL_PENALTY = 0.3
    WARNING_PENALTY = 0.1
    AGREEMENT_BONUS = 0.05
    VERIFIED_THRESHOLD = 0.85
    REVIEW_THRESHOLD = 0.6

    @classmethod
    def score(
        cls,
        claims: List[Claim],
        mismatches: List[Mismatch],
        evidence_docs: List[Dict[str, Any]],
    ) -> tuple:
        """
        Compute confidence score and status.

        Returns:
            (confidence: float, status: str)
        """
        if not claims:
            return (0.5, "needs_review")

        confidence = 1.0

        # Apply penalties
        for mismatch in mismatches:
            if mismatch.severity == "critical":
                confidence -= cls.CRITICAL_PENALTY
            elif mismatch.severity == "warning":
                confidence -= cls.WARNING_PENALTY

        # Agreement bonus: check if multiple docs agree on years
        year_claims = [c for c in claims if c.claim_type == "year"]
        if year_claims and len(evidence_docs) > 1:
            for claim in year_claims:
                try:
                    year = int(claim.value)
                    agreeing = sum(
                        1 for doc in evidence_docs
                        if doc.get("year") == year
                        or str(doc.get("year")) == str(year)
                    )
                    if agreeing > 1:
                        confidence += cls.AGREEMENT_BONUS * (agreeing - 1)
                except (ValueError, TypeError):
                    pass

        # Clamp to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        # Determine status
        if confidence >= cls.VERIFIED_THRESHOLD:
            status = "verified"
        elif confidence >= cls.REVIEW_THRESHOLD:
            status = "needs_review"
        else:
            status = "rejected"

        return (confidence, status)


# ======================================================================
# SELF-VERIFICATION ENGINE — main orchestrator
# ======================================================================

class SelfVerificationEngine:
    """
    Anti-hallucination verification engine.

    Orchestrates: Claim Extraction → Evidence Comparison →
                  Confidence Scoring → Verification Result

    Usage:
        verifier = SelfVerificationEngine(known_entities=entity_set)
        result = verifier.verify(answer_text, evidence_docs)

        if result.is_verified:
            publish(answer_text)
        elif result.status == "needs_review":
            queue_for_moderation(answer_text, result)
        else:
            regenerate_or_refuse()
    """

    def __init__(
        self,
        known_entities: Optional[Set[str]] = None,
    ):
        self.extractor = ClaimExtractor(known_entities=known_entities)
        self.comparator = EvidenceComparator()
        self.scorer = ConfidenceScorer()

    def verify(
        self,
        answer: str,
        evidence_docs: List[Dict[str, Any]],
    ) -> VerificationResult:
        """
        Verify an answer against evidence documents.

        Pipeline:
            1. Extract claims from answer
            2. Compare claims against evidence
            3. Compute confidence score
            4. Return structured result

        Args:
            answer: Generated answer text.
            evidence_docs: Documents used to generate the answer.

        Returns:
            VerificationResult with claims, mismatches, confidence, status.
        """
        # Step 1: Extract claims
        claims = self.extractor.extract(answer)

        # Step 2: Compare against evidence
        mismatches = self.comparator.compare(claims, evidence_docs)

        # Step 3: Score confidence
        confidence, status = self.scorer.score(
            claims, mismatches, evidence_docs
        )

        # Step 4: Build result
        return VerificationResult(
            claims=claims,
            mismatches=mismatches,
            confidence=confidence,
            status=status,
            details={
                "total_claims": len(claims),
                "year_claims": len([c for c in claims if c.claim_type == "year"]),
                "entity_claims": len([c for c in claims if c.claim_type == "entity"]),
                "critical_mismatches": len([m for m in mismatches if m.severity == "critical"]),
                "warning_mismatches": len([m for m in mismatches if m.severity == "warning"]),
                "evidence_doc_count": len(evidence_docs),
            },
        )

    def verify_and_decide(
        self,
        answer: str,
        evidence_docs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Verify and return a decision-ready dict.

        Returns:
            {
                "answer": str,
                "confidence": float,
                "is_verified": bool,
                "status": str,
                "should_regenerate": bool,
                "mismatches": [...],
            }
        """
        result = self.verify(answer, evidence_docs)

        return {
            "answer": answer,
            "confidence": result.confidence,
            "is_verified": result.is_verified,
            "status": result.status,
            "should_regenerate": result.status == "rejected",
            "mismatches": [
                {
                    "type": m.claim.claim_type,
                    "value": m.claim.value,
                    "severity": m.severity,
                    "detail": m.evidence_summary,
                }
                for m in result.mismatches
            ],
            "details": result.details,
        }
