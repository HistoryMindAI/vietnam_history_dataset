# Hướng Dẫn Triển Khai AI Service (Docker)

Tài liệu này hướng dẫn chi tiết các bước để cài đặt, xây dựng và chạy **AI Service** của hệ thống Vietnam History AI sử dụng Docker. Service này cung cấp API để tìm kiếm và trả lời câu hỏi lịch sử dựa trên dữ liệu đã được index.

## Yêu cầu tiên quyết

Trước khi bắt đầu, đảm bảo máy tính của bạn đã cài đặt:

*   **Docker Desktop** (hoặc Docker Engine trên Linux).
*   **Python 3.10+** (để chạy script tạo dữ liệu index).
*   **Git** (để clone repository).

---

## Các bước thực hiện

### 1. Chuẩn bị môi trường & Dữ liệu Index

Service AI hoạt động dựa trên cơ chế tìm kiếm vector (RAG), do đó cần có dữ liệu index (FAISS index) trước khi build Docker image.

Từ thư mục gốc của dự án (root folder), thực hiện các lệnh sau:

**a. Cài đặt thư viện Python cần thiết:**

```bash
# Tạo môi trường ảo (khuyến nghị)
python -m venv venv
source venv/bin/activate  # Trên Linux/macOS
# hoặc: venv\Scripts\activate  # Trên Windows

# Cài đặt các thư viện
pip install -r ai-service/requirements.txt
```

**b. Chạy script tạo Index:**

Script này sẽ đọc dữ liệu từ `data/history_cleaned.jsonl`, xử lý và tạo ra thư mục `ai-service/faiss_index` chứa các file vector.

```bash
# Đảm bảo bạn đang ở thư mục gốc của dự án
export PYTHONPATH=.
python pipeline/index_docs.py
```

*Lưu ý: Trên Windows (PowerShell), thay `export PYTHONPATH=.` bằng `$env:PYTHONPATH="."`*

Sau khi chạy xong, kiểm tra xem thư mục `ai-service/faiss_index/` đã được tạo chưa và có chứa `history.index` và `meta.json` không.

---

### 2. Build Docker Image

Di chuyển vào thư mục `ai-service` và tiến hành build Docker image.

```bash
cd ai-service
docker build -t vietnam-history-ai .
```

**Giải thích lệnh:**
*   `docker build`: Lệnh để xây dựng một image mới.
*   `-t vietnam-history-ai`: Gán nhãn (tag) tên cho image là `vietnam-history-ai` để dễ quản lý.
*   `.`: Dấu chấm đại diện cho "build context" là thư mục hiện tại. Docker sẽ tìm file `Dockerfile` ở đây và copy các file cần thiết (bao gồm cả thư mục `faiss_index` vừa tạo ở bước 1) vào trong image.

---

### 3. Chạy Docker Container

Sau khi build thành công, chạy service bằng lệnh sau:

```bash
docker run -d -p 8000:8000 --name ai-service-container vietnam-history-ai
```

**Giải thích lệnh:**
*   `docker run`: Lệnh khởi tạo và chạy một container từ image.
*   `-d` (detach): Chạy container ở chế độ nền (background), không chiếm dụng cửa sổ terminal hiện tại.
*   `-p 8000:8000`: Ánh xạ cổng (port mapping). Cổng 8000 của máy chủ (host) sẽ được nối với cổng 8000 của container. Bạn sẽ truy cập service qua cổng này.
*   `--name ai-service-container`: Đặt tên dễ nhớ cho container là `ai-service-container`.
*   `vietnam-history-ai`: Tên của image cần chạy (đã đặt ở bước build).

---

### 4. Kiểm tra hoạt động

Sau khi container chạy, bạn có thể kiểm tra service bằng các cách sau:

**Cách 1: Truy cập Swagger UI**
Mở trình duyệt và truy cập: [http://localhost:8000/docs](http://localhost:8000/docs)
Tại đây bạn sẽ thấy giao diện Swagger UI để test các API trực tiếp.

**Cách 2: Sử dụng cURL**

```bash
curl -X 'POST' \
  'http://localhost:8000/api/chat' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "message": "Chiến thắng Bạch Đằng năm 938 diễn ra như thế nào?",
  "history": []
}'
```

---

## Quản lý Container

Một số lệnh hữu ích để quản lý service:

*   **Xem danh sách container đang chạy:**
    ```bash
    docker ps
    ```

*   **Xem log của service (để debug):**
    ```bash
    docker logs -f ai-service-container
    ```

*   **Dừng service:**
    ```bash
    docker stop ai-service-container
    ```

*   **Xóa container (sau khi đã dừng):**
    ```bash
    docker rm ai-service-container
    ```

*   **Xóa image (nếu cần build lại từ đầu):**
    ```bash
    docker rmi vietnam-history-ai
    ```

## Xử lý lỗi thường gặp

1.  **Lỗi "Port already in use":**
    *   Nguyên nhân: Cổng 8000 đang bị chiếm dụng bởi một ứng dụng khác.
    *   Khắc phục: Đổi cổng mapping, ví dụ `-p 8080:8000` (truy cập qua localhost:8080).

2.  **Lỗi "faiss_index/history.index not found":**
    *   Nguyên nhân: Bạn chưa chạy script tạo index (Bước 1) hoặc chạy sai thư mục.
    *   Khắc phục: Kiểm tra lại thư mục `ai-service/faiss_index` có tồn tại trước khi build Docker.

3.  **Lỗi liên quan đến bộ nhớ (OOM Killed):**
    *   Nguyên nhân: FAISS hoặc model AI tốn nhiều RAM.
    *   Khắc phục: Tăng giới hạn RAM cho Docker Desktop (nếu dùng trên Mac/Windows).
