# Vietnam History AI - Hệ thống Chatbot Lịch sử Việt Nam

Dự án này là một hệ thống Chatbot thông minh hỗ trợ tra cứu và trả lời các câu hỏi về lịch sử Việt Nam, sử dụng kỹ thuật RAG (Retrieval-Augmented Generation) để cung cấp thông tin chính xác và có chiều sâu.

## 🏗 Kiến trúc hệ thống

Hệ thống được thiết kế theo mô hình 3 lớp:

```mermaid
graph TD
    subgraph "🖥 Frontend - React"
        A["Giao diện Chat"]
    end

    subgraph "⚙️ Backend - Spring Boot"
        B["API Gateway / Orchestrator"]
        B1["Quản lý User"]
        B2["Quản lý Session"]
    end

    subgraph "🤖 AI Service - FastAPI"
        C["Query Engine"]
        C1["Semantic Search - FAISS"]
        C2["Entity Resolution"]
        C3["Intent Detection"]
    end

    subgraph "💾 Data Layer"
        D1["FAISS Index - 630 vectors"]
        D2["meta.json - Metadata"]
        D3["knowledge_base.json - Aliases"]
        D4["history_timeline.json"]
    end

    A -- "HTTP Request" --> B
    B -- "REST API" --> C
    C --> C1 & C2 & C3
    C1 --> D1
    C2 --> D3
    C3 --> D2
    D4 -. "pipeline build" .-> D1
    D4 -. "pipeline build" .-> D2
```

1. **Frontend (React)**: Giao diện người dùng cho phép tương tác và trò chuyện với Chatbot.
2. **Backend (Spring Boot)**: Đóng vai trò là lớp điều phối (Orchestrator), xử lý nghiệp vụ chính và quản lý người dùng.
3. **AI Service (FastAPI)**: Cung cấp API xử lý ngôn ngữ tự nhiên, thực hiện tìm kiếm ngữ nghĩa và truy xuất dữ liệu lịch sử.

---

## 🚀 Pipeline xử lý dữ liệu (AI Pipeline)

Quá trình xây dựng cơ sở tri thức cho AI bao gồm các bước:

```mermaid
graph LR
    subgraph "📥 Input"
        A["Vietnam-History-1M-Vi<br/>(HuggingFace Dataset)"]
    end

    subgraph "🔧 Bước 1: Chuẩn hóa"
        B["storyteller.py"]
        B1["Làm sạch văn bản"]
        B2["Trích xuất thời gian"]
        B3["Nhận diện thực thể"]
        B4["Phân loại sự kiện"]
    end

    subgraph "📊 Bước 2: Đánh chỉ mục"
        C["index_docs.py"]
        C1["Tạo Embedding vectors"]
        C2["Build FAISS Index"]
        C3["Export Metadata"]
    end

    subgraph "📦 Output"
        D1["history_timeline.json"]
        D2["faiss_index/index.bin"]
        D3["faiss_index/meta.json"]
    end

    A --> B
    B --> B1 & B2 & B3 & B4
    B1 & B2 & B3 & B4 --> D1
    D1 --> C
    C --> C1 & C2 & C3
    C1 --> D2
    C2 --> D2
    C3 --> D3
```

### 1. Chuẩn hóa và Trích xuất thực thể (`pipeline/storyteller.py`)

- **Dữ liệu đầu vào**: Sử dụng tập dữ liệu [Vietnam-History-1M-Vi](https://huggingface.co/datasets/minhxthanh/Vietnam-History-1M-Vi) (dạng Arrow).
- **Xử lý**:
  - Làm sạch văn bản, loại bỏ các nội dung nhiễu.
  - Trích xuất chính xác thời gian (năm diễn ra sự kiện).
  - Nhận diện các thực thể lịch sử: Nhân vật (Vua, Tướng lĩnh), Địa danh (Chiến trường, Kinh đô), Tập thể (Triều đại, Quân đội).
  - Phân loại tính chất sự kiện (Quân sự, Thể chế, Văn hóa, Kinh tế) và sắc thái (Hào hùng, Bi thương, Trung tính).
- **Kết quả**: Tạo ra file `data/history_timeline.json` chứa dòng thời gian lịch sử đã được cấu trúc hóa.

### 2. Đánh chỉ mục Vector (`pipeline/index_docs.py`)

- **Mô hình Embedding**: Sử dụng `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Đây là mô hình đa ngôn ngữ mạnh mẽ, hỗ trợ tốt tiếng Việt.
- **Quy trình**:
  - Chuyển đổi các sự kiện lịch sử thành các câu chuyện (stories) có ngữ cảnh.
  - Tạo vector embedding cho từng câu chuyện.
  - Lưu trữ vào **FAISS** (Facebook AI Similarity Search) để thực hiện tìm kiếm vector tốc độ cao.

---

## 🤖 AI Service — Data-Driven Architecture

Dịch vụ API sử dụng kiến trúc **Data-Driven** — không hardcode patterns, tự động scale theo dữ liệu.

### Tổng quan Query Engine

```mermaid
graph TD
    subgraph "🚀 Startup - Khởi tạo một lần"
        S1["meta.json<br/>(630 documents)"]
        S2["knowledge_base.json<br/>(Aliases & Synonyms)"]
        S1 -- "auto-build" --> IDX["Inverted Indexes"]
        S2 -- "load" --> KB["Knowledge Base"]
    end

    subgraph "📇 Inverted Indexes"
        IDX --> I1["PERSONS_INDEX<br/>tên → doc_ids"]
        IDX --> I2["DYNASTY_INDEX<br/>triều đại → doc_ids"]
        IDX --> I3["KEYWORD_INDEX<br/>keyword → doc_ids"]
        IDX --> I4["PLACES_INDEX<br/>địa danh → doc_ids"]
    end

    subgraph "📖 Knowledge Base"
        KB --> K1["PERSON_ALIASES<br/>Trần Quốc Tuấn → Trần Hưng Đạo"]
        KB --> K2["TOPIC_SYNONYMS<br/>Mông Cổ → Nguyên Mông"]
        KB --> K3["DYNASTY_ALIASES<br/>Nhà Trần → Trần"]
    end

    Q["User Query"] --> R["resolve_query_entities()"]
    R -- "tra cứu" --> K1 & K2 & K3
    R -- "tra cứu" --> I1 & I2 & I3 & I4
    R --> RE["Resolved Entities<br/>{persons, dynasties, topics, places}"]
    RE --> SCAN["scan_by_entities()<br/>O(1) Lookup"]
    SCAN --> RESULT["Matched Documents"]
```

### Chi tiết: Luồng xử lý câu hỏi

```mermaid
flowchart TD
    INPUT["📝 Câu hỏi người dùng"] --> CREATOR{"Hỏi về tác giả?"}
    CREATOR -- Có --> CR["🤖 Creator Response"]
    CREATOR -- Không --> IDENTITY{"Hỏi 'bạn là ai'?"}
    IDENTITY -- Có --> ID["🤖 Identity Response"]
    IDENTITY -- Không --> YEAR_RANGE{"Khoảng năm?<br/>VD: từ 1225-1400"}
    YEAR_RANGE -- Có --> YR["📅 scan_by_year_range()"]
    YEAR_RANGE -- Không --> MULTI_YEAR{"Nhiều năm?<br/>VD: 938 và 1288"}
    MULTI_YEAR -- Có --> MY["📅 scan_by_year() x N"]
    MULTI_YEAR -- Không --> ENTITY{"Có entity?<br/>Person/Dynasty/Topic/Place"}
    ENTITY -- Có --> ME["🔍 scan_by_entities()"]
    ENTITY -- Không --> DEFINITION{"Chứa 'là gì/là ai'?"}
    DEFINITION -- Có --> DEF["📖 semantic_search()"]
    DEFINITION -- Không --> SINGLE_YEAR{"Có năm đơn?"}
    SINGLE_YEAR -- Có --> SY["📅 scan_by_year()"]
    SINGLE_YEAR -- Không --> SEM["🧠 semantic_search()"]

    YR & MY & ME & DEF & SY & SEM --> DEDUP["Deduplicate & Enrich"]
    DEDUP --> FORMAT["Format Answer"]
    FORMAT --> OUTPUT["📤 JSON Response"]

    style ME fill:#2d6a4f,color:#fff
    style ENTITY fill:#2d6a4f,color:#fff
```

### Chi tiết: Entity Resolution (Data-Driven)

Khi user hỏi _"Trần Quốc Tuấn và nhà Trần đánh quân Mông Cổ ở Bạch Đằng"_, hệ thống xử lý:

```mermaid
graph LR
    Q["Query: Trần Quốc Tuấn và nhà Trần<br/>đánh quân Mông Cổ ở Bạch Đằng"]

    subgraph "1️⃣ Person Aliases"
        Q --> PA["PERSON_ALIASES lookup"]
        PA --> P1["Trần Quốc Tuấn → Trần Hưng Đạo ✅"]
    end

    subgraph "2️⃣ Dynasty Aliases"
        Q --> DA["DYNASTY_ALIASES lookup"]
        DA --> D1["nhà Trần → Trần ✅"]
    end

    subgraph "3️⃣ Topic Synonyms"
        Q --> TS["TOPIC_SYNONYMS lookup"]
        TS --> T1["Mông Cổ → Nguyên Mông ✅"]
    end

    subgraph "4️⃣ Places Index"
        Q --> PI["PLACES_INDEX lookup"]
        PI --> PL1["Bạch Đằng ✅"]
    end

    P1 & D1 & T1 & PL1 --> RESOLVED["Resolved:<br/>persons: Trần Hưng Đạo<br/>dynasties: Trần<br/>topics: Nguyên Mông<br/>places: Bạch Đằng"]

    RESOLVED --> SCAN["scan_by_entities()"]
    SCAN --> |"O(1) per entity"| DOCS["Matched Documents"]
```

### Mở rộng hệ thống

> **Muốn thêm nhân vật/alias mới?** Chỉ cần sửa file `knowledge_base.json` — KHÔNG cần sửa code Python.
>
> **Thêm 1000 documents mới?** Inverted indexes tự build tại startup — KHÔNG cần cấu hình gì thêm.

```mermaid
graph LR
    subgraph "🔧 Chỉ cần sửa 1 file"
        KB["knowledge_base.json"]
    end

    subgraph "✅ Tự động scale"
        KB --> |"restart server"| LOAD["_load_knowledge_base()"]
        LOAD --> A1["PERSON_ALIASES mới"]
        LOAD --> A2["TOPIC_SYNONYMS mới"]
        LOAD --> A3["DYNASTY_ALIASES mới"]
    end
```

| Thao tác | File cần sửa | Code cần sửa |
|---|---|---|
| Thêm alias nhân vật | `knowledge_base.json` | ❌ Không |
| Thêm synonym chủ đề | `knowledge_base.json` | ❌ Không |
| Thêm alias triều đại | `knowledge_base.json` | ❌ Không |
| Thêm documents mới | `meta.json` (rebuild index) | ❌ Không |

---

## 🧪 Testing

Hệ thống có **282 unit tests** bao phủ toàn diện:

```bash
python -m pytest tests/ -v
```

| File | Nội dung |
|---|---|
| `test_engine.py` | Engine chính: intent routing, entity resolution, year queries, multi-entity, edge cases |
| `test_engine_dedup.py` | Deduplication, text cleaning, keyword extraction |
| `test_search_utils.py` | Search utilities: keyword extraction, relevance filtering, inverted indexes, knowledge base |

---

## 🛠 Hướng dẫn cài đặt và khởi chạy

### Yêu cầu hệ thống

- Python 3.11+
- Các thư viện: `fastapi`, `uvicorn`, `faiss-cpu` (hoặc `faiss-gpu`), `sentence-transformers`, `pydantic`.

### 🚀 Hướng dẫn chạy API (Quan trọng)

Để khởi chạy dịch vụ API cho chatbot, bạn cần thực hiện các bước sau:

1. Di chuyển vào thư mục `ai-service`:
   ```bash
   cd ai-service
   ```
2. Chạy lệnh khởi động server (FastAPI):
   ```bash
   uvicorn app.main:app --reload
   ```
   _(Lưu ý: Đảm bảo bạn đã cài đặt đầy đủ các thư viện Python cần thiết)_

API sẽ mặc định chạy tại: `http://localhost:8000`

### Chạy Pipeline dữ liệu (Khi cần cập nhật dữ liệu)

1.  Chuẩn hóa dữ liệu:
    ```bash
    python pipeline/storyteller.py
    ```
2.  Tạo chỉ mục vector:
    ```bash
    python pipeline/index_docs.py
    ```

---

## 📂 Cấu trúc thư mục

```
vietnam_history_dataset/
├── ai-service/                   # 🤖 FastAPI AI Service
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py         # Cấu hình paths & constants
│   │   │   └── startup.py        # Build indexes + load knowledge base
│   │   ├── services/
│   │   │   ├── engine.py         # Query Engine — intent routing
│   │   │   └── search_service.py # Entity resolution + FAISS search
│   │   └── main.py               # FastAPI entry point
│   ├── faiss_index/
│   │   ├── index.bin             # FAISS vector index (630 docs)
│   │   └── meta.json             # Document metadata
│   └── knowledge_base.json       # 🔑 Aliases & Synonyms (edit here!)
├── data/
│   └── history_timeline.json     # Structured historical data
├── pipeline/
│   ├── storyteller.py            # Data extraction pipeline
│   └── index_docs.py             # Vector indexing pipeline
└── tests/
    ├── test_engine.py            # Engine core tests
    ├── test_engine_dedup.py      # Dedup & text cleaning tests
    └── test_search_utils.py      # Search & indexing tests
```

## 📚 Công nghệ sử dụng

- **Ngôn ngữ**: Python
- **Framework**: FastAPI
- **Vector Database**: FAISS
- **AI Model**: Sentence-Transformers (MiniLM-L12)
- **Data Processing**: HuggingFace Datasets, Regex, Multiprocessing.

---

_Dự án được phát triển nhằm gìn giữ và truyền bá kiến thức lịch sử Việt Nam thông qua công nghệ AI hiện đại._
