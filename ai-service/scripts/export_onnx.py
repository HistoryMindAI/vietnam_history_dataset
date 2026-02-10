import os
import shutil
from pathlib import Path
import torch
from sentence_transformers import SentenceTransformer
import onnx
from onnxruntime.quantization import quantize_dynamic, QuantType

# Config
MODEL_ID = "keepitreal/vietnamese-sbert"
OUTPUT_DIR = Path("ai-service/onnx_model")
ONNX_MODEL_NAME = "model.onnx"
QUANT_MODEL_NAME = "model_quantized.onnx"

def export_to_onnx():
    print(f"Load model: {MODEL_ID}")
    model = SentenceTransformer(MODEL_ID)
    model.eval()
    
    # Create output dir
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save tokenizer
    print("Saving tokenizer...")
    model.tokenizer.save_pretrained(OUTPUT_DIR)
    
    # Prepare dummy input
    text = "Xin chào Việt Nam"
    features = model.tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    inputs = {k: v for k, v in features.items()}
    
    # Get the transformer part (usually module 0)
    transformer = model[0].auto_model
    
    # Export
    print("Exporting to ONNX...")
    output_path = OUTPUT_DIR / ONNX_MODEL_NAME
    
    # Dynamic axes for variable length inputs
    dynamic_axes = {
        'input_ids': {0: 'batch_size', 1: 'sequence_length'},
        'attention_mask': {0: 'batch_size', 1: 'sequence_length'}
    }
    if 'token_type_ids' in inputs:
        dynamic_axes['token_type_ids'] = {0: 'batch_size', 1: 'sequence_length'}
        input_names = ['input_ids', 'attention_mask', 'token_type_ids']
    else:
        input_names = ['input_ids', 'attention_mask']
        
    torch.onnx.export(
        transformer,
        tuple(inputs.values()),
        str(output_path),
        input_names=input_names,
        output_names=['last_hidden_state', 'pooler_output'],
        dynamic_axes=dynamic_axes,
        opset_version=14,
        do_constant_folding=True
    )
    print(f"Exported: {output_path}")
    
    # Quantize
    print("Quantizing...")
    quant_output_path = OUTPUT_DIR / QUANT_MODEL_NAME
    quantize_dynamic(
        model_input=output_path,
        model_output=quant_output_path,
        weight_type=QuantType.QUInt8
    )
    print(f"Quantized: {quant_output_path}")
    
    # Clean up full precision model
    os.remove(output_path)
    print("Removed full precision model to save space.")
    
    print("Done.")

if __name__ == "__main__":
    export_to_onnx()
