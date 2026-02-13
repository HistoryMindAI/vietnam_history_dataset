"""
Export multilingual NLI model to ONNX (quantized) for Answer Validation.

Model: MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli
  - Lightweight multilingual NLI (same backbone as our cross-encoder)
  - 100+ languages including Vietnamese
  - Labels: entailment / neutral / contradiction
  
This model validates whether an answer (event text) actually addresses
the user's question, filtering out irrelevant results that passed
through semantic search + cross-encoder reranking.

Usage:
    python scripts/export_nli_model.py
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent / "ai-service"
OUTPUT_DIR = BASE_DIR / "onnx_nli"
MODEL_NAME = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"

def main():
    print(f"[EXPORT-NLI] Target model: {MODEL_NAME}")
    print(f"[EXPORT-NLI] Output directory: {OUTPUT_DIR}")
    
    try:
        from transformers import AutoTokenizer
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError as e:
        print(f"[EXPORT-NLI] Missing dependency: {e}")
        os.system(f"{sys.executable} -m pip install optimum[onnxruntime]")
        from transformers import AutoTokenizer
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from onnxruntime.quantization import quantize_dynamic, QuantType

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Download and save tokenizer
    print(f"[EXPORT-NLI] Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print("[EXPORT-NLI] Tokenizer saved")

    # Export to ONNX via Optimum
    print(f"[EXPORT-NLI] Exporting model to ONNX...")
    ort_model = ORTModelForSequenceClassification.from_pretrained(
        MODEL_NAME, export=True
    )
    ort_model.save_pretrained(str(OUTPUT_DIR))
    print("[EXPORT-NLI] ONNX model exported")

    # Quantize
    onnx_path = OUTPUT_DIR / "model.onnx"
    quantized_path = OUTPUT_DIR / "model_quantized.onnx"

    if onnx_path.exists():
        print("[EXPORT-NLI] Quantizing (int8 dynamic)...")
        quantize_dynamic(
            str(onnx_path),
            str(quantized_path),
            weight_type=QuantType.QInt8,
        )
        orig_mb = onnx_path.stat().st_size / (1024 * 1024)
        quant_mb = quantized_path.stat().st_size / (1024 * 1024)
        print(f"[EXPORT-NLI] Original:  {orig_mb:.1f} MB")
        print(f"[EXPORT-NLI] Quantized: {quant_mb:.1f} MB")
        onnx_path.unlink()
    else:
        for f in OUTPUT_DIR.glob("*.onnx"):
            print(f"  Found: {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")

    # Verify
    print("\n[EXPORT-NLI] Verifying...")
    try:
        import onnxruntime as ort
        import numpy as np
        
        session = ort.InferenceSession(str(quantized_path))
        valid_inputs = {i.name for i in session.get_inputs()}
        
        # NLI test: premise=question, hypothesis=answer
        premise = "Ai da danh quan Nguyen Mong?"
        hypothesis = "Tran Hung Dao danh tan quan Nguyen Mong tren song Bach Dang."
        
        enc = tokenizer(premise, hypothesis, return_tensors="np", padding=True, 
                       truncation=True, max_length=512)
        feed = {k: v for k, v in enc.items() if k in valid_inputs}
        logits = session.run(None, feed)[0]
        
        # Get label mapping
        from transformers import AutoConfig
        config = AutoConfig.from_pretrained(MODEL_NAME)
        labels = config.id2label
        
        # Softmax
        exp_logits = np.exp(logits[0] - np.max(logits[0]))
        probs = exp_logits / exp_logits.sum()
        
        print(f"[EXPORT-NLI] Premise:    '{premise}'")
        print(f"[EXPORT-NLI] Hypothesis: '{hypothesis}'")
        for i, label in labels.items():
            print(f"  {label}: {probs[i]:.4f}")
        
        print("[EXPORT-NLI] Verification PASSED")
    except Exception as e:
        print(f"[EXPORT-NLI] Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"\n{'='*60}")
    print(f"[EXPORT-NLI] DONE! Output: {OUTPUT_DIR}")
    print(f"{'='*60}")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
