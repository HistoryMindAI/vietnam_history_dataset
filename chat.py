import sys, os, types, io

# ===================== SIÊU VÁ LỖI TRANSFORMERS (WINDOWS) =====================
import transformers

# 1. Đánh lừa transformers rằng flash_attn KHÔNG tồn tại (để tránh lỗi __spec__)
original_is_package_available = transformers.utils.import_utils._is_package_available
def patched_is_package_available(pkg_name):
    if pkg_name in ["flash_attn", "triton"]:
        return False
    return original_is_package_available(pkg_name)

transformers.utils.import_utils._is_package_available = patched_is_package_available

# 2. Vô hiệu hóa Triton ở mức hệ thống
os.environ["TORCH_COMPILE_DISABLE"] = "1"
os.environ["DISABLE_TRITON"] = "1"

# ===================== IMPORT CHÍNH =====================
import json
import faiss
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig, BloomTokenizerFast

# Fix Unicode hiển thị trên Console Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ===================== CONFIG =====================
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHAT_MODEL  = "vinai/PhoGPT-4B-Chat"
INDEX_PATH = "./faiss_index/history.index"
META_PATH  = "./faiss_index/meta.json"

def main():
    print("[INFO] Nạp embedding model (CPU)...")
    embedder = SentenceTransformer(EMBED_MODEL, device="cpu")

    if not os.path.exists(INDEX_PATH):
        print("[LỖI] Không tìm thấy FAISS index. Hãy chạy index_docs.py!")
        return

    with open(META_PATH, encoding="utf-8") as f:
        docs = json.load(f)
    index = faiss.read_index(INDEX_PATH)

    print("[INFO] Nạp PhoGPT-4B-Chat (CPU – Yêu cầu ~12GB RAM)...")

    # Nạp cấu hình
    config = AutoConfig.from_pretrained(CHAT_MODEL, trust_remote_code=True)
    
    # Ép sử dụng kiến trúc attention cơ bản (eager) để không gọi Triton/Flash
    config.attn_config = {"attn_impl": "torch"} 
    
    # Nạp Tokenizer
    try:
        tokenizer = AutoTokenizer.from_pretrained(CHAT_MODEL, trust_remote_code=True, use_fast=False)
    except:
        tokenizer = BloomTokenizerFast.from_pretrained(CHAT_MODEL, trust_remote_code=True)

    # Nạp Model
    model = AutoModelForCausalLM.from_pretrained(
        CHAT_MODEL,
        config=config,
        trust_remote_code=True,
        torch_dtype=torch.float32,
        device_map={"": "cpu"},
        attn_implementation="eager",
        low_cpu_mem_usage=True
    )
    model.eval()

    print("\n" + "="*40)
    print("🇻🇳 HistoryMindAI – Đã sẵn sàng trả lời!")
    print("="*40 + "\n")

    while True:
        try:
            query = input("Bạn hỏi: ").strip()
        except EOFError: break
        if not query or query.lower() in ["exit", "thoát"]: break

        # RAG: Tìm ngữ cảnh
        q_emb = embedder.encode([query])
        _, I = index.search(q_emb, 2)
        context = "\n".join(docs[i] for i in I[0])

        # Prompt format chuẩn PhoGPT
        prompt = f"### Câu hỏi: {query} Dựa trên thông tin: {context} ### Trả lời:"

        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                # max_new_tokens=400,
                # temperature=0.1,
                # top_p=0.9,
                # do_sample=True,
                # eos_token_id=tokenizer.eos_token_id

                max_new_tokens=100,  # Giới hạn trả lời ngắn gọn
                do_sample=False,     # Quan trọng: Tắt cái này giúp CPU chạy nhanh hơn
                num_beams=1,         # Không dùng tìm kiếm chùm
                use_cache=True
            )

        text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        answer = text.split("### Trả lời:")[-1].strip()
        print(f"\nBot: {answer}\n")

if __name__ == "__main__":
    main()