import os
import json
import faiss
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer
from tqdm import tqdm

# Config
ONNX_MODEL_PATH = "ai-service/onnx_model/model_quantized.onnx"
TOKENIZER_PATH = "ai-service/onnx_model" # Directory for AutoTokenizer
OUT_DIR = "ai-service/faiss_index"
DATA_PATH = "data/history_cleaned.jsonl" # Use local cleaned data
META_PATH = os.path.join(OUT_DIR, "meta.json")
INDEX_PATH = os.path.join(OUT_DIR, "index.bin")

def encode_onnx(session, tokenizer, texts, batch_size=32):
    embeddings = []
    
    for i in tqdm(range(0, len(texts), batch_size), desc="Encoding"):
        batch_texts = texts[i : i + batch_size]
        
        # Tokenize (Transformers AutoTokenizer returns numpy tensors with return_tensors="np")
        encoded = tokenizer(
            batch_texts, 
            return_tensors="np", 
            padding=True, 
            truncation=True, 
            max_length=512
        )
        
        # Prepare inputs
        inputs = {
            "input_ids": encoded["input_ids"].astype(np.int64),
            "attention_mask": encoded["attention_mask"].astype(np.int64)
        }
        
        # Check for token_type_ids
        input_names = [inp.name for inp in session.get_inputs()]
        if "token_type_ids" in input_names and "token_type_ids" in encoded:
            inputs["token_type_ids"] = encoded["token_type_ids"].astype(np.int64)
            
        # Inference
        outputs = session.run(None, inputs)
        
        # Mean Pooling
        last_hidden_state = outputs[0]
        input_mask_expanded = inputs["attention_mask"][:, :, None].astype(last_hidden_state.dtype)
        sum_embeddings = np.sum(last_hidden_state * input_mask_expanded, axis=1)
        sum_mask = np.sum(input_mask_expanded, axis=1)
        sum_mask = np.maximum(sum_mask, 1e-9)
        batch_embeddings = sum_embeddings / sum_mask
        
        # Normalize (L2)
        norm = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
        batch_embeddings = batch_embeddings / norm
        
        embeddings.append(batch_embeddings.astype("float32"))
        
    return np.vstack(embeddings) if embeddings else np.empty((0, 768), dtype="float32")

def build_index():
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

    print(f"🔧 Loading ONNX model: {ONNX_MODEL_PATH}")
    # Load tokenizer locally
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
    
    # Load settings for ONNX
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_options.intra_op_num_threads = 2
    session = ort.InferenceSession(ONNX_MODEL_PATH, sess_options)
    
    # Load Documents
    print(f"📥 Loading data from: {DATA_PATH}")
    documents = []
    texts = []
    
    # Path resolution
    data_path_real = DATA_PATH
    if not os.path.exists(data_path_real):
         # Try walking up if running from scripts/
         alt_path = "../data/history_cleaned.jsonl"
         if os.path.exists(alt_path):
             data_path_real = alt_path
         else:
             print(f"❌ Data file not found at {DATA_PATH} or {alt_path}")
             return

    # Count lines for tqdm
    total_lines = sum(1 for _ in open(data_path_real, "r", encoding="utf-8"))

    with open(data_path_real, "r", encoding="utf-8") as f:
        for line in tqdm(f, total=total_lines, desc="Reading JSONL"):
            line = line.strip()
            if not line: continue
            try:
                record = json.loads(line)
                content = record.get("content", "")
                if not content: continue
                
                # Logic mirroring index_docs.py
                doc_meta = {
                    "id": record.get("id"),
                    "subject_type": record.get("subject_type"),
                    "year": record.get("year", 0),
                    "title": record.get("title", ""),
                    "event": content, # Using content as event description
                    "story": content, # Content used as story to matching index_docs.py
                    "tone": "neutral", # Simplification
                    "nature": record.get("nature", []),
                    "persons": [], 
                    "places": [],
                    "keywords": [],
                    "dynasty": "Unknown" 
                }
                documents.append(doc_meta)
                texts.append(content)
            except json.JSONDecodeError:
                continue

    print(f"📝 Found {len(documents)} documents.")
    
    # Encode
    if not texts:
        print("❌ No texts to encode.")
        return

    print("🧠 Encoding documents...")
    embeddings = encode_onnx(session, tokenizer, texts, batch_size=32)
    
    # Build FAISS Index
    print("🗂️ Constructing FAISS index...")
    d = embeddings.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)
    
    # Save Index
    faiss.write_index(index, INDEX_PATH)
    
    # Save Metadata
    # Structure matching index_docs.py
    meta = {
        "model": "onnx-quantized",
        "dimension": int(d),
        "count": len(documents),
        "documents": documents
    }
    
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        
    print(f"🎉 Done! FAISS index saved to {INDEX_PATH}")
    print(f"✅ Metadata saved to {META_PATH}")

if __name__ == "__main__":
    build_index()
