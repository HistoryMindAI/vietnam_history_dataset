#!/bin/bash
# Railway build script for AI service
# This script is called by Railway during deployment

set -e

echo "🔧 Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "📊 Checking FAISS index..."
if [ -f "faiss_index/history.index" ] && [ -f "faiss_index/meta.json" ]; then
    echo "✅ FAISS index already exists, skipping rebuild"
else
    echo "🔨 Building FAISS index..."
    python scripts/build_faiss.py
fi

echo "✅ Build complete!"
