import os
import sys
import datasets

# 1. Sửa lỗi hiển thị Tiếng Việt trên Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def prepare_data_local():
    # Đường dẫn tuyệt đối đến thư mục local của bạn
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(base_dir, "vietnam_history_dataset")

    print(f"[INFO] Đang nạp dataset từ: {dataset_path}")

    try:
        # Nạp dataset từ thư mục local
        ds = datasets.load_dataset(dataset_path, split="train")
        
        # KIỂM TRA TÊN CỘT THỰC TẾ
        column_names = ds.column_names
        print(f"[INFO] Các cột tìm thấy: {column_names}")
        
        # Ưu tiên lấy cột 'text', nếu không có thì lấy cột đầu tiên có dữ liệu
        target_col = 'text' if 'text' in column_names else column_names[0]
        print(f"[INFO] Sẽ trích xuất dữ liệu từ cột: '{target_col}'")

        os.makedirs("data", exist_ok=True)
        file_path = "data/history_docs.txt"
        
        count = 0
        with open(file_path, "w", encoding="utf-8") as f:
            for item in ds:
                if count >= 2000: break # Lấy thử 2k dòng
                
                val = item.get(target_col)
                if val and str(val).strip():
                    # Làm sạch văn bản: bỏ xuống dòng để FAISS không bị lỗi
                    clean_text = str(val).strip().replace("\n", " ")
                    f.write(clean_text + "\n")
                    count += 1
        
        print(f"[DONE] Đã trích xuất thành công {count} dòng vào {file_path}")

    except Exception as e:
        print(f"[Lỗi] Không thể nạp dữ liệu: {e}")

if __name__ == "__main__":
    prepare_data_local()