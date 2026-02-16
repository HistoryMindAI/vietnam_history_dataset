"""
query_schema.py — Unified Query & Answer Data Schemas (Phase 1 / Giai đoạn 11)

PURPOSE:
    Chuẩn hóa toàn bộ ràng buộc (constraints) từ câu hỏi vào 1 object duy nhất,
    và chuẩn hóa câu trả lời thành JSON trước khi format text.

CONTEXT:
    - TRƯỚC ĐÂY: Logic rải rác trong engine.py, intent_classifier.py, answer_synthesis.py
    - BÂY GIỜ: Tập trung vào 2 dataclass: QueryInfo (input) + StructuredAnswer (output)

RELATED OLD FILES:
    - intent_classifier.py → QueryAnalysis dataclass (vẫn giữ, QueryInfo bọc thêm constraints)
    - answer_synthesis.py → synthesize_answer() (vẫn giữ làm fallback)
    - engine.py → engine_answer() (sẽ tích hợp QueryInfo + StructuredAnswer)

USAGE:
    1. ConstraintExtractor tạo QueryInfo từ QueryAnalysis + resolved entities
    2. AnswerValidator dùng QueryInfo để lọc candidates
    3. AnswerBuilder tạo StructuredAnswer từ validated events
    4. AnswerFormatter convert StructuredAnswer → Vietnamese text
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class QueryInfo:
    """
    Gom toàn bộ ràng buộc trích xuất từ câu hỏi người dùng.

    Được tạo bởi ConstraintExtractor sau bước NLU + Intent Classification.
    Dùng bởi AnswerValidator (hard filter) + AnswerBuilder (build structured answer).

    Fields:
        original_query:       Câu hỏi gốc từ user
        normalized_query:     Câu hỏi sau NLU rewrite
        intent:               Intent phân loại (person_query, year_specific, ...)
        question_type:        Loại câu hỏi (who, when, where, what, list)
        required_year:        Năm BẮT BUỘC phải có trong answer (nếu user hỏi cụ thể)
        required_year_range:  Khoảng năm bắt buộc (start, end)
        required_persons:     Persons/dynasties bắt buộc — HARD constraint (reject nếu thiếu)
        required_topics:      Topics — SOFT constraint (search boost, không reject)
        required_topic:       Topic chính (vd: "Nguyên Mông", "Bạch Đằng")
        answer_type_required: Loại answer bắt buộc (person / event / dynasty / year)
        is_fact_check:        True nếu user hỏi xác nhận sự thật
        claimed_year:         Năm user khẳng định (có thể sai)
        confidence_threshold: Ngưỡng tin cậy tối thiểu để trả lời
    """
    # Raw input
    original_query: str
    normalized_query: str

    # Intent (from intent_classifier.py → QueryAnalysis)
    intent: str                              # person_query, year_specific, event_query, etc.
    question_type: Optional[str] = None      # who, when, where, what, list

    # Hard constraints — events MUST match these to be returned
    required_year: Optional[int] = None
    required_year_range: Optional[tuple] = None   # (start, end)
    required_persons: List[str] = field(default_factory=list)   # Persons + dynasties (HARD)
    required_topics: List[str] = field(default_factory=list)    # Topics (SOFT — search boost only)
    required_topic: Optional[str] = None

    # Structural requirement — answer type MUST match
    answer_type_required: Optional[str] = None  # "person" | "event" | "dynasty" | "year" | "location"

    # Fact-check (from intent_classifier.py)
    is_fact_check: bool = False
    claimed_year: Optional[int] = None

    # Conflict detection (Phase 1 — Conflict Detector)
    has_conflict: bool = False
    conflict_reasons: List[str] = field(default_factory=list)

    # Phase 3 v2.1: Relation type (extracted by ConstraintExtractor)
    # "belong_to" | "live_during" | "compare" | None
    relation_type: Optional[str] = None

    # Phase 4: Soft Semantic Layer (non-blocking)
    semantic_notes: List[str] = field(default_factory=list)
    semantic_warnings: List[str] = field(default_factory=list)
    semantic_expansions: Dict[str, List[str]] = field(default_factory=dict)

    # Scoring
    confidence_threshold: float = 0.55

    @property
    def required_entities(self) -> List[str]:
        """Backward compat — returns required_persons (hard entities only)."""
        return self.required_persons


@dataclass
class StructuredAnswer:
    """
    Câu trả lời dạng JSON chuẩn — chỉ chứa DATA, không chứa text format.

    Được tạo bởi AnswerBuilder, sau đó chuyển cho AnswerFormatter → text.

    Flow: Events → AnswerBuilder → StructuredAnswer → AnswerFormatter → text

    Fields:
        answer_type:       Loại answer (event, person, dynasty, year, list, fact_check)
        title:             Tên sự kiện/nhân vật chính
        year:              Năm chính
        year_range:        Khoảng năm (nếu có)
        people:            Danh sách nhân vật liên quan
        location:          Địa điểm
        dynasty:           Triều đại
        description:       Mô tả chi tiết (raw text từ data)
        items:             Danh sách events (cho list answer)
        confidence:        Điểm tin cậy cuối cùng
        fact_check_result:  Kết quả fact-check ("confirmed" | "corrected" | None)
        fact_check_detail:  Chi tiết fact-check (năm đúng vs năm user nêu)
    """
    answer_type: str       # "event" | "person" | "dynasty" | "year" | "list" | "fact_check"

    # Core data
    title: Optional[str] = None
    year: Optional[int] = None
    year_range: Optional[tuple] = None
    people: List[str] = field(default_factory=list)
    location: Optional[str] = None
    dynasty: Optional[str] = None
    description: str = ""

    # List answers (multiple events)
    items: List[dict] = field(default_factory=list)

    # Scoring
    confidence: float = 0.0

    # Fact-check specific
    fact_check_result: Optional[str] = None   # "confirmed" | "corrected"
    fact_check_detail: Optional[str] = None   # "Năm đúng: 1911, user nêu: 1991"
