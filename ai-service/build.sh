#!/bin/bash
# Railway build script for AI service
# Downloads data from HuggingFace and builds FAISS index

set -e

echo "🔧 Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "📊 Checking FAISS index..."

# Check if FAISS index exists and is recent
if [ -f "faiss_index/history.index" ] && [ -f "faiss_index/meta.json" ]; then
    # Check if index has enough documents (should be > 1000)
    DOC_COUNT=$(python -c "import json; print(json.load(open('faiss_index/meta.json'))['count'])" 2>/dev/null || echo "0")
    
    if [ "$DOC_COUNT" -gt 1000 ]; then
        echo "✅ FAISS index exists with $DOC_COUNT documents, skipping rebuild"
        exit 0
    else
        echo "⚠️ FAISS index has only $DOC_COUNT documents, rebuilding..."
    fi
fi

echo "🔨 Building FAISS index from HuggingFace..."
echo "   Dataset: minhxthanh/Vietnam-History-1M-Vi"
echo "   Max samples: ${MAX_SAMPLES:-50000}"

# Build from HuggingFace
python scripts/build_from_huggingface.py

echo "✅ Build complete!"
echo ""

# Show stats
python -c "
import json
meta = json.load(open('faiss_index/meta.json'))
print(f'📊 Index Stats:')
print(f'   Documents: {meta[\"count\"]}')
print(f'   Source: {meta.get(\"source\", \"local\")}')
"
