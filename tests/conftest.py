import sys
from unittest.mock import MagicMock

# Mock heavy dependencies
mock_modules = [
    'faiss',
    'sentence_transformers',
    'datasets',
    'numpy'
]

for mod_name in mock_modules:
    sys.modules[mod_name] = MagicMock()
