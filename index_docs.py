import os
import json
import faiss
import sys
from sentence_transformers import SentenceTransformer

# Cấu hình
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" #
DOC_FILE = "./data/history_docs.txt" #
INDEX_DIR = "faiss_index" #

def main():
    # Sửa lỗi hiển thị tiếng Việt trên Terminal Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    if not os.path.exists(DOC_FILE):
        print(f"[Error] Không tìm thấy file {DOC_FILE}. Hãy chạy run.py trước!")
        return

    print("[INFO] Đang nạp model embedding...")
    model = SentenceTransformer(MODEL_NAME) #

    print("[INFO] Đang đọc tài liệu lịch sử...")
    with open(DOC_FILE, encoding="utf-8") as f:
        # Lọc bỏ các dòng trống và các dòng quá ngắn (dưới 10 ký tự thường là rác)
        docs = [line.strip() for line in f if len(line.strip()) > 10] 

    if not docs:
        print("[Error] Dữ liệu trong history_docs.txt quá ít hoặc trống!")
        return

    print(f"[INFO] Tổng số đoạn văn bản: {len(docs)}")
    
    # Tạo vector đại diện cho văn bản
    print("[INFO] Đang tạo vector (embeddings)...")
    embeddings = model.encode(docs, show_progress_bar=True) #

    # Tạo FAISS index
    dimension = embeddings.shape[1] #
    index = faiss.IndexFlatL2(dimension) #
    index.add(embeddings) #

    # Lưu index và metadata
    os.makedirs(INDEX_DIR, exist_ok=True) #
    faiss.write_index(index, os.path.join(INDEX_DIR, "history.index")) #
    
    # Lưu metadata (docs) để sau này chat.py có thể lấy nội dung gốc
    with open(os.path.join(INDEX_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2) #

    print("[DONE] Đã tạo xong FAISS index!")

if __name__ == "__main__":
    main()