# Context7 Integration - Cải thiện độ chính xác câu trả lời

## Tổng quan

Context7 là một service được tích hợp vào HistoryMindAI để đảm bảo câu trả lời luôn bám sát câu hỏi của người dùng. Service này giải quyết vấn đề câu trả lời lệch chủ đề hoặc chứa thông tin không liên quan.

## Vấn đề được giải quyết

### Trước khi có Context7:
Câu hỏi: "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"

Câu trả lời (có vấn đề):
- Năm 1225: Nhà Trần thành lập... ✓ (OK - liên quan)
- Năm 1255: Cải cách hành chính... ✗ (KHÔNG liên quan - không phải chiến công)
- Năm 1258: Kháng chiến lần 1 chống Mông Cổ... ✓ (OK)
- Năm 1077: Lý Thường Kiệt... ✗ (KHÔNG liên quan - nhà Lý, không phải nhà Trần)

### Sau khi có Context7:
Câu trả lời (chính xác):
- Năm 1258: Kháng chiến lần 1 chống Mông Cổ ✓
- Năm 1284: Hịch tướng sĩ ✓
- Năm 1285: Kháng chiến lần 2 chống Nguyên ✓
- Năm 1288: Trận Bạch Đằng ✓

## Cách hoạt động

Context7 hoạt động qua 3 bước chính:

### 1. Phân tích câu hỏi (Query Focus Extraction)

```python
from app.services.context7_service import extract_query_focus

query = "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"
focus = extract_query_focus(query)

# Kết quả:
{
    "main_topics": [
        "dynasty:trần",
        "event:military_achievement",
        "event:against"
    ],
    "required_keywords": ["trần", "nguyên mông"],
    "excluded_keywords": [],
    "question_type": "narrative"
}
```

### 2. Tính điểm liên quan (Relevance Scoring)

Mỗi sự kiện được chấm điểm dựa trên:

- **Từ khóa bắt buộc** (trọng số cao nhất): +15 điểm/từ khóa
  - Nếu thiếu từ khóa bắt buộc → điểm = 0.1 (gần như loại bỏ)

- **Triều đại**: +10 điểm nếu khớp
  - Nếu câu hỏi chỉ định triều đại nhưng sự kiện không khớp → điểm = 0.01

- **Loại sự kiện**: +12 điểm nếu khớp
  - Hỏi về chiến công nhưng không có từ khóa quân sự → -10 điểm

- **Tone phù hợp**: +5 điểm
  - Hỏi về chiến công nhưng tone không phải "heroic" → điểm × 0.2

- **Từ khóa trong câu hỏi**: +2 điểm/từ

### 3. Lọc và xếp hạng (Filtering & Ranking)

```python
from app.services.context7_service import filter_and_rank_events

events = [...]  # Danh sách sự kiện từ search
filtered = filter_and_rank_events(events, query, max_results=10)

# Chỉ giữ lại các sự kiện có điểm >= 10.0
# Sắp xếp theo điểm giảm dần
```

## Tích hợp vào Engine

Context7 được tích hợp vào `engine.py` tại 2 điểm:

### 1. Sau khi search, trước khi deduplicate:

```python
# engine.py
if raw_events:
    raw_events = filter_and_rank_events(raw_events, query, max_results=50)
```

### 2. Sau khi tạo answer, validate kết quả:

```python
# engine.py
if answer and not no_data:
    validation = validate_answer_relevance(answer, query)
    if not validation["is_relevant"]:
        # Log issues for debugging
        pass
```

## Ví dụ sử dụng

### Ví dụ 1: Lọc theo triều đại

```python
query = "Chiến công của nhà Trần"

# Sự kiện nhà Lý sẽ bị loại bỏ (điểm = 0.01)
# Chỉ giữ lại sự kiện nhà Trần
```

### Ví dụ 2: Lọc theo loại sự kiện

```python
query = "Chiến công chống Nguyên Mông"

# Sự kiện "Cải cách hành chính" sẽ bị loại bỏ (không có từ khóa quân sự)
# Chỉ giữ lại các trận chiến
```

### Ví dụ 3: Xếp hạng theo độ liên quan

```python
query = "Chiến thắng chống Nguyên Mông"

# Sự kiện "Trận Bạch Đằng" (có "chiến thắng") → điểm cao
# Sự kiện "Nhà Trần thành lập" (không có "chiến thắng") → điểm thấp
```

## Testing

Chạy tests để kiểm tra Context7:

```bash
cd vietnam_history_dataset
python -m pytest tests/test_context7_integration.py -v
```

Tests bao gồm:
- ✓ Lọc sự kiện không liên quan (năm 1255, nhà Lý)
- ✓ Xếp hạng theo độ liên quan
- ✓ Validate câu trả lời
- ✓ Extract query focus
- ✓ Calculate relevance score
- ✓ Filter and rank events

## Cấu hình

Các tham số có thể điều chỉnh trong `context7_service.py`:

```python
# Ngưỡng điểm tối thiểu để giữ lại sự kiện
min_score_threshold = 10.0

# Trọng số cho các yếu tố
REQUIRED_KEYWORD_WEIGHT = 15.0
DYNASTY_WEIGHT = 10.0
EVENT_TYPE_WEIGHT = 12.0
TONE_WEIGHT = 5.0
WORD_MATCH_WEIGHT = 2.0
```

## Kết quả

Sau khi tích hợp Context7:
- ✅ Câu trả lời bám sát câu hỏi
- ✅ Loại bỏ sự kiện không liên quan
- ✅ Xếp hạng sự kiện theo độ quan trọng
- ✅ Giảm nhiễu thông tin
- ✅ Cải thiện trải nghiệm người dùng

## Tác giả

Tích hợp Context7 bởi Kiro AI Assistant
Dự án: HistoryMindAI by Võ Đức Hiếu (h1eudayne)
