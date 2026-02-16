"""
temporal_engine.py — Production Temporal Reasoning Engine V2.

Upgrade from V1 skeleton to full reasoning layer:
  ✅ TimeRange dataclass — overlaps, before, after, contains, duration
  ✅ TemporalEvent dataclass — named event with time range
  ✅ TemporalReasoner — events_after, events_before, events_during, range_between
  ✅ Temporal conflict detection — detect year mismatches between docs
  ✅ Temporal majority voting — weight by agreement count
  ✅ Century/Decade/RelativeTime parsing
  ✅ TemporalDataSource — connects to startup.DOCUMENTS

Core design principles:
  ✅ No embedding — uses metadata indexes only
  ✅ No rerank — no probabilistic scoring
  ✅ 100% deterministic — same input → same output always

Pipeline integration:
    Hybrid Retriever
        ↓
    Temporal Filter
        ↓
    Temporal Reasoner
        ↓
    Answer Synthesizer
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.temporal.comparator import Comparator
from app.temporal.duration_calculator import DurationCalculator
from app.temporal.temporal_intent import TemporalIntent
from app.temporal.timeline_resolver import TimelineResolver


# ======================================================================
# CORE DATA STRUCTURES
# ======================================================================

@dataclass
class TimeRange:
    """
    Represents a time interval [start, end] inclusive.

    Supports:
      - Single year events: TimeRange(1954, 1954)
      - Multi-year periods: TimeRange(1946, 1954)
      - Open-ended:         TimeRange(1945, None) — ongoing
    """
    start: int
    end: Optional[int] = None

    def __post_init__(self):
        if self.end is None:
            self.end = self.start

    @property
    def duration(self) -> int:
        """Duration in years (inclusive)."""
        return (self.end or self.start) - self.start + 1

    def overlaps(self, other: "TimeRange") -> bool:
        """Check if two time ranges overlap."""
        return not (
            (self.end or self.start) < other.start
            or self.start > (other.end or other.start)
        )

    def before(self, other: "TimeRange") -> bool:
        """Check if this range ends before another starts."""
        return (self.end or self.start) < other.start

    def after(self, other: "TimeRange") -> bool:
        """Check if this range starts after another ends."""
        return self.start > (other.end or other.start)

    def contains(self, year: int) -> bool:
        """Check if a year falls within this range."""
        return self.start <= year <= (self.end or self.start)

    def contains_range(self, other: "TimeRange") -> bool:
        """Check if this range fully contains another."""
        return (
            self.start <= other.start
            and (self.end or self.start) >= (other.end or other.start)
        )

    def __repr__(self) -> str:
        if self.start == self.end:
            return f"TimeRange({self.start})"
        return f"TimeRange({self.start}–{self.end})"


@dataclass
class TemporalEvent:
    """
    Named historical event with temporal metadata.

    Wraps TimeRange with event identity for reasoning.
    """
    name: str
    time_range: TimeRange
    description: str = ""
    event_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def start_year(self) -> int:
        return self.time_range.start

    @property
    def end_year(self) -> int:
        return self.time_range.end or self.time_range.start

    @property
    def duration(self) -> int:
        return self.time_range.duration


# ======================================================================
# TEMPORAL PARSERS
# ======================================================================

class TemporalParser:
    """
    Parse temporal expressions from text into TimeRange objects.

    Supports:
      - Exact years: "1954" → TimeRange(1954, 1954)
      - Year ranges: "1946-1954" → TimeRange(1946, 1954)
      - Centuries: "thế kỷ 19" → TimeRange(1800, 1899)
      - Decades: "thập niên 1930" → TimeRange(1930, 1939)
      - Relative: "cuối thế kỷ 19" → TimeRange(1870, 1899)
    """

    _YEAR_RE = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")
    _CENTURY_RE = re.compile(
        r"(?:thế\s+kỷ|century)\s+(\d{1,2})", re.IGNORECASE
    )
    _DECADE_RE = re.compile(
        r"(?:thập\s+niên|decade)\s+(\d{3,4})", re.IGNORECASE
    )
    _RANGE_RE = re.compile(
        r"(\d{3,4})\s*[-–đến]\s*(\d{3,4})"
    )
    _RELATIVE_RE = re.compile(
        r"(đầu|giữa|cuối)\s+thế\s+kỷ\s+(\d{1,2})", re.IGNORECASE
    )

    @classmethod
    def parse(cls, text: str) -> Optional[TimeRange]:
        """
        Parse temporal expression from text.

        Tries patterns in order of specificity:
          1. Relative century ("cuối thế kỷ 19")
          2. Century ("thế kỷ 19")
          3. Decade ("thập niên 1930")
          4. Year range ("1946-1954")
          5. Single year ("1954")
        """
        # 1. Relative century
        m = cls._RELATIVE_RE.search(text)
        if m:
            position = m.group(1).lower()
            century = int(m.group(2))
            base = (century - 1) * 100
            if position in ("đầu",):
                return TimeRange(base, base + 30)
            elif position in ("giữa",):
                return TimeRange(base + 30, base + 70)
            else:  # cuối
                return TimeRange(base + 70, base + 99)

        # 2. Century
        m = cls._CENTURY_RE.search(text)
        if m:
            century = int(m.group(1))
            base = (century - 1) * 100
            return TimeRange(base, base + 99)

        # 3. Decade
        m = cls._DECADE_RE.search(text)
        if m:
            decade = int(m.group(1))
            return TimeRange(decade, decade + 9)

        # 4. Year range
        m = cls._RANGE_RE.search(text)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if start <= end:
                return TimeRange(start, end)

        # 5. Single year
        m = cls._YEAR_RE.search(text)
        if m:
            year = int(m.group(1))
            if 40 <= year <= 2100:
                return TimeRange(year, year)

        return None

    @classmethod
    def parse_all_years(cls, text: str) -> List[int]:
        """Extract all years from text."""
        matches = cls._YEAR_RE.findall(text)
        return [int(y) for y in matches if 40 <= int(y) <= 2100]


# ======================================================================
# TEMPORAL CONFLICT DETECTION
# ======================================================================

@dataclass
class TemporalConflict:
    """Represents a temporal conflict between sources."""
    entity_name: str
    claimed_years: List[int]
    majority_year: int
    confidence: float
    description: str


class TemporalConflictDetector:
    """
    Detect and resolve temporal conflicts between documents.

    When multiple docs claim different years for the same event:
      - Use majority voting to determine the correct year
      - Penalize outlier docs
      - Track confidence based on agreement ratio
    """

    @staticmethod
    def detect_conflicts(
        docs: List[Dict[str, Any]], entity_name: str
    ) -> Optional[TemporalConflict]:
        """
        Detect year conflicts for a named entity across documents.

        Args:
            docs: List of documents mentioning this entity.
            entity_name: Name of the entity to check.

        Returns:
            TemporalConflict if conflict found, None otherwise.
        """
        years = []
        for doc in docs:
            year = doc.get("year")
            if year is not None:
                try:
                    years.append(int(year))
                except (ValueError, TypeError):
                    continue

        if len(years) < 2:
            return None

        # Check for conflicts
        unique_years = set(years)
        if len(unique_years) <= 1:
            return None

        # Majority voting
        from collections import Counter
        year_counts = Counter(years)
        majority_year, majority_count = year_counts.most_common(1)[0]
        confidence = majority_count / len(years)

        return TemporalConflict(
            entity_name=entity_name,
            claimed_years=sorted(unique_years),
            majority_year=majority_year,
            confidence=confidence,
            description=(
                f"Conflict: '{entity_name}' has {len(unique_years)} "
                f"different years: {sorted(unique_years)}. "
                f"Majority: {majority_year} ({confidence:.0%} agreement)."
            ),
        )


# ======================================================================
# TEMPORAL DATA SOURCE
# ======================================================================

class TemporalDataSource:
    """
    Adapter: wraps startup.DOCUMENTS to provide temporal data.

    Connects the TemporalEngine to the existing in-memory indexes
    (DOCUMENTS, ENTITY_TEMPORAL_METADATA, DYNASTY_INDEX, etc.)
    """

    def __init__(self, documents: Optional[List[Dict[str, Any]]] = None):
        self._documents = documents or []
        self._events_cache: Dict[str, List[TemporalEvent]] = {}

    def set_documents(self, documents: List[Dict[str, Any]]):
        """Update documents and clear cache."""
        self._documents = documents
        self._events_cache.clear()

    def get_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Get all entities of a given type with temporal metadata.

        Args:
            entity_type: "dynasty", "person", "war", "event"

        Returns:
            List of entity dicts with start_year, end_year.
        """
        entities = []
        seen_names = set()

        for doc in self._documents:
            name = doc.get("event", "") or doc.get("dynasty", "")
            if not name or name.lower() in seen_names:
                continue

            year = doc.get("year")
            if year is None:
                continue

            # Build entity from document metadata
            entity = {
                "name": name,
                "start_year": doc.get("start_year", year),
                "end_year": doc.get("end_year", year),
                "event_type": doc.get("event_type", entity_type),
                "dynasty": doc.get("dynasty", ""),
            }
            entities.append(entity)
            seen_names.add(name.lower())

        return entities

    def get_entity_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a single entity by name (case-insensitive)."""
        name_lower = name.lower()
        for doc in self._documents:
            event = doc.get("event", "")
            if event and name_lower in event.lower():
                return {
                    "name": event,
                    "start_year": doc.get("start_year", doc.get("year")),
                    "end_year": doc.get("end_year", doc.get("year")),
                    "event_type": doc.get("event_type", ""),
                    "dynasty": doc.get("dynasty", ""),
                }
        return None

    def get_temporal_events(
        self, entity_type: str = "all"
    ) -> List[TemporalEvent]:
        """
        Get TemporalEvent objects for reasoning.

        Caches results per entity_type for performance.
        """
        if entity_type in self._events_cache:
            return self._events_cache[entity_type]

        events = []
        seen = set()

        for doc in self._documents:
            name = doc.get("event", "")
            if not name or name.lower() in seen:
                continue

            year = doc.get("year")
            if year is None:
                continue

            try:
                start = int(doc.get("start_year", year))
                end = int(doc.get("end_year", year))
            except (ValueError, TypeError):
                continue

            event = TemporalEvent(
                name=name,
                time_range=TimeRange(start, end),
                description=doc.get("story", ""),
                event_type=doc.get("event_type", ""),
                metadata=doc,
            )
            events.append(event)
            seen.add(name.lower())

        self._events_cache[entity_type] = events
        return events


# ======================================================================
# TEMPORAL REASONER — the real reasoning layer
# ======================================================================

class TemporalReasoner:
    """
    Full temporal reasoning engine.

    Supports queries like:
      - "Sau Hiệp định Genève điều gì xảy ra?"   → events_after
      - "Trước Điện Biên Phủ?"                   → events_before
      - "Sự kiện năm 1954?"                       → events_during
      - "Sau Điện Biên Phủ nhưng trước Mậu Thân?" → range_between
      - "Sự kiện cùng lúc với Kháng chiến?"       → events_overlapping
    """

    def __init__(self, events: List[TemporalEvent]):
        self.events = events

    def events_after(self, event_name: str) -> List[TemporalEvent]:
        """Find events that start after the named event ends."""
        target = self._find_event(event_name)
        if not target:
            return []
        return sorted(
            [e for e in self.events if e.time_range.after(target.time_range)],
            key=lambda e: e.start_year,
        )

    def events_before(self, event_name: str) -> List[TemporalEvent]:
        """Find events that end before the named event starts."""
        target = self._find_event(event_name)
        if not target:
            return []
        return sorted(
            [e for e in self.events if e.time_range.before(target.time_range)],
            key=lambda e: e.start_year,
        )

    def events_during(self, year: int) -> List[TemporalEvent]:
        """Find events that overlap with a specific year."""
        return sorted(
            [e for e in self.events if e.time_range.contains(year)],
            key=lambda e: e.start_year,
        )

    def events_in_range(self, time_range: TimeRange) -> List[TemporalEvent]:
        """Find events that overlap with a time range."""
        return sorted(
            [e for e in self.events if e.time_range.overlaps(time_range)],
            key=lambda e: e.start_year,
        )

    def range_between(
        self, event_a_name: str, event_b_name: str
    ) -> List[TemporalEvent]:
        """
        Find events that occur between two named events.

        Query: "Sau Điện Biên Phủ nhưng trước Tết Mậu Thân?"
        Logic: A.end < X.start AND X.end < B.start
        """
        event_a = self._find_event(event_a_name)
        event_b = self._find_event(event_b_name)

        if not event_a or not event_b:
            return []

        # Ensure a is before b
        if event_a.start_year > event_b.start_year:
            event_a, event_b = event_b, event_a

        return sorted(
            [
                e for e in self.events
                if (
                    e.time_range.after(event_a.time_range)
                    and e.time_range.before(event_b.time_range)
                    and e.name != event_a.name
                    and e.name != event_b.name
                )
            ],
            key=lambda e: e.start_year,
        )

    def events_overlapping(self, event_name: str) -> List[TemporalEvent]:
        """Find events that overlap temporally with the named event."""
        target = self._find_event(event_name)
        if not target:
            return []
        return sorted(
            [
                e for e in self.events
                if e.time_range.overlaps(target.time_range)
                and e.name != target.name
            ],
            key=lambda e: e.start_year,
        )

    def _find_event(self, name: str) -> Optional[TemporalEvent]:
        """Find event by name (fuzzy, case-insensitive)."""
        name_lower = name.lower()
        for e in self.events:
            if name_lower in e.name.lower():
                return e
        return None


# ======================================================================
# TEMPORAL ENGINE — orchestrator
# ======================================================================

class TemporalEngine:
    """
    Deterministic temporal reasoning orchestrator V2.

    Dispatches temporal queries to specialized solvers:
      - duration_max/min → DurationCalculator + Comparator
      - compare → Comparator
      - before_after → TemporalReasoner
      - overlap → TemporalReasoner
      - range_between → TemporalReasoner (NEW)
      - at_year → TemporalReasoner (NEW)

    Also provides:
      - Temporal conflict detection
      - Temporal parsing
      - Majority voting on year disputes
    """

    def __init__(self, data_source: TemporalDataSource):
        self.data = data_source
        self.parser = TemporalParser()
        self.conflict_detector = TemporalConflictDetector()

    def solve(self, query_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route temporal query to appropriate solver.

        Args:
            query_info: Dict with:
                - "intent": TemporalIntent value
                - "entity_type": str (dynasty, person, etc.)
                - Additional keys depend on intent type.

        Returns:
            Result dict with:
                - "result": entity/event data
                - "reasoning": str explaining the logic
                - "conflicts": any detected temporal conflicts
        """
        intent = query_info.get("intent")

        if intent == TemporalIntent.DURATION_MAX:
            return self._solve_duration_max(query_info)

        if intent == TemporalIntent.DURATION_MIN:
            return self._solve_duration_min(query_info)

        if intent == TemporalIntent.COMPARE:
            return self._solve_compare(query_info)

        if intent == TemporalIntent.BEFORE_AFTER:
            return self._solve_before_after(query_info)

        if intent == TemporalIntent.OVERLAP:
            return self._solve_overlap(query_info)

        # V2 new intents
        if intent == "range_between":
            return self._solve_range_between(query_info)

        if intent == "at_year":
            return self._solve_at_year(query_info)

        raise ValueError(f"Unsupported temporal intent: {intent}")

    # ==================================================================
    # V1 SOLVERS (enhanced)
    # ==================================================================

    def _solve_duration_max(self, query_info: Dict[str, Any]) -> Dict[str, Any]:
        """Find entity with longest duration."""
        entity_type = query_info.get("entity_type", "dynasty")
        entities = self.data.get_entities(entity_type)

        DurationCalculator.enrich_entities(entities)
        result = Comparator.max_entity(entities, "duration")

        if result is None:
            return {
                "result": None,
                "reasoning": f"Không tìm thấy {entity_type} nào có dữ liệu thời gian.",
                "conflicts": [],
            }

        return {
            "result": result,
            "reasoning": (
                f"{result['name']} tồn tại {result['duration']} năm "
                f"({result.get('start_year')}–{result.get('end_year')}), "
                f"là {entity_type} lâu nhất."
            ),
            "conflicts": [],
        }

    def _solve_duration_min(self, query_info: Dict[str, Any]) -> Dict[str, Any]:
        """Find entity with shortest duration."""
        entity_type = query_info.get("entity_type", "dynasty")
        entities = self.data.get_entities(entity_type)

        DurationCalculator.enrich_entities(entities)
        entities = [e for e in entities if e.get("duration", 0) > 0]
        result = Comparator.min_entity(entities, "duration")

        if result is None:
            return {
                "result": None,
                "reasoning": f"Không tìm thấy {entity_type} nào có dữ liệu thời gian.",
                "conflicts": [],
            }

        return {
            "result": result,
            "reasoning": (
                f"{result['name']} tồn tại {result['duration']} năm "
                f"({result.get('start_year')}–{result.get('end_year')}), "
                f"là {entity_type} ngắn nhất."
            ),
            "conflicts": [],
        }

    def _solve_compare(self, query_info: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two entities by duration."""
        name_a = query_info.get("entity_a", "")
        name_b = query_info.get("entity_b", "")

        entity_a = self.data.get_entity_by_name(name_a)
        entity_b = self.data.get_entity_by_name(name_b)

        if entity_a is None or entity_b is None:
            missing = name_a if entity_a is None else name_b
            return {
                "result": None,
                "reasoning": f"Không tìm thấy thông tin về '{missing}'.",
                "conflicts": [],
            }

        dur_a = DurationCalculator.calculate_safe(
            entity_a.get("start_year"), entity_a.get("end_year")
        )
        dur_b = DurationCalculator.calculate_safe(
            entity_b.get("start_year"), entity_b.get("end_year")
        )
        entity_a["duration"] = dur_a
        entity_b["duration"] = dur_b

        cmp = Comparator.compare(entity_a, entity_b, "duration")
        if cmp > 0:
            winner, loser = entity_a, entity_b
        elif cmp < 0:
            winner, loser = entity_b, entity_a
        else:
            return {
                "result": [entity_a, entity_b],
                "reasoning": f"{name_a} và {name_b} đều tồn tại {dur_a} năm.",
                "conflicts": [],
            }

        return {
            "result": winner,
            "reasoning": (
                f"{winner['name']} ({winner['duration']} năm) "
                f"lâu hơn {loser['name']} ({loser['duration']} năm)."
            ),
            "conflicts": [],
        }

    def _solve_before_after(self, query_info: Dict[str, Any]) -> Dict[str, Any]:
        """Find entities before or after a reference point using TemporalReasoner."""
        reference_name = query_info.get("reference", "")
        direction = query_info.get("direction", "after")

        events = self.data.get_temporal_events()
        reasoner = TemporalReasoner(events)

        if direction == "before":
            result = reasoner.events_before(reference_name)
            word = "trước"
        else:
            result = reasoner.events_after(reference_name)
            word = "sau"

        result_dicts = [
            {
                "name": e.name,
                "start_year": e.start_year,
                "end_year": e.end_year,
                "description": e.description,
            }
            for e in result
        ]

        return {
            "result": result_dicts,
            "reasoning": (
                f"Có {len(result_dicts)} sự kiện {word} "
                f"'{reference_name}'."
            ),
            "conflicts": [],
        }

    def _solve_overlap(self, query_info: Dict[str, Any]) -> Dict[str, Any]:
        """Find entities overlapping with a reference."""
        reference_name = query_info.get("reference", "")

        events = self.data.get_temporal_events()
        reasoner = TemporalReasoner(events)
        result = reasoner.events_overlapping(reference_name)

        result_dicts = [
            {
                "name": e.name,
                "start_year": e.start_year,
                "end_year": e.end_year,
            }
            for e in result
        ]

        return {
            "result": result_dicts,
            "reasoning": (
                f"Có {len(result_dicts)} sự kiện cùng thời với "
                f"'{reference_name}'."
            ),
            "conflicts": [],
        }

    # ==================================================================
    # V2 NEW SOLVERS
    # ==================================================================

    def _solve_range_between(self, query_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find events between two named events.

        Query: "Sau Điện Biên Phủ nhưng trước Tết Mậu Thân?"
        """
        event_a = query_info.get("event_a", "")
        event_b = query_info.get("event_b", "")

        events = self.data.get_temporal_events()
        reasoner = TemporalReasoner(events)
        result = reasoner.range_between(event_a, event_b)

        result_dicts = [
            {
                "name": e.name,
                "start_year": e.start_year,
                "end_year": e.end_year,
                "description": e.description,
            }
            for e in result
        ]

        return {
            "result": result_dicts,
            "reasoning": (
                f"Có {len(result_dicts)} sự kiện giữa "
                f"'{event_a}' và '{event_b}'."
            ),
            "conflicts": [],
        }

    def _solve_at_year(self, query_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find events at a specific year or time range.

        Query: "Sự kiện năm 1954?" or "Sự kiện giai đoạn 1946-1954?"
        """
        year = query_info.get("year")
        query_text = query_info.get("query", "")

        events = self.data.get_temporal_events()
        reasoner = TemporalReasoner(events)

        # Try parsing time range from query
        parsed_range = self.parser.parse(query_text)

        if parsed_range and parsed_range.start != parsed_range.end:
            result = reasoner.events_in_range(parsed_range)
            time_desc = f"giai đoạn {parsed_range.start}–{parsed_range.end}"
        elif year:
            result = reasoner.events_during(int(year))
            time_desc = f"năm {year}"
        elif parsed_range:
            result = reasoner.events_during(parsed_range.start)
            time_desc = f"năm {parsed_range.start}"
        else:
            return {
                "result": [],
                "reasoning": "Không xác định được thời gian từ truy vấn.",
                "conflicts": [],
            }

        result_dicts = [
            {
                "name": e.name,
                "start_year": e.start_year,
                "end_year": e.end_year,
                "description": e.description,
            }
            for e in result
        ]

        return {
            "result": result_dicts,
            "reasoning": (
                f"Có {len(result_dicts)} sự kiện trong {time_desc}."
            ),
            "conflicts": [],
        }

    # ==================================================================
    # TEMPORAL FILTER (for Hybrid pipeline integration)
    # ==================================================================

    def filter_by_temporal(
        self,
        docs: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Filter retrieved documents by temporal constraints in query.

        Used in the pipeline: Hybrid → Temporal Filter → Reranker

        Args:
            docs: Retrieved documents.
            query: User query (may contain temporal constraints).

        Returns:
            Filtered documents. Returns original if no temporal
            constraints found or filter empties the list.
        """
        parsed = self.parser.parse(query)
        if not parsed:
            return docs

        filtered = []
        for doc in docs:
            year = doc.get("year") or doc.get("metadata", {}).get("year")
            if year is None:
                filtered.append(doc)  # Keep docs without year info
                continue

            try:
                doc_year = int(year)
                if parsed.contains(doc_year):
                    filtered.append(doc)
            except (ValueError, TypeError):
                filtered.append(doc)

        return filtered if filtered else docs
