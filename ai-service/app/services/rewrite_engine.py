"""
rewrite_engine.py — LLM Rewrite Layer PLACEHOLDER (Phase 1 / Giai đoạn 11)

PURPOSE:
    Placeholder cho LLM rewrite layer — DISABLED by default.
    Khi enable, LLM sẽ viết lại câu trả lời tự nhiên hơn.
    LLM KHÔNG suy luận, KHÔNG thêm thông tin — chỉ viết lại ngữ pháp.

CONTEXT:
    - HIỆN TẠI: Disabled — trả text nguyên bản từ AnswerFormatter
    - TƯƠNG LAI: Enable = True → gửi text cho Claude/GPT → nhận text cải thiện
    - Chi phí dự kiến khi enable: ~5-30 USD/tháng tùy lượng user

RELATED OLD FILES:
    - Không có file cũ tương đương — module hoàn toàn mới

PIPELINE POSITION:
    Answer Format → **(Rewrite Layer — disabled)** → Final Answer

CONFIG:
    USE_LLM_REWRITE = False (trong config.py)
    Bật: USE_LLM_REWRITE = True
"""

from app.core.query_schema import StructuredAnswer


class RewriteEngine:
    """
    LLM Rewrite Layer — cải thiện ngữ pháp câu trả lời.

    Khi disabled: trả text nguyên bản (no-op).
    Khi enabled: gửi text cho LLM API (future implementation).

    Usage:
        rewriter = RewriteEngine(enabled=False)
        final_text = rewriter.rewrite(structured_answer, formatted_text)
    """

    def __init__(self, enabled: bool = False):
        """
        Args:
            enabled: True để bật LLM rewrite, False để bypass
        """
        self.enabled = enabled

    def rewrite(self, structured: StructuredAnswer, text: str) -> str:
        """
        Rewrite text nếu enabled — ngược lại trả nguyên bản.

        Args:
            structured: StructuredAnswer (JSON data — dùng làm context cho LLM)
            text: Formatted text từ AnswerFormatter

        Returns:
            Rewritten text (hoặc nguyên bản nếu disabled)
        """
        if not self.enabled:
            return text

        # ======================================================
        # FUTURE: LLM API call
        # ======================================================
        # Khi enable, implementation sẽ:
        # 1. Build prompt từ structured + text
        # 2. Gọi LLM API (Claude/GPT)
        # 3. Parse response
        # 4. Validate: output không thêm thông tin mới
        # 5. Return rewritten text
        #
        # Prompt template:
        # "Viết lại câu trả lời sau cho tự nhiên hơn.
        #  KHÔNG thêm thông tin mới. KHÔNG suy luận.
        #  Chỉ cải thiện ngữ pháp và cách diễn đạt.
        #  Input: {text}
        #  Data context: {structured}"
        #
        # Cost estimate: ~0.001 USD/query → 5-30 USD/month
        # ======================================================

        return text
