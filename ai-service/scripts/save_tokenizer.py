from transformers import AutoTokenizer
import os

MODEL_ID = "keepitreal/vietnamese-sbert"
OUTPUT_PATH = "ai-service/onnx_model/tokenizer.json"

def save_tokenizer():
    print(f"Loading tokenizer from {MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    
    print(f"Saving to {OUTPUT_PATH}")
    # This saves the backend tokenizer as a single JSON file
    if tokenizer.is_fast:
        tokenizer.save_pretrained("ai-service/onnx_model")
        # save_pretrained saves tokenizer.json if fast.
        # Check if it did.
    else:
        print("Tokenizer is not fast. Attempting conversion.")
        from transformers import PreTrainedTokenizerFast
        # Try to convert
        fast_tokenizer = PreTrainedTokenizerFast.from_pretrained(MODEL_ID)
        fast_tokenizer.save_pretrained("ai-service/onnx_model")

if __name__ == "__main__":
    save_tokenizer()
