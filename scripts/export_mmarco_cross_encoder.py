"""
Export multilingual mmarco Cross-Encoder to ONNX (quantized).

Replaces the English-only ms-marco model with a multilingual version
that understands Vietnamese queries for better reranking accuracy.

Model: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
  - 14 languages including Vietnamese
  - Trained on multilingual MS MARCO passages
  
Usage:
    python scripts/export_mmarco_cross_encoder.py
"""

import os
import sys
import shutil
from pathlib import Path

# Target directory
BASE_DIR = Path(__file__).resolve().parent.parent / "ai-service"
OUTPUT_DIR = BASE_DIR / "onnx_cross_encoder_new"
MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

def main():
    print(f"[EXPORT] Target model: {MODEL_NAME}")
    print(f"[EXPORT] Output directory: {OUTPUT_DIR}")
    
    # Step 1: Install dependencies if needed
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError as e:
        print(f"[EXPORT] Missing dependency: {e}")
        print("[EXPORT] Installing required packages...")
        os.system(f"{sys.executable} -m pip install torch transformers optimum[onnxruntime] onnxruntime")
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from onnxruntime.quantization import quantize_dynamic, QuantType
    
    # Step 2: Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 3: Download and save tokenizer
    print(f"[EXPORT] Downloading tokenizer from {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print("[EXPORT] Tokenizer saved ✅")
    
    # Step 4: Export to ONNX via Optimum
    print(f"[EXPORT] Exporting model to ONNX...")
    ort_model = ORTModelForSequenceClassification.from_pretrained(
        MODEL_NAME, export=True
    )
    
    # Save the ONNX model
    ort_model.save_pretrained(str(OUTPUT_DIR))
    print("[EXPORT] ONNX model exported ✅")
    
    # Step 5: Quantize the ONNX model (int8 dynamic quantization)
    onnx_path = OUTPUT_DIR / "model.onnx"
    quantized_path = OUTPUT_DIR / "model_quantized.onnx"
    
    if onnx_path.exists():
        print("[EXPORT] Quantizing model (int8 dynamic)...")
        quantize_dynamic(
            str(onnx_path),
            str(quantized_path),
            weight_type=QuantType.QInt8,
        )
        
        # Report sizes
        original_size = onnx_path.stat().st_size / (1024 * 1024)
        quantized_size = quantized_path.stat().st_size / (1024 * 1024)
        print(f"[EXPORT] Original ONNX:    {original_size:.1f} MB")
        print(f"[EXPORT] Quantized ONNX:   {quantized_size:.1f} MB")
        print(f"[EXPORT] Size reduction:   {(1 - quantized_size/original_size)*100:.1f}%")
        
        # Remove the unquantized model to save space
        onnx_path.unlink()
        print("[EXPORT] Removed unquantized model to save space")
    else:
        print(f"[WARN] ONNX model not found at {onnx_path}")
        # Check if the file has a different name
        for f in OUTPUT_DIR.glob("*.onnx"):
            print(f"  Found: {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")
    
    # Step 6: Verify the exported model
    print("\n[EXPORT] Verifying exported model...")
    try:
        import onnxruntime as ort
        session = ort.InferenceSession(str(quantized_path))
        inputs = tokenizer(
            "Trần Hưng Đạo đánh quân Nguyên Mông",
            "Chiến thắng Bạch Đằng năm 1288",
            return_tensors="np",
            padding=True,
            truncation=True,
            max_length=512,
        )
        import numpy as np
        model_inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64),
        }
        # Add token_type_ids if the model expects them
        input_names = [i.name for i in session.get_inputs()]
        if "token_type_ids" in input_names and "token_type_ids" in inputs:
            model_inputs["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)
        
        outputs = session.run(None, model_inputs)
        score = outputs[0][0]
        print(f"[EXPORT] Test query: 'Trần Hưng Đạo đánh quân Nguyên Mông'")
        print(f"[EXPORT] Test doc:   'Chiến thắng Bạch Đằng năm 1288'")
        print(f"[EXPORT] Score:      {score}")
        print("[EXPORT] Verification PASSED ✅")
    except Exception as e:
        print(f"[EXPORT] Verification FAILED: {e}")
        return False
    
    # Step 7: Summary
    print("\n" + "=" * 60)
    print("[EXPORT] DONE! Model exported successfully.")
    print(f"[EXPORT] Output: {OUTPUT_DIR}")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Backup current onnx_cross_encoder/")
    print("  2. Replace with onnx_cross_encoder_new/")
    print("  3. Update config.py if needed")
    print("  4. Test with test_manual.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
