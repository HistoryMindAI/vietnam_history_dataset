"""
benchmark.py — Production Evaluation Benchmark Framework.

Measures accuracy, temporal correctness, entity accuracy,
hallucination rate, and latency against a gold dataset.

Architecture:
    Gold Dataset (Q&A JSON)
        ↓
    EvaluationRunner
        ↓
    ScoringEngine
        ↓
    Metrics Report

Metrics:
  - Exact Match
  - F1 Score (token overlap)
  - Temporal Accuracy (year correctness)
  - Entity Accuracy (entity mention correctness)
  - Hallucination Rate (claims without evidence)
  - Latency (response time)

Target thresholds (production-grade):
  - Overall accuracy:  ≥ 90%
  - Temporal accuracy: ≥ 95%
  - Hallucination rate: ≤ 3%
  - Multi-hop accuracy: ≥ 85%
  - Latency:           < 2.5s
"""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


# ======================================================================
# BENCHMARK ITEM
# ======================================================================

@dataclass
class BenchmarkItem:
    """A single evaluation question with gold answer."""
    id: str
    question: str
    gold_answer: str
    expected_entities: List[str] = field(default_factory=list)
    expected_years: List[int] = field(default_factory=list)
    query_type: str = "general"
    difficulty: str = "medium"
    multi_hop: bool = False
    temporal_constraint: bool = False


@dataclass
class EvalResult:
    """Result for a single benchmark item."""
    item_id: str
    question: str
    engine_answer: str
    gold_answer: str
    exact_match: bool
    f1_score: float
    temporal_accuracy: float
    entity_accuracy: float
    hallucination_detected: bool
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Aggregate report for entire benchmark run."""
    total_items: int
    results: List[EvalResult]
    metrics: Dict[str, float]
    timestamp: str = ""

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"=== Benchmark Report ({self.total_items} items) ===",
        ]
        for key, value in self.metrics.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.2%}")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)


# ======================================================================
# SCORING UTILITIES
# ======================================================================

def compute_f1(prediction: str, gold: str) -> float:
    """
    Token-level F1 score between prediction and gold answer.

    Tokenizes by whitespace and computes precision/recall overlap.
    """
    pred_tokens = set(prediction.lower().split())
    gold_tokens = set(gold.lower().split())

    if not pred_tokens or not gold_tokens:
        return 0.0

    common = pred_tokens & gold_tokens
    if not common:
        return 0.0

    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gold_tokens)

    return 2 * precision * recall / (precision + recall)


def check_temporal_accuracy(
    answer: str,
    expected_years: List[int],
) -> float:
    """
    Check if expected years appear in the answer.

    Returns fraction of expected years found.
    """
    if not expected_years:
        return 1.0

    found = 0
    for year in expected_years:
        if str(year) in answer:
            found += 1

    return found / len(expected_years)


def check_entity_accuracy(
    answer: str,
    expected_entities: List[str],
) -> float:
    """
    Check if expected entities appear in the answer.

    Case-insensitive substring matching.
    """
    if not expected_entities:
        return 1.0

    answer_lower = answer.lower()
    found = 0
    for entity in expected_entities:
        if entity.lower() in answer_lower:
            found += 1

    return found / len(expected_entities)


def detect_hallucination(
    answer: str,
    gold_answer: str,
    expected_years: List[int],
) -> bool:
    """
    Simple hallucination detection.

    Checks if answer contains years not in expected set
    or gold answer.
    """
    _YEAR_RE = re.compile(r"\b(\d{3,4})\b")
    answer_years = {
        int(y) for y in _YEAR_RE.findall(answer)
        if 40 <= int(y) <= 2100
    }
    gold_years = {
        int(y) for y in _YEAR_RE.findall(gold_answer)
        if 40 <= int(y) <= 2100
    }

    expected_set = set(expected_years) | gold_years

    # If answer mentions years not in expected set → possible hallucination
    unexpected = answer_years - expected_set
    return len(unexpected) > 0


# ======================================================================
# EVALUATION RUNNER
# ======================================================================

class EvaluationRunner:
    """
    Run benchmark evaluation against the engine.

    Usage:
        runner = EvaluationRunner(
            engine_fn=lambda q: engine.answer(q),
            dataset_path="evaluation/adversarial_queries.json"
        )
        report = runner.run()
        print(report.summary())
    """

    # Production thresholds
    THRESHOLDS = {
        "overall_accuracy": 0.90,
        "temporal_accuracy": 0.95,
        "hallucination_rate": 0.03,
        "multi_hop_accuracy": 0.85,
        "max_latency_ms": 2500,
    }

    def __init__(
        self,
        engine_fn: Callable[[str], str],
        dataset: Optional[List[BenchmarkItem]] = None,
        dataset_path: Optional[str] = None,
    ):
        """
        Args:
            engine_fn: Function that takes a question and returns answer str.
            dataset: List of BenchmarkItem objects.
            dataset_path: Path to JSON dataset file.
        """
        self.engine_fn = engine_fn
        self.dataset = dataset or []

        if dataset_path and not self.dataset:
            self.dataset = self._load_dataset(dataset_path)

    def run(self) -> BenchmarkReport:
        """
        Run evaluation on all benchmark items.

        Returns:
            BenchmarkReport with per-item results and aggregate metrics.
        """
        results = []

        for item in self.dataset:
            result = self._evaluate_item(item)
            results.append(result)

        metrics = self._aggregate_metrics(results)

        return BenchmarkReport(
            total_items=len(results),
            results=results,
            metrics=metrics,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _evaluate_item(self, item: BenchmarkItem) -> EvalResult:
        """Evaluate a single benchmark item."""
        start = time.time()
        try:
            answer = self.engine_fn(item.question)
        except Exception as e:
            answer = f"[ERROR] {e}"
        latency_ms = (time.time() - start) * 1000

        return EvalResult(
            item_id=item.id,
            question=item.question,
            engine_answer=answer,
            gold_answer=item.gold_answer,
            exact_match=(
                answer.strip().lower() == item.gold_answer.strip().lower()
            ),
            f1_score=compute_f1(answer, item.gold_answer),
            temporal_accuracy=check_temporal_accuracy(
                answer, item.expected_years
            ),
            entity_accuracy=check_entity_accuracy(
                answer, item.expected_entities
            ),
            hallucination_detected=detect_hallucination(
                answer, item.gold_answer, item.expected_years
            ),
            latency_ms=latency_ms,
            details={
                "query_type": item.query_type,
                "difficulty": item.difficulty,
                "multi_hop": item.multi_hop,
            },
        )

    def _aggregate_metrics(
        self, results: List[EvalResult]
    ) -> Dict[str, float]:
        """Compute aggregate metrics from individual results."""
        if not results:
            return {}

        n = len(results)
        metrics = {
            "exact_match_rate": sum(r.exact_match for r in results) / n,
            "avg_f1_score": sum(r.f1_score for r in results) / n,
            "temporal_accuracy": sum(r.temporal_accuracy for r in results) / n,
            "entity_accuracy": sum(r.entity_accuracy for r in results) / n,
            "hallucination_rate": sum(
                r.hallucination_detected for r in results
            ) / n,
            "avg_latency_ms": sum(r.latency_ms for r in results) / n,
            "p95_latency_ms": sorted(
                r.latency_ms for r in results
            )[int(n * 0.95)] if n > 1 else results[0].latency_ms,
        }

        # Multi-hop accuracy (subset)
        multi_hop = [
            r for r in results if r.details.get("multi_hop")
        ]
        if multi_hop:
            metrics["multi_hop_accuracy"] = sum(
                r.f1_score > 0.5 for r in multi_hop
            ) / len(multi_hop)

        # Pass/fail against thresholds
        metrics["passes_thresholds"] = all([
            metrics["temporal_accuracy"] >= self.THRESHOLDS["temporal_accuracy"],
            metrics["hallucination_rate"] <= self.THRESHOLDS["hallucination_rate"],
            metrics["avg_latency_ms"] <= self.THRESHOLDS["max_latency_ms"],
        ])

        return metrics

    @staticmethod
    def _load_dataset(path: str) -> List[BenchmarkItem]:
        """Load benchmark dataset from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = []
        for item in data:
            items.append(BenchmarkItem(
                id=item.get("id", ""),
                question=item.get("question", ""),
                gold_answer=item.get("gold_answer", ""),
                expected_entities=item.get("expected_entities", []),
                expected_years=item.get("expected_years", []),
                query_type=item.get("query_type", "general"),
                difficulty=item.get("difficulty", "medium"),
                multi_hop=item.get("multi_hop", False),
                temporal_constraint=item.get("temporal_constraint", False),
            ))

        return items
