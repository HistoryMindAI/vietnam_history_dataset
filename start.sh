#!/bin/bash
set -e

# Detect python command
if command -v python > /dev/null 2>&1; then
    py=python
elif command -v python3 > /dev/null 2>&1; then
    py=python3
else
    echo "Python not found"
    exit 1
fi

cd ai-service
$py -m pip install -r requirements.txt
$py -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
