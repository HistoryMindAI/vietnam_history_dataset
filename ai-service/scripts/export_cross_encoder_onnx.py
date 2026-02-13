"""
Export Cross-Encoder model to ONNX format with quantization.

This script converts a Cross-Encoder model from sentence-transformers
into an ONNX format for lightweight production deployment.
Only needs to run ONCE locally (requires torch + sentence-transformers).
Production only needs onnxruntime.

Usage:
    python scripts/export_cross_encoder_onnx.py
"""

import os
import sys
import shutil
from pathlib import Path

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from onnxruntime.quantization import quantize_dynamic, QuantType

# Config
MODEL_ID = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# Resolve path relative to this script's parent (ai-service/scripts/ -> ai-service/)
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR.parent / "onnx_cross_encoder"
ONNX_MODEL_NAME = "model.onnx"
QUANT_MODEL_NAME = "model_quantized.onnx"


def export_cross_encoder_to_onnx():
    """Export Cross-Encoder to ONNX and quantize to INT8."""
    print(f"[1/5] Loading Cross-Encoder model: {MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
    model.eval()

    # Create output dir
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save tokenizer
    print("[2/5] Saving tokenizer...")
    tokenizer.save_pretrained(OUTPUT_DIR)

    # Prepare dummy input (Cross-Encoder takes query-document PAIR as input)
    print("[3/5] Preparing dummy input for ONNX export...")
    dummy_query = "Nhà Trần chống quân Nguyên Mông"
    dummy_doc = "Năm 1288, Trần Hưng Đạo đánh bại quân Nguyên tại sông Bạch Đằng."

    # Cross-Encoder tokenizes query+doc as a sentence pair
    inputs = tokenizer(
        dummy_query, dummy_doc,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )

    # Dynamic axes for variable-length inputs
    dynamic_axes = {
        "input_ids": {0: "batch_size", 1: "sequence_length"},
        "attention_mask": {0: "batch_size", 1: "sequence_length"},
        "logits": {0: "batch_size"},
    }

    input_names = ["input_ids", "attention_mask"]
    input_tensors = [inputs["input_ids"], inputs["attention_mask"]]

    if "token_type_ids" in inputs:
        dynamic_axes["token_type_ids"] = {0: "batch_size", 1: "sequence_length"}
        input_names.append("token_type_ids")
        input_tensors.append(inputs["token_type_ids"])

    # Export to ONNX
    print("[4/5] Exporting to ONNX...")
    output_path = OUTPUT_DIR / ONNX_MODEL_NAME

    torch.onnx.export(
        model,
        tuple(input_tensors),
        str(output_path),
        input_names=input_names,
        output_names=["logits"],
        dynamic_axes=dynamic_axes,
        opset_version=18,
        do_constant_folding=True,
    )
    print(f"  Exported: {output_path}")

    # Verify ONNX model
    import onnx
    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)
    print("  ONNX model validated OK")

    # Quantize to INT8
    print("[5/5] Quantizing to INT8...")
    quant_path = OUTPUT_DIR / QUANT_MODEL_NAME

    try:
        quantize_dynamic(
            model_input=output_path,
            model_output=quant_path,
            weight_type=QuantType.QUInt8,
        )
        # Report sizes
        full_size = output_path.stat().st_size / (1024 * 1024)
        quant_size = quant_path.stat().st_size / (1024 * 1024)
        print(f"  Full model:      {full_size:.1f} MB")
        print(f"  Quantized model: {quant_size:.1f} MB")
        print(f"  Size reduction:  {(1 - quant_size / full_size) * 100:.0f}%")

        # Remove full precision model
        os.remove(output_path)
        print("  Removed full precision model.")

    except Exception as e:
        print(f"  [WARN] Quantization failed: {e}")
        print("  Using full precision model instead (still lightweight for MiniLM).")
        # Rename full model to quantized name so config paths work
        if output_path.exists():
            shutil.move(str(output_path), str(quant_path))
            model_size = quant_path.stat().st_size / (1024 * 1024)
            print(f"  Model size: {model_size:.1f} MB (full precision)")

    # Quick inference test
    print("\n--- Quick Inference Test ---")
    import onnxruntime as ort
    session = ort.InferenceSession(str(quant_path))

    test_pairs = [
        ("Nhà Trần chống Nguyên Mông", "Năm 1288, Trần Hưng Đạo đánh bại quân Nguyên tại Bạch Đằng"),
        ("Nhà Trần chống Nguyên Mông", "Hồ Quý Ly lập nhà Hồ năm 1400, cải cách hành chính"),
        ("Hai Bà Trưng khởi nghĩa", "Trưng Trắc và Trưng Nhị lãnh đạo khởi nghĩa chống Hán năm 40"),
        ("Hai Bà Trưng khởi nghĩa", "Hồ Quý Ly cải cách mạnh, đổi quốc hiệu Đại Ngu"),
    ]

    for query, doc in test_pairs:
        enc = tokenizer(query, doc, return_tensors="np", padding=True, truncation=True, max_length=512)
        feed = {k: v for k, v in enc.items() if k in [n.name for n in session.get_inputs()]}
        score = session.run(None, feed)[0][0][0]
        print(f"  Score={score:+.3f} | Q: '{query}' → D: '{doc[:60]}...'")

    print(f"\n[DONE] Cross-Encoder ONNX model ready at: {OUTPUT_DIR}")
    print("   Commit the 'onnx_cross_encoder/' folder to Git.")


if __name__ == "__main__":
    export_cross_encoder_to_onnx()
