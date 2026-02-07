#!/bin/bash
set -e

# Ensure we are in the script's directory
cd "$(dirname "$0")"

# Detect python executable
if command -v python3 >/dev/null 2>&1; then
    py="python3"
elif command -v python >/dev/null 2>&1; then
    py="python"
else
    echo "Error: Python not found"
    exit 1
fi

echo "Using python: $py"

# Ensure pip is available
if ! $py -m pip --version >/dev/null 2>&1; then
    echo "Pip not found. Attempting to install..."
    # Try ensurepip which is bundled with python
    if ! $py -m ensurepip --default-pip >/dev/null 2>&1; then
        echo "Error: Failed to install pip via ensurepip. Please install pip manually."
        exit 1
    fi
    $py -m pip install --upgrade pip
fi

cd ai-service

# Install dependencies
# Using --extra-index-url for CPU wheels if needed
echo "Installing dependencies..."
$py -m pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Start application
echo "Starting application..."
# Check if PORT is set, default to 8000
PORT=${PORT:-8000}
exec $py -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
