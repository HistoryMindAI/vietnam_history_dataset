from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import Whitespace
from tokenizers.trainers import BpeTrainer
from tokenizers.processors import TemplateProcessing
import os

# Paths
VOCAB_PATH = "ai-service/onnx_model/vocab.txt"
MERGES_PATH = "ai-service/onnx_model/bpe.codes"
OUTPUT_PATH = "ai-service/onnx_model/tokenizer.json"

def build_tokenizer():
    print("Building tokenizer from vocab and merges...")
    
    # Initialize BPE model
    # Note: vocab.txt usually contains tokens line by line.
    # But BPE model needs a vocab dictionary (token -> id) + merges.
    # "vocab.txt" in this folder might strictly be the vocab.
    # "bpe.codes" is merges.
    
    # Check regular BPE structure
    # Usually: vocab.json + merges.txt
    # Here we have: vocab.txt + bpe.codes? 
    # This looks like FastText or older formats?
    # Or maybe it's just standard BPE with different names.
    
    # Let's try to load using transformers manually if converting failed.
    # Wait, "keepitreal/vietnamese-sbert" seems to be based on "bkai-foundation-models/vietnamese-bi-encoder".
    # It likely uses "RobertaTokenizer".
    
    # Let's try to start a "Roberta" tokenizer using the tokenizers library.
    # But first, verify if we can just use the PreTrainedTokenizerFast from files.
    
    try:
        from transformers import RobertaTokenizerFast
        print("Attempting to load as RobertaTokenizerFast...")
        tokenizer = RobertaTokenizerFast(
            vocab_file=VOCAB_PATH,
            merges_file=MERGES_PATH,
            tokenizer_file=None,
        )
        tokenizer.save_pretrained("ai-service/onnx_model")
        print("Success!")
        return
    except Exception as e:
        print(f"Failed to load as RobertaTokenizerFast: {e}")

    # Fallback: Try generic AutoTokenizer again but force use_fast=True with upgrade checks?
    # No, previous attempts failed.
    
    pass

if __name__ == "__main__":
    build_tokenizer()
