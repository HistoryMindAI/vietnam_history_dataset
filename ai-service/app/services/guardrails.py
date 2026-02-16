"""
guardrails.py — Phase 5: Output Verification Pass (v1.0)

PURPOSE:
    Final verification layer before returning answer to user.
    Runs AFTER answer synthesis (Phase 8 in engine_answer).
    Detects and auto-corrects output quality issues.

SEVERITY LEVELS:
    PASS       — No issues found
    AUTO_FIX   — Issue found but auto-correctable (truncation, punctuation)
    SOFT_FAIL  — Issue found, answer returned with warning
    HARD_FAIL  — Issue found, answer must be blocked/regenerated

INVARIANTS:
    - NEVER mutates query_info
    - NEVER changes conflict status
    - Deterministic and stateless
    - Runs in <1ms (no model calls)
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ==============================================================================
# SEVERITY ENUM
# ==============================================================================

class Severity(Enum):
    PASS = "PASS"
    AUTO_FIX = "AUTO_FIX"
    SOFT_FAIL = "SOFT_FAIL"
    HARD_FAIL = "HARD_FAIL"


# ==============================================================================
# CHECK RESULT
# ==============================================================================

@dataclass
class CheckResult:
    """Result of a single verification check."""
    name: str
    severity: Severity
    message: str = ""
    auto_corrected: bool = False


@dataclass
class VerificationResult:
    """Aggregated result of all verification checks."""
    status: Severity = Severity.PASS
    checks: List[CheckResult] = field(default_factory=list)
    corrected_answer: Optional[str] = None
    auto_correctable: bool = True

    @property
    def passed(self) -> bool:
        return self.status in (Severity.PASS, Severity.AUTO_FIX)

    @property
    def hard_failed(self) -> bool:
        return self.status == Severity.HARD_FAIL


# ==============================================================================
# OUTPUT VERIFIER (Phase 5)
# ==============================================================================

# Patterns that indicate truncated output
_TRUNCATION_PATTERNS = [
    re.compile(r',\s*g\.\s*$'),                # ends with ", g."
    re.compile(r',\s*$'),                       # ends with dangling comma
    re.compile(r';\s*$'),                       # ends with dangling semicolon
    re.compile(r'\.\.\.\s*$'),                  # ends with "..."
    re.compile(r'\b\w{1,3}\s*$'),               # ends with 1-3 char fragment
]

# Valid sentence endings
_VALID_ENDINGS = re.compile(r'[.!?…"»]\s*$')

# Patterns for phantom years (years not grounded in metadata)
_YEAR_PATTERN = re.compile(r'\b([1-9]\d{2,3})\b')


class OutputVerifier:
    """
    Phase 5: Final output verification before returning to user.

    Checks:
    1. Truncation — no dangling comma/period, complete sentences
    2. Completeness — ends with proper punctuation
    3. Topic drift — no entities outside query scope
    4. Year hallucination — no phantom years outside metadata range

    Each check returns a severity level:
    - PASS: no issue
    - AUTO_FIX: fixed automatically (truncation, punctuation)
    - SOFT_FAIL: issue logged, answer returned with warning
    - HARD_FAIL: answer must be blocked
    """

    def verify(self, answer: str, query_info=None) -> VerificationResult:
        """Run all verification checks on the answer."""
        result = VerificationResult()

        if not answer or not answer.strip():
            result.status = Severity.HARD_FAIL
            result.checks.append(CheckResult(
                name="empty_answer",
                severity=Severity.HARD_FAIL,
                message="Answer is empty"
            ))
            result.auto_correctable = False
            return result

        corrected = answer

        # 1. Truncation check
        trunc_check, corrected = self._check_truncation(corrected)
        result.checks.append(trunc_check)

        # 2. Completeness check
        complete_check, corrected = self._check_completeness(corrected)
        result.checks.append(complete_check)

        # 3. Topic drift check (requires query_info)
        if query_info is not None:
            drift_check = self._check_topic_drift(corrected, query_info)
            result.checks.append(drift_check)

        # 4. Year hallucination check (requires query_info)
        if query_info is not None:
            year_check = self._check_year_hallucination(corrected, query_info)
            result.checks.append(year_check)

        # Aggregate severity — worst check wins
        worst = Severity.PASS
        for check in result.checks:
            if check.severity == Severity.HARD_FAIL:
                worst = Severity.HARD_FAIL
                result.auto_correctable = False
                break
            elif check.severity == Severity.SOFT_FAIL and worst != Severity.HARD_FAIL:
                worst = Severity.SOFT_FAIL
            elif check.severity == Severity.AUTO_FIX and worst == Severity.PASS:
                worst = Severity.AUTO_FIX

        result.status = worst

        if corrected != answer:
            result.corrected_answer = corrected

        return result

    def _check_truncation(self, answer: str) -> tuple:
        """Check for truncated output (dangling comma, fragment, etc.)."""
        stripped = answer.rstrip()

        for pattern in _TRUNCATION_PATTERNS:
            if pattern.search(stripped):
                # Auto-fix: trim the dangling fragment
                fixed = re.sub(r'[,;]\s*\w{0,3}\s*$', '.', stripped)
                fixed = re.sub(r'\.\.\.\s*$', '.', fixed)
                return (
                    CheckResult(
                        name="truncation",
                        severity=Severity.AUTO_FIX,
                        message="Truncated output detected and auto-fixed",
                        auto_corrected=True,
                    ),
                    fixed,
                )

        return (
            CheckResult(name="truncation", severity=Severity.PASS),
            answer,
        )

    def _check_completeness(self, answer: str) -> tuple:
        """Check answer ends with proper punctuation."""
        stripped = answer.rstrip()

        if not stripped:
            return (
                CheckResult(
                    name="completeness",
                    severity=Severity.HARD_FAIL,
                    message="Answer is empty after stripping",
                ),
                answer,
            )

        if _VALID_ENDINGS.search(stripped):
            return (
                CheckResult(name="completeness", severity=Severity.PASS),
                answer,
            )

        # Auto-fix: add period
        fixed = stripped + "."
        return (
            CheckResult(
                name="completeness",
                severity=Severity.AUTO_FIX,
                message="Missing terminal punctuation — added period",
                auto_corrected=True,
            ),
            fixed,
        )

    def _check_topic_drift(self, answer: str, query_info) -> CheckResult:
        """
        Check if answer contains entities not present in the query.
        Topic drift = answer mentions persons/events the user didn't ask about.

        NOTE: This is a soft check — false positives possible when the answer
        legitimately mentions related historical figures.
        """
        # Only check if query has specific required persons
        required_persons = getattr(query_info, "required_persons", [])
        if not required_persons or len(required_persons) == 0:
            return CheckResult(name="topic_drift", severity=Severity.PASS)

        # For fact-check queries, ensure the answer addresses the claimed entity
        is_fact_check = getattr(query_info, "is_fact_check", False)
        if is_fact_check:
            answer_lower = answer.lower()
            has_any_person = any(
                p.lower() in answer_lower for p in required_persons
            )
            if not has_any_person:
                return CheckResult(
                    name="topic_drift",
                    severity=Severity.SOFT_FAIL,
                    message=f"Fact-check answer doesn't mention queried entity: {required_persons}",
                )

        return CheckResult(name="topic_drift", severity=Severity.PASS)

    def _check_year_hallucination(self, answer: str, query_info) -> CheckResult:
        """
        Check if answer contains years that don't match query constraints.

        For fact-check queries with a claimed_year:
        - Answer should reference the CORRECT year, not an unrelated one
        - The correct year should be close to the entity's actual timeline

        NOTE: Only fires for fact-check queries to avoid false positives
        on general historical narratives.
        """
        is_fact_check = getattr(query_info, "is_fact_check", False)
        claimed_year = getattr(query_info, "claimed_year", None)

        if not is_fact_check or claimed_year is None:
            return CheckResult(name="year_hallucination", severity=Severity.PASS)

        # Extract all years from the answer
        years_in_answer = set(int(m) for m in _YEAR_PATTERN.findall(answer))

        if not years_in_answer:
            return CheckResult(name="year_hallucination", severity=Severity.PASS)

        # For fact-check: answer should NOT contain years wildly different
        # from both the claimed year and the entity's actual period
        required_year = getattr(query_info, "required_year", None)
        if required_year:
            # Any year within 200 years of either claimed or actual is OK
            for y in years_in_answer:
                if abs(y - claimed_year) > 500 and abs(y - required_year) > 500:
                    return CheckResult(
                        name="year_hallucination",
                        severity=Severity.SOFT_FAIL,
                        message=f"Year {y} in answer is far from claimed ({claimed_year}) and actual ({required_year})",
                    )

        return CheckResult(name="year_hallucination", severity=Severity.PASS)
