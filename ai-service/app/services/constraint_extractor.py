"""
constraint_extractor.py — Trích xuất ràng buộc cứng từ câu hỏi (Phase 1 / Giai đoạn 11)

PURPOSE:
    Nhận output từ NLU + Intent Classifier → trả về QueryInfo đầy đủ.
    Gom tất cả constraints (year, entities, answer_type) vào 1 object.

CONTEXT:
    - TRƯỚC ĐÂY: Logic trích xuất rải rác trong engine.py (extract_single_year,
      extract_year_range, resolve_query_entities, classify_intent)
    - BÂY GIỜ: Gom lại thành 1 bước rõ ràng, output là QueryInfo

RELATED OLD FILES:
    - engine.py → extract_single_year(), extract_year_range(), extract_multiple_years()
    - intent_classifier.py → classify_intent() → QueryAnalysis
    - search_service.py → resolve_query_entities() → resolved dict

USAGE IN PIPELINE:
    NLU → Intent Classify → ConstraintExtractor.extract() → QueryInfo
    → Search → Rerank → NLI → Hard Filter (uses QueryInfo) → Answer Build

NOTE:
    Không duplicate logic — reuse hàm có sẵn từ intent_classifier.py và engine.py.
    ConstraintExtractor chỉ "gom" kết quả vào QueryInfo.
"""

import re
from typing import Optional, Tuple, List

from app.core.query_schema import QueryInfo
from app.services.intent_classifier import QueryAnalysis


class ConstraintExtractor:
    """
    Trích xuất ràng buộc cứng (hard constraints) từ câu hỏi.

    Input:  QueryAnalysis (từ intent classifier) + resolved entities + raw query info
    Output: QueryInfo (unified constraint object)

    Mapping logic:
        intent_classifier → QueryAnalysis.intent        → QueryInfo.intent
        intent_classifier → QueryAnalysis.question_type  → QueryInfo.question_type
        intent_classifier → QueryAnalysis.year            → QueryInfo.required_year
        intent_classifier → QueryAnalysis.year_range      → QueryInfo.required_year_range
        intent_classifier → QueryAnalysis.is_fact_check   → QueryInfo.is_fact_check
        resolved_entities → persons/dynasties              → QueryInfo.required_persons
        resolved_entities → topics                         → QueryInfo.required_topics
        inferred from intent + question_type               → QueryInfo.answer_type_required
    """

    # Vietnamese question patterns → answer type mapping
    _WHO_PATTERNS = re.compile(
        r'\b(?:ai\s+(?:đã|là|đánh|lãnh đạo|chỉ huy)|'
        r'ai\b|nhân vật nào|người nào|vị tướng nào|vị vua nào|'
        r'tướng nào|danh tướng nào|anh hùng nào)\b', re.I
    )
    _WHEN_PATTERNS = re.compile(
        r'\b(?:khi nào|năm nào|bao giờ|thời gian nào|'
        r'vào năm nào|diễn ra khi|xảy ra khi|bắt đầu khi|'
        r'sinh năm|mất năm|ra đời năm)\b', re.I
    )
    _WHERE_PATTERNS = re.compile(
        r'\b(?:ở đâu|nơi nào|địa điểm nào|tại đâu|'
        r'ở vùng nào|xảy ra ở|diễn ra ở|chiến trường)\b', re.I
    )
    _DURATION_PATTERNS = re.compile(
        r'\b(?:bao lâu|kéo dài|bao nhiêu năm|thời gian)\b', re.I
    )
    _LIST_PATTERNS = re.compile(
        r'\b(?:liệt kê|kể tên|nêu|những|các|danh sách|bao nhiêu)\b', re.I
    )

    def extract(
        self,
        original_query: str,
        normalized_query: str,
        query_analysis: QueryAnalysis,
        resolved_entities: dict,
    ) -> QueryInfo:
        """
        Trích xuất toàn bộ constraints từ query đã phân tích.

        Args:
            original_query: Câu hỏi gốc từ người dùng
            normalized_query: Câu hỏi sau NLU rewrite
            query_analysis: Output từ classify_intent()
            resolved_entities: Output từ resolve_query_entities()

        Returns:
            QueryInfo chứa toàn bộ ràng buộc
        """
        # --- Build required_persons (hard) + required_topics (soft) ---
        required_persons = self._extract_required_persons(resolved_entities)
        required_topics = self._extract_required_topics(resolved_entities)

        # --- Extract required_topic (legacy single topic) ---
        required_topic = self._extract_required_topic(resolved_entities)

        # --- Detect question type (enhanced) ---
        question_type = self._detect_question_type(
            normalized_query, query_analysis.question_type
        )

        # --- Infer answer_type_required ---
        answer_type = self._infer_answer_type(
            query_analysis.intent, question_type, normalized_query
        )

        # --- Determine required_year ---
        # Only set required_year when query explicitly asks about a specific year
        # Don't set it for fact-check (fact-check uses claimed_year instead)
        required_year = None
        if not query_analysis.is_fact_check:
            if query_analysis.intent in ("year_specific", "year"):
                required_year = query_analysis.year

        # --- Detect relation type (Phase 3 v2.1) ---
        relation_type = self._detect_relation_type(normalized_query)

        return QueryInfo(
            original_query=original_query,
            normalized_query=normalized_query,
            intent=query_analysis.intent,
            question_type=question_type,
            required_year=required_year,
            required_year_range=query_analysis.year_range,
            required_persons=required_persons,
            required_topics=required_topics,
            required_topic=required_topic,
            answer_type_required=answer_type,
            is_fact_check=query_analysis.is_fact_check,
            claimed_year=query_analysis.fact_check_year,
            confidence_threshold=0.55,
            relation_type=relation_type,
        )

    def _extract_required_persons(self, resolved: dict) -> List[str]:
        """
        Lấy danh sách persons/dynasties bắt buộc — HARD constraint.

        Chỉ persons — topics KHÔNG đưa vào (soft constraint).
        Places không đưa vào (quá chung).
        """
        persons = []

        # Persons — most specific, always required if present
        for person in resolved.get("persons", []):
            canonical = person.strip().lower()
            if canonical and canonical not in persons:
                persons.append(canonical)

        return persons

    def _extract_required_topics(self, resolved: dict) -> List[str]:
        """
        Lấy danh sách topics — SOFT constraint (search boost only, không reject).
        """
        topics = []
        for topic in resolved.get("topics", []):
            canonical = topic.strip().lower()
            if canonical and canonical not in topics:
                topics.append(canonical)
        return topics

    def _extract_required_topic(self, resolved: dict) -> Optional[str]:
        """Lấy topic chính từ resolved entities."""
        topics = resolved.get("topics", [])
        if topics:
            return topics[0].strip().lower()
        return None

    def _detect_relation_type(self, query: str) -> Optional[str]:
        """
        Phase 3 v2.1: Detect person-dynasty relation type from query text.

        Priority order (higher wins):
            1. live_during — temporal reference, NOT membership
            2. belong_to  — explicit membership claim
            3. compare    — comparison between entities
            4. None       — no relation detected → Phase 3 skips

        Priority matters:
            "Nguyễn Trãi sống cuối thời nhà Trần"
            Contains BOTH "thời nhà" (belong_to) AND "cuối thời" (live_during).
            live_during wins → Phase 3 DOES NOT fire → no false reject.
        """
        q = query.lower()

        # 1. live_during (must check BEFORE belong_to)
        live_during_patterns = [
            r"cuối\s+thời", r"đầu\s+thời", r"sinh\s+thời",
            r"trong\s+giai\s+đoạn", r"sống\s+vào", r"sống\s+thời",
            r"sinh\s+vào", r"ra\s+đời\s+thời", r"cuối\s+đời",
        ]
        for pattern in live_during_patterns:
            if re.search(pattern, q):
                return "live_during"

        # 2. belong_to (explicit membership)
        belong_to_patterns = [
            r"thuộc", r"phục\s+vụ", r"thời\s+nhà",
            r"dưới\s+triều", r"triều\s+đại",
            r"\btriều\b",  # "triều Lê" → belong_to
            r"\bthời\b",  # generic "thời" as fallback belong_to
        ]
        for pattern in belong_to_patterns:
            if re.search(pattern, q):
                return "belong_to"

        # 3. compare
        compare_patterns = [
            r"so\s+với", r"\bvà\b.*\bthời\b",
        ]
        for pattern in compare_patterns:
            if re.search(pattern, q):
                return "compare"

        return None

    def _detect_question_type(
        self, query: str, existing_type: str
    ) -> str:
        """
        Phát hiện loại câu hỏi với regex tiếng Việt chi tiết hơn.

        Bổ sung cho detect_question_type() cũ trong intent_classifier.py.
        Ưu tiên kết quả mới nếu match rõ ràng, ngược lại dùng existing_type.
        """
        q = query.lower().strip()

        # Check patterns in priority order
        if self._WHO_PATTERNS.search(q):
            return "who"
        if self._WHEN_PATTERNS.search(q):
            return "when"
        if self._WHERE_PATTERNS.search(q):
            return "where"
        if self._DURATION_PATTERNS.search(q):
            return "duration"
        if self._LIST_PATTERNS.search(q):
            return "list"

        # Fallback to existing classification
        return existing_type or "what"

    def _infer_answer_type(
        self, intent: str, question_type: str, query: str
    ) -> Optional[str]:
        """
        Suy ra answer_type bắt buộc từ intent + question_type.

        Mapping:
            who → person
            when → year
            where → location
            list → list
            person_query → person
            year_specific/year_range → event
            dynasty → dynasty
            fact_check → fact_check
        """
        # Question type takes priority
        if question_type == "who":
            return "person"
        if question_type == "when":
            return "year"
        if question_type == "where":
            return "location"
        if question_type == "list":
            return "list"

        # Fallback: infer from intent
        if intent in ("person", "person_query", "definition"):
            return "person"
        if intent in ("year", "year_specific", "year_range", "multi_year"):
            return "event"
        if intent == "dynasty":
            return "dynasty"
        if intent == "fact_check":
            return "fact_check"

        # No strict requirement for general queries
        return None
