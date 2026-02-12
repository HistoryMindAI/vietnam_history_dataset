# Tóm tắt: Tích hợp Context7 vào HistoryMindAI

## Vấn đề ban đầu

### Vấn đề 1: Sự kiện không liên quan
Test case có vấn đề:
- **Câu hỏi**: "Hãy kể cho tôi về triều đại nhà Trần và những chiến công chống quân Nguyên Mông"
- **Câu trả lời (có vấn đề)**: 
  - Năm 1225: Nhà Trần thành lập ✓
  - Năm 1255: Cải cách hành chính ✗ (KHÔNG phải chiến công)
  - Năm 1258: Kháng chiến lần 1 ✓
  - Năm 1284: Hịch tướng sĩ ✓
  - Năm 1285: Kháng chiến lần 2 ✓
  - Năm 1288: Trận Bạch Đằng ✓

**Vấn đề**: Câu trả lời chứa năm 1255 (sự kiện hành chính) không liên quan đến "chiến công chống Nguyên Mông"

### Vấn đề 2: Sai nhân vật
Test case có vấn đề:
- **Câu hỏi**: "Ai là Hai Bà Trưng và cuộc khởi nghĩa của họ có ý nghĩa như thế nào?"
- **Câu trả lời (có vấn đề)**:
  - Năm 1400: Hồ Quý Ly lập nhà Hồ ✗ (SAI NGƯỜI - không phải Hai Bà Trưng)

**Vấn đề**: Câu trả lời về Hồ Quý Ly khi hỏi về Hai Bà Trưng - hoàn toàn sai người!

### Vấn đề 3: Sai từ khóa
Test case có vấn đề:
- **Câu hỏi**: "Đại Việt đã được thành lập như thế nào và phát triển qua các thời kỳ ra sao?"
- **Câu trả lời (có vấn đề)**:
  - Năm 1010: Chiếu dời đô ✗ (KHÔNG có "Đại Việt" - chỉ có "Đại La")
  - Năm 1054: Đổi quốc hiệu thành Đại Việt ✓
  - Năm 1075: Lý Thường Kiệt tiến công ✓
  - Năm 1077: Phòng tuyến Như Nguyệt ✓

**Vấn đề**: Câu trả lời chứa năm 1010 (Chiếu dời đô) không có từ "Đại Việt" - quốc hiệu "Đại Việt" chỉ xuất hiện từ năm 1054!

## Giải pháp: Tích hợp Context7

### 1. Files đã tạo

#### a) `ai-service/app/services/context7_service.py`
Service chính xử lý Context7 với các chức năng:

- `extract_query_focus(query)`: Phân tích câu hỏi để xác định trọng tâm
  - Trích xuất triều đại, nhân vật, loại sự kiện
  - Xác định từ khóa bắt buộc
  - Phân loại câu hỏi (kể, liệt kê, so sánh, v.v.)

- `calculate_relevance_score(event, query_focus, query)`: Tính điểm liên quan
  - Kiểm tra triều đại (penalty lớn nếu không khớp)
  - Kiểm tra từ khóa bắt buộc
  - Kiểm tra loại sự kiện (chiến công, kháng chiến, v.v.)
  - Kiểm tra tone (heroic, neutral)
  - Tính điểm dựa trên nhiều yếu tố

- `filter_and_rank_events(events, query, max_results)`: Lọc và xếp hạng
  - Tính điểm cho tất cả sự kiện
  - Lọc bỏ sự kiện có điểm < 10.0
  - Sắp xếp theo điểm giảm dần

- `validate_answer_relevance(answer, query)`: Validate câu trả lời
  - Kiểm tra triều đại có được nhắc đến
  - Kiểm tra kẻ thù có được nhắc đến (khi hỏi "chống X")
  - Kiểm tra nội dung quân sự (khi hỏi về chiến công)

#### b) `tests/test_context7_integration.py`
Test suite đầy đủ với 9 test cases:

1. `test_tran_dynasty_mongol_wars_query`: Test case chính - câu hỏi về nhà Trần và chiến công
2. `test_context7_filters_irrelevant_events`: Test lọc sự kiện không liên quan
3. `test_context7_ranks_by_relevance`: Test xếp hạng theo độ liên quan
4. `test_context7_service_extract_query_focus`: Test phân tích câu hỏi
5. `test_context7_service_calculate_relevance_score`: Test tính điểm
6. `test_context7_service_filter_and_rank`: Test lọc và xếp hạng
7. `test_context7_service_validate_answer`: Test validate câu trả lời
8. `test_hai_ba_trung_wrong_person_filter`: Test lọc sai nhân vật (Hồ Quý Ly vs Hai Bà Trưng)
9. `test_dai_viet_keyword_filter`: Test lọc theo từ khóa quan trọng (Đại Việt)

**Kết quả**: ✅ 9/9 tests PASSED

#### c) `ai-service/scripts/test_context7_demo.py`
Script demo trực quan để xem Context7 hoạt động:

- Demo 1: Phân tích câu hỏi
- Demo 2: Tính điểm liên quan
- Demo 3: Lọc và xếp hạng
- Demo 4: Validate câu trả lời

#### d) `ai-service/app/services/CONTEXT7_README.md`
Tài liệu chi tiết về Context7

### 2. Files đã sửa

#### `ai-service/app/services/engine.py`
Tích hợp Context7 vào engine:

```python
# Import Context7
from app.services.context7_service import (
    filter_and_rank_events,
    validate_answer_relevance,
)

# Áp dụng Context7 filtering sau khi search
if raw_events:
    raw_events = filter_and_rank_events(raw_events, query, max_results=50)

# Validate câu trả lời cuối cùng
if answer and not no_data:
    validation = validate_answer_relevance(answer, query)
```

## Kết quả

### Vấn đề 1: Trước khi có Context7:
```
Câu hỏi: "Chiến công chống Nguyên Mông của nhà Trần"

Kết quả (7 sự kiện):
- Năm 1225: Nhà Trần thành lập (điểm: 1.40) ✗
- Năm 1255: Cải cách hành chính (điểm: 1.40) ✗
- Năm 1258: Kháng chiến lần 1 (điểm: 130.00) ✓
- Năm 1284: Hịch tướng sĩ (điểm: 98.00) ✓
- Năm 1285: Kháng chiến lần 2 (điểm: 130.00) ✓
- Năm 1288: Trận Bạch Đằng (điểm: 46.00) ✓
- Năm 1077: Phòng tuyến Như Nguyệt (điểm: 0.01) ✗
```

### Vấn đề 1: Sau khi có Context7:
```
Câu hỏi: "Chiến công chống Nguyên Mông của nhà Trần"

Kết quả (4 sự kiện - đã lọc):
1. Năm 1258: Kháng chiến lần 1 chống Mông Cổ ✓
2. Năm 1285: Kháng chiến lần 2 chống Nguyên ✓
3. Năm 1284: Hịch tướng sĩ ✓
4. Năm 1288: Trận Bạch Đằng ✓

Đã loại bỏ:
- Năm 1225: Nhà Trần thành lập (không phải chiến công)
- Năm 1255: Cải cách hành chính (không phải chiến công)
- Năm 1077: Phòng tuyến Như Nguyệt (nhà Lý, không phải nhà Trần)
```

### Vấn đề 2: Trước khi có Context7:
```
Câu hỏi: "Ai là Hai Bà Trưng và cuộc khởi nghĩa của họ có ý nghĩa như thế nào?"

Kết quả (có vấn đề):
- Năm 40: Khởi nghĩa Hai Bà Trưng ✓
- Năm 1400: Hồ Quý Ly lập nhà Hồ ✗ (SAI NGƯỜI!)
```

### Vấn đề 2: Sau khi có Context7:
```
Câu hỏi: "Ai là Hai Bà Trưng và cuộc khởi nghĩa của họ có ý nghĩa như thế nào?"

Kết quả (đã lọc):
- Năm 40: Khởi nghĩa Hai Bà Trưng ✓

Đã loại bỏ:
- Năm 1400: Hồ Quý Ly lập nhà Hồ (sai người - không phải Hai Bà Trưng)
```

## Cách chạy tests

```bash
# Chạy tất cả tests Context7
cd vietnam_history_dataset
python -m pytest tests/test_context7_integration.py -v

# Chạy demo script
cd ai-service
python scripts/test_context7_demo.py
```

## Lợi ích

1. ✅ **Độ chính xác cao hơn**: Câu trả lời bám sát câu hỏi
2. ✅ **Lọc nhiễu**: Loại bỏ sự kiện không liên quan
3. ✅ **Xếp hạng thông minh**: Sự kiện quan trọng nhất lên đầu
4. ✅ **Validate tự động**: Phát hiện câu trả lời không phù hợp
5. ✅ **Dễ mở rộng**: Có thể thêm logic lọc mới dễ dàng

## Cấu hình

Các tham số có thể điều chỉnh trong `context7_service.py`:

```python
# Ngưỡng điểm tối thiểu
min_score_threshold = 10.0

# Trọng số
REQUIRED_KEYWORD_WEIGHT = 15.0  # Từ khóa bắt buộc
DYNASTY_WEIGHT = 10.0            # Triều đại
EVENT_TYPE_WEIGHT = 12.0         # Loại sự kiện
TONE_WEIGHT = 5.0                # Tone (heroic/neutral)
WORD_MATCH_WEIGHT = 2.0          # Từ khóa khớp
```

## Tác giả

- **Tích hợp Context7**: Kiro AI Assistant
- **Dự án HistoryMindAI**: Võ Đức Hiếu (h1eudayne)
- **Ngày hoàn thành**: 2026-02-13

## Ghi chú

Context7 là một giải pháp tùy chỉnh được thiết kế riêng cho HistoryMindAI, không phải là một thư viện bên ngoài. Tên "Context7" được chọn để phản ánh việc sử dụng 7 yếu tố chính trong việc tính điểm liên quan:

1. **Nhân vật (Person)** - Kiểm tra nhân vật trong câu hỏi có khớp với sự kiện không
2. **Triều đại (Dynasty)** - Kiểm tra triều đại có khớp không
3. **Từ khóa bắt buộc (Required Keywords)** - Từ khóa quan trọng phải có
4. **Chủ đề chính (Main Topics)** - Loại sự kiện (chiến công, khởi nghĩa, v.v.)
5. **Tone (Heroic/Neutral)** - Tone của sự kiện
6. **Từ khóa khớp (Word Matching)** - Số từ khóa từ câu hỏi xuất hiện trong sự kiện
7. **Độ dài nội dung (Content Length)** - Lọc bỏ sự kiện quá ngắn

## Đặc điểm quan trọng

### 1. Hoàn toàn động (Dynamic)
Context7 KHÔNG hardcode danh sách nhân vật, triều đại hay từ khóa. Tất cả đều được lấy động từ dữ liệu:

```python
# Lấy nhân vật từ PERSON_ALIASES và PERSONS_INDEX
all_person_names = set()
if hasattr(startup, 'PERSON_ALIASES') and startup.PERSON_ALIASES:
    all_person_names.update(startup.PERSON_ALIASES.keys())
    all_person_names.update(startup.PERSON_ALIASES.values())

if hasattr(startup, 'PERSONS_INDEX') and startup.PERSONS_INDEX:
    all_person_names.update(startup.PERSONS_INDEX.keys())

# Sắp xếp theo độ dài để tránh match substring
sorted_persons = sorted(all_person_names, key=len, reverse=True)
```

### 2. Fallback thông minh
Nếu không có dữ liệu từ startup, Context7 sử dụng pattern matching để tìm tên người:
- Pattern: 2-3 từ viết hoa liên tiếp
- Ví dụ: "Trần Hưng Đạo", "Hai Bà Trưng"

### 3. Tự động cập nhật
Khi thêm nhân vật mới vào knowledge base:
- KHÔNG cần sửa code Context7
- Tự động được nhận diện và lọc
- Hoạt động ngay lập tức
Context7 hiện có khả năng lọc chặt chẽ theo nhân vật:
- Nếu câu hỏi về nhân vật X, sự kiện PHẢI liên quan đến X
- Nếu không khớp → điểm = 0.001 (gần như loại bỏ hoàn toàn)
- Xử lý các trường hợp đặc biệt: "Hai Bà Trưng" = "Trưng Trắc" = "Trưng Nhị"

Điều này giải quyết vấn đề câu trả lời sai người (ví dụ: hỏi về Hai Bà Trưng nhưng trả lời về Hồ Quý Ly).
