import os
import json
import gc
from collections import defaultdict

# ===============================
# IMPORTS: MOVED HEAVY LIBS TO load_resources
# ===============================
# import faiss  <-- LAZY LOADED
# from sentence_transformers import SentenceTransformer <-- LAZY LOADED

from .config import (
    EMBED_MODEL,
    INDEX_PATH,
    META_PATH,
    EMBED_MODEL_PATH,
    TOKENIZER_PATH,
    KNOWLEDGE_BASE_PATH,
    CROSS_ENCODER_MODEL_PATH,
    CROSS_ENCODER_TOKENIZER_PATH,
    NLI_MODEL_PATH,
    NLI_TOKENIZER_PATH,
)

# Global resources (initialized in load_resources)
session = None
tokenizer = None
index = None
DOCUMENTS = []
DOCUMENTS_BY_YEAR = defaultdict(list)
LOADING_ERROR = None

# Cross-Encoder Reranker (ONNX)
cross_encoder_session = None
cross_encoder_tokenizer = None

# NLI Answer Validator (ONNX)
nli_session = None
nli_tokenizer = None

# Dynamic inverted indexes (auto-built from DOCUMENTS at startup)
PERSONS_INDEX = defaultdict(list)     # "trần hưng đạo" → [doc_idx, ...]
DYNASTY_INDEX = defaultdict(list)     # "trần" → [doc_idx, ...]
KEYWORD_INDEX = defaultdict(list)     # "khởi_nghĩa" → [doc_idx, ...]
PLACES_INDEX = defaultdict(list)      # "bạch đằng" → [doc_idx, ...]

# Knowledge base (loaded from knowledge_base.json)
PERSON_ALIASES = {}    # "quang trung" → "nguyễn huệ"
TOPIC_SYNONYMS = {}    # "mông cổ" → "nguyên mông"
DYNASTY_ALIASES = {}   # "nhà trần" → "trần"
RESISTANCE_SYNONYMS = {}  # "kháng chiến" → [specific events]
IMPLICIT_CONTEXT = {}     # vietnam_indicators list

# Dynamic data loaded from knowledge_base.json (replaces hardcoded dicts)
ABBREVIATIONS = {}          # "dbp" → "điện biên phủ"
TYPO_FIXES = {}             # "quangtrung" → "quang trung"
QUESTION_PATTERNS = {}      # "person_search" → ["ai đã", ...]
HISTORICAL_PHRASES = set()  # Auto-generated multi-word phrases
_knowledge_base_raw = {}    # Raw knowledge_base.json for services to read

def load_resources():
    """
    Load all heavy resources (Embedding model, FAISS index, Metadata).
    This should be called during app startup (lifespan) in a background thread.
    """
    global session, tokenizer, index, DOCUMENTS, DOCUMENTS_BY_YEAR, LOADING_ERROR
    
    print("[STARTUP] Loading embedding model & FAISS...", flush=True)

    try:
        # ONNX Imports
        import onnxruntime as ort
        from transformers import AutoTokenizer
        import numpy as np

        # ===============================
        # LOAD ONNX MODEL & TOKENIZER
        # ===============================
        try:
            print(f"[STARTUP] Loading ONNX model from {EMBED_MODEL_PATH}...", flush=True)
            
            # 1. Load Tokenizer (Slow/Fast agnostic)
            # Use local path (onnx_model folder)
            tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH)
            
            print("[STARTUP] Tokenizer loaded.", flush=True)

            # 2. Load ONNX Session
            sess_options = ort.SessionOptions()
            # Optimize for single-core/low-memory envs
            sess_options.intra_op_num_threads = 1 
            sess_options.inter_op_num_threads = 1
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            session = ort.InferenceSession(EMBED_MODEL_PATH, sess_options)
            print("[STARTUP] ONNX Session loaded successfully.", flush=True)
            
            gc.collect()

        except Exception as e:
            print(f"[FATAL] Failed to load ONNX model: {e}", flush=True)
            raise e

        # ===============================
        # LOAD FAISS INDEX
        # ===============================
        index = None

        if os.path.exists(INDEX_PATH):
            try:
                import faiss
                index = faiss.read_index(INDEX_PATH)
                print(f"[STARTUP] FAISS index loaded from {INDEX_PATH}", flush=True)
            except Exception as e:
                print(f"[ERROR] Failed to read FAISS index: {e}", flush=True)
        else:
            print(f"[WARN] FAISS index not found at {INDEX_PATH}", flush=True)

        # ===============================
        # AUTO-BUILD INDEX IF MISSING
        # ===============================
        if index is None:
            print("[FATAL] FAISS index not found! We are in READ-ONLY mode.", flush=True)
            print("[FATAL] You must build 'faiss_index' locally and commit it to Git.", flush=True)
            # We fail fast here because the user explicitly requested NO server-side building.
            raise RuntimeError("FAISS index missing. Server requires pre-built index.")

        # ===============================
        # LOAD METADATA
        # ===============================
        if os.path.exists(META_PATH):
            try:
                with open(META_PATH, encoding="utf-8") as f:
                    META_RAW = json.load(f)
                print(f"[STARTUP] Metadata loaded from {META_PATH}", flush=True)
            except Exception as e:
                print(f"[ERROR] Failed to read metadata: {e}", flush=True)
                META_RAW = {"documents": []}
        else:
            print(f"[WARN] Metadata not found at {META_PATH}", flush=True)
            META_RAW = {"documents": []}

        DOCUMENTS = META_RAW.get("documents", [])

        # ===============================
        # PRE-CALCULATE YEAR INDEX
        # ===============================
        DOCUMENTS_BY_YEAR = defaultdict(list)
        for doc in DOCUMENTS:
            y = doc.get("year")
            if y is not None:
                DOCUMENTS_BY_YEAR[y].append(doc)

        # ===============================
        # BUILD INVERTED INDEXES (Data-Driven)
        # ===============================
        _build_inverted_indexes()
        _load_knowledge_base()

        # ===============================
        # AUTO-ENRICH NLU MAPS (from knowledge_base data)
        # ===============================
        try:
            from app.services.query_understanding import build_unaccented_map_from_knowledge_base
            build_unaccented_map_from_knowledge_base()
        except Exception as e:
            print(f"[WARN] Failed to auto-enrich UNACCENTED_MAP: {e}", flush=True)

        # Build HISTORICAL_PHRASES from knowledge base (auto-generated)
        _build_historical_phrases()

        # ===============================
        # LOAD CROSS-ENCODER ONNX (optional)
        # ===============================
        _load_cross_encoder()

        # ===============================
        # LOAD NLI ANSWER VALIDATOR (optional)
        # ===============================
        _load_nli_model()

        print(
            f"[STARTUP] Ready | docs={len(DOCUMENTS)} | years={len(DOCUMENTS_BY_YEAR)}"
            f" | persons={len(PERSONS_INDEX)} | dynasties={len(DYNASTY_INDEX)}"
            f" | aliases={len(PERSON_ALIASES)} | abbrevs={len(ABBREVIATIONS)}"
            f" | typos={len(TYPO_FIXES)} | phrases={len(HISTORICAL_PHRASES)}"
            f" | cross_encoder={'✅' if cross_encoder_session else '❌'}"
            f" | nli={'✅' if nli_session else '❌'}",
            flush=True
        )

    except Exception as e:
        print(f"❌ [STARTUP] Critical failure in load_resources: {e}", flush=True)
        LOADING_ERROR = str(e)
        # We catch everything so the thread doesn't crash silently without setting the flag.


def _build_inverted_indexes():
    """
    Auto-build inverted indexes from DOCUMENTS metadata.
    No hardcoded patterns — scales automatically with data.
    """
    global PERSONS_INDEX, DYNASTY_INDEX, KEYWORD_INDEX, PLACES_INDEX

    PERSONS_INDEX = defaultdict(list)
    DYNASTY_INDEX = defaultdict(list)
    KEYWORD_INDEX = defaultdict(list)
    PLACES_INDEX = defaultdict(list)

    for idx, doc in enumerate(DOCUMENTS):
        # Index persons (merge both fields, deduplicate via set)
        all_persons = set(doc.get("persons", []) + doc.get("persons_all", []))
        for person in all_persons:
            key = person.strip().lower()
            if key and len(key) > 1:
                PERSONS_INDEX[key].append(idx)

        # Index dynasty
        dynasty = doc.get("dynasty", "").strip().lower()
        if dynasty:
            DYNASTY_INDEX[dynasty].append(idx)

        # Index keywords
        for kw in doc.get("keywords", []):
            key = kw.strip().lower().replace("_", " ")
            if key:
                KEYWORD_INDEX[key].append(idx)

        # Index places
        for place in doc.get("places", []):
            key = place.strip().lower()
            if key and len(key) > 1:
                PLACES_INDEX[key].append(idx)

    print(
        f"[STARTUP] Inverted indexes built:"
        f" persons={len(PERSONS_INDEX)}, dynasties={len(DYNASTY_INDEX)},"
        f" keywords={len(KEYWORD_INDEX)}, places={len(PLACES_INDEX)}",
        flush=True
    )


def _load_knowledge_base():
    """
    Load aliases & synonyms from knowledge_base.json.
    This is the ONLY file that needs editing when scaling —
    no Python code changes required.
    """
    global PERSON_ALIASES, TOPIC_SYNONYMS, DYNASTY_ALIASES
    global ABBREVIATIONS, TYPO_FIXES, QUESTION_PATTERNS
    global _knowledge_base_raw
    global RESISTANCE_SYNONYMS, IMPLICIT_CONTEXT

    PERSON_ALIASES = {}
    TOPIC_SYNONYMS = {}
    DYNASTY_ALIASES = {}
    ABBREVIATIONS = {}
    TYPO_FIXES = {}
    QUESTION_PATTERNS = {}
    RESISTANCE_SYNONYMS = {}
    IMPLICIT_CONTEXT = {}

    if not os.path.exists(KNOWLEDGE_BASE_PATH):
        print(f"[WARN] Knowledge base not found at {KNOWLEDGE_BASE_PATH}", flush=True)
        return

    try:
        with open(KNOWLEDGE_BASE_PATH, encoding="utf-8") as f:
            kb = json.load(f)

        # Store raw KB for services (e.g., cross_encoder_service reads reranker_config)
        _knowledge_base_raw = kb

        # Build person alias lookup: alias → canonical name
        for canonical, aliases in kb.get("person_aliases", {}).items():
            canonical_lower = canonical.strip().lower()
            PERSON_ALIASES[canonical_lower] = canonical_lower
            for alias in aliases:
                alias_lower = alias.strip().lower()
                if alias_lower:
                    PERSON_ALIASES[alias_lower] = canonical_lower

        # Build topic synonym lookup: synonym → canonical topic
        for canonical, synonyms in kb.get("topic_synonyms", {}).items():
            canonical_lower = canonical.strip().lower()
            TOPIC_SYNONYMS[canonical_lower] = canonical_lower
            for syn in synonyms:
                syn_lower = syn.strip().lower()
                if syn_lower:
                    TOPIC_SYNONYMS[syn_lower] = canonical_lower

        # Build dynasty alias lookup: alias → canonical dynasty name
        for canonical, aliases in kb.get("dynasty_aliases", {}).items():
            canonical_lower = canonical.strip().lower()
            DYNASTY_ALIASES[canonical_lower] = canonical_lower
            for alias in aliases:
                alias_lower = alias.strip().lower()
                if alias_lower:
                    DYNASTY_ALIASES[alias_lower] = canonical_lower

        # Load abbreviations (replaces hardcoded ABBREVIATIONS in query_understanding.py)
        ABBREVIATIONS = {k.strip().lower(): v.strip().lower()
                         for k, v in kb.get("abbreviations", {}).items()}

        # Load typo fixes (replaces hardcoded TYPO_FIXES in query_understanding.py)
        TYPO_FIXES = {k.strip().lower(): v.strip().lower()
                      for k, v in kb.get("typo_fixes", {}).items()}

        # Load question patterns (supplements regex in extract_question_intent)
        QUESTION_PATTERNS = kb.get("question_patterns", {})

        # Load resistance synonyms (for implicit context expansion)
        RESISTANCE_SYNONYMS = kb.get("resistance_synonyms", {})
        # Remove description keys
        RESISTANCE_SYNONYMS = {k: v for k, v in RESISTANCE_SYNONYMS.items()
                                if not k.startswith("_") and isinstance(v, list)}

        # Load implicit context config
        IMPLICIT_CONTEXT = kb.get("implicit_context", {})

        print(
            f"[STARTUP] Knowledge base loaded:"
            f" person_aliases={len(PERSON_ALIASES)},"
            f" topic_synonyms={len(TOPIC_SYNONYMS)},"
            f" dynasty_aliases={len(DYNASTY_ALIASES)},"
            f" abbreviations={len(ABBREVIATIONS)},"
            f" typo_fixes={len(TYPO_FIXES)},"
            f" resistance_synonyms={len(RESISTANCE_SYNONYMS)}",
            flush=True
        )

    except Exception as e:
        print(f"[ERROR] Failed to load knowledge base: {e}", flush=True)


def _build_historical_phrases():
    """
    Auto-generate HISTORICAL_PHRASES from knowledge_base entities.
    These are multi-word phrases that should NOT be split during keyword extraction.
    Replaces hardcoded HISTORICAL_PHRASES list in search_service.py.
    """
    global HISTORICAL_PHRASES
    phrases = set()

    # Collect all multi-word names from person aliases
    for name in PERSON_ALIASES:
        if " " in name:
            phrases.add(name)

    # Collect all multi-word topics/synonyms
    for name in TOPIC_SYNONYMS:
        if " " in name:
            phrases.add(name)

    # Collect all multi-word dynasty aliases
    for name in DYNASTY_ALIASES:
        if " " in name:
            phrases.add(name)

    # Collect all multi-word places from index
    for place in PLACES_INDEX:
        if " " in place:
            phrases.add(place)

    # Common historical action phrases (linguistic, not data)
    _action_phrases = [
        "khởi nghĩa", "chiến thắng", "chiến dịch", "cách mạng",
        "độc lập", "thống nhất", "giải phóng", "kháng chiến",
        "phong trào", "cần vương",
    ]
    phrases.update(_action_phrases)

    HISTORICAL_PHRASES = phrases
    print(f"[STARTUP] Historical phrases auto-generated: {len(HISTORICAL_PHRASES)}", flush=True)


def _load_cross_encoder():
    """
    Load Cross-Encoder ONNX model for reranking (optional).
    If model file doesn't exist, system falls back to keyword scoring.
    """
    global cross_encoder_session, cross_encoder_tokenizer

    if not os.path.exists(CROSS_ENCODER_MODEL_PATH):
        print(
            f"[STARTUP] Cross-Encoder ONNX not found at {CROSS_ENCODER_MODEL_PATH}"
            f" — using keyword fallback scoring",
            flush=True,
        )
        return

    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        print(f"[STARTUP] Loading Cross-Encoder ONNX from {CROSS_ENCODER_MODEL_PATH}...", flush=True)

        # Load tokenizer
        cross_encoder_tokenizer = AutoTokenizer.from_pretrained(CROSS_ENCODER_TOKENIZER_PATH)

        # Load ONNX session (same optimization as bi-encoder)
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 1
        sess_options.inter_op_num_threads = 1
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        cross_encoder_session = ort.InferenceSession(
            CROSS_ENCODER_MODEL_PATH, sess_options
        )

        print("[STARTUP] Cross-Encoder ONNX loaded ✅", flush=True)
        gc.collect()

    except Exception as e:
        print(f"[WARN] Failed to load Cross-Encoder ONNX: {e}", flush=True)
        print("[WARN] System will use keyword fallback scoring", flush=True)
        cross_encoder_session = None
        cross_encoder_tokenizer = None


def _load_nli_model():
    """
    Load NLI ONNX model for answer validation (optional).
    If model file doesn't exist, system skips NLI validation.
    """
    global nli_session, nli_tokenizer

    if not os.path.exists(NLI_MODEL_PATH):
        print(
            f"[STARTUP] NLI ONNX not found at {NLI_MODEL_PATH}"
            f" — NLI validation disabled",
            flush=True,
        )
        return

    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        print(f"[STARTUP] Loading NLI ONNX from {NLI_MODEL_PATH}...", flush=True)

        nli_tokenizer = AutoTokenizer.from_pretrained(NLI_TOKENIZER_PATH)

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 1
        sess_options.inter_op_num_threads = 1
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        nli_session = ort.InferenceSession(NLI_MODEL_PATH, sess_options)

        print("[STARTUP] NLI ONNX loaded ✅", flush=True)
        gc.collect()

    except Exception as e:
        print(f"[WARN] Failed to load NLI ONNX: {e}", flush=True)
        print("[WARN] NLI answer validation disabled", flush=True)
        nli_session = None
        nli_tokenizer = None
