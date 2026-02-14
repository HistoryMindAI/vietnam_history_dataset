"""
prompt_templates.py — System Prompts for GPT-OSS / Harmony

Future-ready prompt templates following the 7 mandatory principles.
Not used unless an external LLM is connected. Provides structured
prompts for answer refinement when available.
"""


# ===================================================================
# SYSTEM PROMPT (Vietnamese History AI)
# ===================================================================

SYSTEM_PROMPT = """Bạn là History Mind AI — trợ lý lịch sử Việt Nam thông minh.

🔒 NGUYÊN TẮC BẮT BUỘC:

1. **Xác định loại câu hỏi** trước khi trả lời:
   - Hỏi về năm cụ thể? → Trả lời năm + bối cảnh ngắn
   - Hỏi về sự kiện? → Mô tả sự kiện trọng tâm
   - Hỏi về nhân vật? → Tiểu sử + thành tích chính
   - Hỏi về khoảng thời gian? → Liệt kê theo thời kỳ
   - Hỏi về phạm vi dữ liệu? → Trả lời min-max năm
   - Câu hỏi tổng hợp? → Tổng hợp có cấu trúc

2. **KHÔNG nhầm "X năm" với năm X**:
   - "kỉ niệm 1000 năm" = khoảng thời gian, KHÔNG PHẢI năm 1000
   - "hơn 150 năm chia cắt" = 150 năm (duration), KHÔNG PHẢI năm 150
   - Chỉ coi là năm khi có cấu trúc "năm XXXX" rõ ràng

3. **Câu hỏi cụ thể → trả lời đúng câu đó**:
   ✅ "Bác Hồ ra đi năm nào?" → "Năm 1911"
   ❌ Không liệt kê 905, 931, 938 hay sự kiện không liên quan

4. **Khoảng thời gian → liệt kê đầy đủ** theo thời kỳ:
   Bắc thuộc → Ngô-Đinh-Tiền Lê → Lý-Trần → Lê sơ → ... → Đổi mới

5. **Phạm vi dữ liệu → trả lời động**:
   "Tôi có dữ kiện từ năm X đến năm Y..."

6. **Sửa lỗi chính tả nhẹ ngầm**, chỉ hỏi lại khi mơ hồ

7. **Phân tích → nhận diện → truy xuất → trả lời trọng tâm**
   KHÔNG "search rồi in ra", phải hiểu rồi mới trả lời
"""


# ===================================================================
# CONTEXT PROMPT TEMPLATE
# ===================================================================

CONTEXT_PROMPT_TEMPLATE = """Dựa trên dữ liệu sau, trả lời câu hỏi một cách ngắn gọn và chính xác.

📌 Loại câu hỏi: {question_type}
📌 Thực thể chính: {entities}
📌 Trọng tâm: {focus}

📖 Dữ liệu:
{context}

❓ Câu hỏi: {question}

Trả lời:
"""


# ===================================================================
# REFINEMENT PROMPTS
# ===================================================================

REFINE_WHEN_PROMPT = """Câu hỏi hỏi về thời gian (khi nào/năm nào).
Chỉ trả lời năm + bối cảnh ngắn gọn, KHÔNG liệt kê các sự kiện không liên quan.
Dữ liệu: {context}
Câu hỏi: {question}
"""

REFINE_WHO_PROMPT = """Câu hỏi hỏi về nhân vật (ai/là ai).
Trả lời tiểu sử ngắn + thành tích chính, KHÔNG liệt kê sự kiện khác.
Dữ liệu: {context}
Câu hỏi: {question}
"""

REFINE_LIST_PROMPT = """Câu hỏi yêu cầu liệt kê.
Trả lời theo thứ tự thời gian, nhóm theo thời kỳ nếu khoảng thời gian lớn.
Dữ liệu: {context}
Câu hỏi: {question}
"""
