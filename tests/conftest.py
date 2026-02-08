"""
conftest.py - Pytest configuration for AI service tests

Sets up Python path and mocks for heavy dependencies.
"""
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

# Add ai-service to path for imports
AI_SERVICE_DIR = Path(__file__).parent.parent / "ai-service"
PIPELINE_DIR = Path(__file__).parent.parent / "pipeline"

if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))
if str(PIPELINE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR.parent))

# Mock heavy dependencies that aren't needed for unit tests
mock_modules = [
    'faiss',
    'sentence_transformers',
    'datasets',
    'huggingface_hub',
]

for mod_name in mock_modules:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Mock numpy with minimal implementation
import numpy as np
