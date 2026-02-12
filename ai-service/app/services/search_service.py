import app.core.startup as startup
from app.core.config import TOP_K, SIM_THRESHOLD, SIM_THRESHOLD_LOW, FUZZY_MATCH_THRESHOLD, HIGH_CONFIDENCE_SCORE
from functools import lru_cache
from app.utils.normalize import normalize_query
from app.services.query_understanding import (
    fuzzy_match_entity,
    generate_phonetic_variants,
    generate_search_variations,
)
import re
from unicodedata import normalize as unicode_normalize
import unicodedata

# NOTE: Moved heavy imports (faiss, numpy) to function scope to improve startup time.
# import faiss
import numpy as np


def _strip_accents_light(text: str) -> str:
    """Strip Vietnamese diacritical marks for fuzzy comparison."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

# ===================================================================
# DYNAMIC ENTITY RESOLUTION (Data-Driven)
# Uses inverted indexes + knowledge_base.json loaded at startup.
# No hardcoded patterns — scales automatically with data.
# ===================================================================

# NOTE: HISTORICAL_PHRASES is auto-generated at startup from knowledge_base.json.
# Access via startup.HISTORICAL_PHRASES (set of multi-word phrases).
# No hardcoded list needed — adding entries to knowledge_base.json is sufficient.


def _normalize_query_text(text: str) -> str:
    """Lowercase + NFC normalize for consistent matching."""
    return unicode_normalize("NFC", text.lower().strip())


def resolve_query_entities(query: str) -> dict:
    """
    Dynamically resolve persons, dynasties, topics, and places from query
    using inverted indexes and aliases loaded at startup.

    Returns: {
        "persons": [canonical_name, ...],
        "dynasties": [canonical_dynasty, ...],
        "topics": [canonical_topic, ...],
        "places": [place_name, ...],
    }
    """
    q_low = _normalize_query_text(query)
    result = {"persons": [], "dynasties": [], "topics": [], "places": []}
    seen_persons = set()
    seen_dynasties = set()
    seen_topics = set()
    seen_places = set()

    # --- 1. Resolve persons via knowledge_base aliases ---
    for alias, canonical in startup.PERSON_ALIASES.items():
        if alias in q_low and canonical not in seen_persons:
            seen_persons.add(canonical)
            result["persons"].append(canonical)

    # --- 2. Direct person match from inverted index ---
    for person_key in startup.PERSONS_INDEX:
        if person_key in q_low and person_key not in seen_persons:
            seen_persons.add(person_key)
            result["persons"].append(person_key)

    # --- 3. Resolve dynasties via aliases ---
    for alias, canonical in startup.DYNASTY_ALIASES.items():
        if alias in q_low and canonical not in seen_dynasties:
            seen_dynasties.add(canonical)
            result["dynasties"].append(canonical)

    # --- 4. Direct dynasty match from inverted index ---
    for dynasty_key in startup.DYNASTY_INDEX:
        if dynasty_key in q_low and dynasty_key not in seen_dynasties:
            # GUARD: Prevent false match when short dynasty name is part of
            # a person name. e.g., "nguyễn" in "nguyễn huệ" ≠ dynasty "nguyễn"
            is_part_of_person = any(
                dynasty_key in person for person in result["persons"]
            )
            if is_part_of_person:
                continue
            seen_dynasties.add(dynasty_key)
            result["dynasties"].append(dynasty_key)

    # --- 5. Resolve topics via synonyms ---
    for synonym, canonical in startup.TOPIC_SYNONYMS.items():
        if synonym in q_low and canonical not in seen_topics:
            # GUARD: If synonym is a person name already matched, skip topic match
            # e.g., "nguyễn huệ" matches person → don't also match topic "tây sơn"
            is_person_synonym = any(synonym in person for person in result["persons"])
            if is_person_synonym:
                continue
            seen_topics.add(canonical)
            result["topics"].append(canonical)

    # --- 6. Direct place match from inverted index ---
    for place_key in startup.PLACES_INDEX:
        if place_key in q_low and place_key not in seen_places:
            seen_places.add(place_key)
            result["places"].append(place_key)

    # --- 7. HYBRID FUZZY MATCHING (Always-on, supplements Exact Match) ---
    # Run fuzzy match IN PARALLEL with exact match to catch typos/variants.
    # High-confidence fuzzy matches (>= 0.85) are always added.
    # Lower-confidence (>= threshold) only added when no exact results for that entity type.
    
    # Fuzzy match against person aliases
    fuzzy_persons = fuzzy_match_entity(q_low, startup.PERSON_ALIASES, FUZZY_MATCH_THRESHOLD)
    for matched_key, _score in fuzzy_persons:
        canonical = startup.PERSON_ALIASES.get(matched_key, matched_key)
        if canonical not in seen_persons:
            # High confidence: always add. Low confidence: only if no exact matches
            if _score >= 0.85 or not result["persons"]:
                seen_persons.add(canonical)
                result["persons"].append(canonical)

    # Fuzzy match against dynasty aliases
    fuzzy_dynasties = fuzzy_match_entity(q_low, startup.DYNASTY_ALIASES, 0.80)
    for matched_key, _score in fuzzy_dynasties:
        canonical = startup.DYNASTY_ALIASES.get(matched_key, matched_key)
        if canonical not in seen_dynasties:
            # GUARD: Skip if fuzzy-matched dynasty is part of a resolved person name
            # e.g., "nguyễn" dynasty should NOT match when "nguyễn huệ" is a person
            is_part_of_person = any(
                canonical in person or matched_key in person
                for person in result["persons"]
            )
            if is_part_of_person:
                continue
            # GUARD: Skip if fuzzy-matched key is very similar to a resolved topic
            # Use BOTH accented and stripped comparison since Vietnamese accents
            # can differ between similar words: "nguyễn" vs "nguyên" → both strip to "nguyen"
            matched_stripped = _strip_accents_light(matched_key)
            is_similar_to_topic = any(
                matched_key in topic or topic in matched_key or
                matched_stripped in _strip_accents_light(topic)
                for topic in result["topics"]
            )
            if is_similar_to_topic:
                continue
            if _score >= 0.85 or not result["dynasties"]:
                seen_dynasties.add(canonical)
                result["dynasties"].append(canonical)

    # Fuzzy match against topic synonyms
    fuzzy_topics = fuzzy_match_entity(q_low, startup.TOPIC_SYNONYMS, FUZZY_MATCH_THRESHOLD)
    for matched_key, _score in fuzzy_topics:
        canonical = startup.TOPIC_SYNONYMS.get(matched_key, matched_key)
        if canonical not in seen_topics:
            if _score >= 0.85 or not result["topics"]:
                seen_topics.add(canonical)
                result["topics"].append(canonical)

    # --- 8. PHONETIC VARIANT FALLBACK ---
    # When both exact and fuzzy match find nothing, try phonetic variants
    if not any(result.values()):
        phonetic_variants = generate_phonetic_variants(q_low)
        for variant in phonetic_variants[:3]:  # Limit to avoid over-expansion
            variant_result = {"persons": [], "dynasties": [], "topics": [], "places": []}
            # Try exact match with phonetic variant
            for alias, canonical in startup.PERSON_ALIASES.items():
                if alias in variant and canonical not in seen_persons:
                    seen_persons.add(canonical)
                    result["persons"].append(canonical)
            for alias, canonical in startup.DYNASTY_ALIASES.items():
                if alias in variant and canonical not in seen_dynasties:
                    seen_dynasties.add(canonical)
                    result["dynasties"].append(canonical)
            for synonym, canonical in startup.TOPIC_SYNONYMS.items():
                if synonym in variant and canonical not in seen_topics:
                    seen_topics.add(canonical)
                    result["topics"].append(canonical)
            for place_key in startup.PLACES_INDEX:
                if place_key in variant and place_key not in seen_places:
                    seen_places.add(place_key)
                    result["places"].append(place_key)
            # If phonetic variant found something, stop trying more variants
            if any(result.values()):
                break

    return result


def scan_by_entities(resolved: dict, max_results: int = 50) -> list:
    """
    Scan documents using inverted indexes — O(1) lookup per entity.
    Falls back to text-based scan when index is empty for a resolved entity.
    Returns deduplicated list of matching documents.
    """
    doc_indices = set()
    unmatched_persons = []  # Persons not found in inverted index
    unmatched_topics = []   # Topics not found in inverted index

    for person in resolved.get("persons", []):
        idx_hits = startup.PERSONS_INDEX.get(person, [])
        if idx_hits:
            doc_indices.update(idx_hits)
        else:
            unmatched_persons.append(person)

    for dynasty in resolved.get("dynasties", []):
        doc_indices.update(startup.DYNASTY_INDEX.get(dynasty, []))

    for topic in resolved.get("topics", []):
        # Topic synonyms map to canonical topics; search both keyword and text index
        hits = startup.KEYWORD_INDEX.get(topic, [])
        topic_underscored = topic.replace(" ", "_")
        hits_us = startup.KEYWORD_INDEX.get(topic_underscored, [])
        if hits or hits_us:
            doc_indices.update(hits)
            doc_indices.update(hits_us)
        else:
            unmatched_topics.append(topic)

    for place in resolved.get("places", []):
        doc_indices.update(startup.PLACES_INDEX.get(place, []))

    # --- TEXT-BASED FALLBACK ---
    # When inverted index has no entries, scan DOCUMENTS text fields directly.
    # This handles cases where pipeline didn't extract entities into metadata.
    # PRIORITY: match in metadata fields (persons, keywords) > match in story text
    if unmatched_persons or unmatched_topics:
        # Build search terms: include all aliases for each person
        search_terms_persons = set()
        for person in unmatched_persons:
            search_terms_persons.add(person)
            for alias, canonical in startup.PERSON_ALIASES.items():
                if canonical == person and alias != person:
                    search_terms_persons.add(alias)
        search_terms_topics = set()
        for topic in unmatched_topics:
            search_terms_topics.add(topic)
            for syn, canonical in startup.TOPIC_SYNONYMS.items():
                if canonical == topic and syn != topic:
                    search_terms_topics.add(syn)

        # Phase 1: Match against metadata fields (high confidence)
        metadata_matches = set()
        for idx, doc in enumerate(startup.DOCUMENTS):
            if idx in doc_indices:
                continue
            doc_persons_lower = [p.lower() for p in doc.get("persons", [])]
            doc_keywords_lower = [k.lower() for k in doc.get("keywords", [])]
            persons_meta = " ".join(doc_persons_lower)
            keywords_meta = " ".join(doc_keywords_lower)
            if any(t in persons_meta for t in search_terms_persons):
                metadata_matches.add(idx)
            elif any(t in keywords_meta for t in search_terms_topics):
                metadata_matches.add(idx)
        
        doc_indices.update(metadata_matches)

        # Phase 2: Only fall back to story text if Phase 1 found nothing
        # Story text matching is noisier (mentions ≠ relevance)
        if not metadata_matches:
            story_matches = set()
            all_terms = search_terms_persons | search_terms_topics
            for idx, doc in enumerate(startup.DOCUMENTS):
                if idx in doc_indices:
                    continue
                doc_text = " ".join([
                    str(doc.get("story", "")),
                    str(doc.get("event", "")),
                    str(doc.get("title", "")),
                ]).lower()
                if any(term in doc_text for term in all_terms):
                    story_matches.add(idx)
                if len(story_matches) >= max_results:
                    break
            doc_indices.update(story_matches)

    # Return actual documents, capped at max_results
    docs = []
    for i in sorted(doc_indices):
        if i < len(startup.DOCUMENTS):
            docs.append(startup.DOCUMENTS[i])
        if len(docs) >= max_results:
            break
    return docs


# ===================================================================
# BACKWARD-COMPATIBLE WRAPPERS
# These wrap resolve_query_entities() for engine.py compatibility.
# ===================================================================

def detect_dynasty_from_query(query: str) -> str | None:
    """
    Detect if the query is asking about a specific dynasty.
    Uses dynamic aliases from knowledge_base.json.
    Returns dynasty name or None.
    """
    resolved = resolve_query_entities(query)
    dynasties = resolved.get("dynasties", [])
    return dynasties[0] if dynasties else None


def detect_place_from_query(query: str) -> str | None:
    """
    Detect if the query mentions a historical place.
    Uses dynamic places index from DOCUMENTS.
    Returns place name or None.
    """
    resolved = resolve_query_entities(query)
    places = resolved.get("places", [])
    return places[0] if places else None


# ===================================================================
# KEYWORD EXTRACTION (improved for Vietnamese history)
# ===================================================================

def extract_important_keywords(text: str) -> set:
    """
    Extract important keywords from query for relevance filtering.
    Handles multi-word phrases and avoids filtering out historical terms.
    """
    if not text:
        return set()
    
    # Common words to ignore — ONLY truly generic words
    # DO NOT include historical terms like triều, đại, chiến, etc.
    stop_words = {
        "là", "gì", "như", "thế", "nào", "có", "của", "và", "trong", "được",
        "với", "cho", "tôi", "về", "hãy", "kể", "biết",  "hỏi",
        "những", "các", "một", "này", "đó", "từ", "đến", "hay", "hoặc",
        "bạn", "mình", "xin", "vui", "lòng", "giúp", "tìm",
        "hiểu", "muốn", "cần", "thêm",
    }
    
    q_low = text.lower()
    extracted = set()
    
    # Step 1: Extract multi-word phrases first
    for phrase in startup.HISTORICAL_PHRASES:
        if phrase in q_low:
            # Add as underscore-joined keyword for matching
            extracted.add(phrase.replace(" ", "_"))
            # Also add individual significant words
            for word in phrase.split():
                if len(word) > 2 and word not in stop_words:
                    extracted.add(word)
    
    # Step 2: Extract remaining single words
    normalized = re.sub(r'[^\w\s]', ' ', q_low)
    words = normalized.split()
    for w in words:
        if len(w) > 2 and w not in stop_words:
            extracted.add(w)
    
    return extracted


def check_query_relevance(query: str, doc: dict, dynasty_filter: str = None) -> bool:
    """
    Check if a document is actually relevant to the query.
    Uses keyword matching AND dynasty filtering.
    Alias-aware: expands person aliases for better matching.
    """
    # If dynasty filter is active, check dynasty first
    if dynasty_filter:
        doc_dynasty = doc.get("dynasty", "")
        # Allow partial matches: "Lê" matches "Lê sơ", "Lê trung hưng"
        if dynasty_filter.lower() in doc_dynasty.lower():
            return True  # Dynasty match = always relevant
    
    query_keywords = extract_important_keywords(query)
    
    if not query_keywords:
        return True  # No specific keywords, accept all
    
    # Build document text for matching (include ALL metadata fields)
    doc_parts = [
        str(doc.get("title", "")),
        str(doc.get("event", "")),
        str(doc.get("story", "")),
        " ".join(doc.get("persons", [])),
        " ".join(doc.get("places", [])),
        " ".join(doc.get("keywords", [])),
        str(doc.get("dynasty", "")),
        str(doc.get("period", "")),
    ]
    doc_text = " ".join(doc_parts).lower()
    
    # Expand query keywords with person aliases for better matching
    # e.g., "quang_trung" → also check "nguyễn_huệ"
    expanded_keywords = set(query_keywords)
    for kw in query_keywords:
        kw_clean = kw.replace("_", " ")
        # Check if keyword is a person alias → add canonical name
        canonical = startup.PERSON_ALIASES.get(kw_clean)
        if canonical and canonical != kw_clean:
            expanded_keywords.add(canonical.replace(" ", "_"))
            expanded_keywords.add(canonical)  # Also without underscore
        # Check reverse: if keyword is canonical → add aliases
        for alias, canon in startup.PERSON_ALIASES.items():
            if canon == kw_clean and alias != kw_clean:
                expanded_keywords.add(alias.replace(" ", "_"))
                expanded_keywords.add(alias)
    
    # Check keyword matching with expanded set
    matching_keywords = sum(1 for kw in expanded_keywords if kw in doc_text)
    
    # More lenient threshold: always require at least 1 match
    # Only raise to 2 for very keyword-rich queries (5+)
    min_matches = 2 if len(query_keywords) >= 5 else 1
    return matching_keywords >= min_matches


# ===================================================================
# EMBEDDING + SEARCH
# ===================================================================

@lru_cache(maxsize=1024)
def get_cached_embedding(query: str):
    """
    Encodes and normalizes a query, caching the result to speed up repeated searches.
    Uses ONNX Runtime + Transformers Tokenizer.
    """
    if startup.session is None or startup.tokenizer is None:
        raise RuntimeError("ONNX model is not loaded")

    # 1. Tokenize (return numpy arrays)
    inputs = startup.tokenizer(
        query, 
        return_tensors="np", 
        padding=True, 
        truncation=True, 
        max_length=512
    )
    
    # 2. Prepare Inputs (ONNX expects int64)
    model_inputs = {
        "input_ids": inputs["input_ids"].astype(np.int64),
        "attention_mask": inputs["attention_mask"].astype(np.int64)
    }
    
    # Check session inputs for token_type_ids
    input_names = [i.name for i in startup.session.get_inputs()]
    if "token_type_ids" in input_names and "token_type_ids" in inputs:
        model_inputs["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)

    # 3. Inference
    outputs = startup.session.run(None, model_inputs)
    
    # 4. Pooling (Mean Pooling)
    last_hidden_state = outputs[0]
    
    input_mask_expanded = model_inputs["attention_mask"][:, :, None].astype(last_hidden_state.dtype)
    sum_embeddings = np.sum(last_hidden_state * input_mask_expanded, axis=1)
    sum_mask = np.sum(input_mask_expanded, axis=1)
    sum_mask = np.maximum(sum_mask, 1e-9)
    embedding = sum_embeddings / sum_mask
    
    # 5. Normalize (L2)
    norm = np.linalg.norm(embedding, axis=1, keepdims=True)
    embedding = embedding / norm
    
    # Flatten to [dimension]
    return embedding[0].astype("float32")


def semantic_search(query: str):
    """
    Perform semantic search with improved relevance filtering.
    Supports dynasty-aware filtering for broader historical queries.
    Uses multi-query strategy for better recall.
    """
    if startup.index is None:
        print("[WARN] Search called before index is ready")
        return []

    if startup.session is None:
        print("[WARN] Search called before ONNX session is ready")
        return []

    # Detect dynasty and place filters from query
    dynasty_filter = detect_dynasty_from_query(query)
    place_filter = detect_place_from_query(query)

    # Normalize query before searching/caching to increase hit rate
    try:
        norm_q = normalize_query(query)
        emb = get_cached_embedding(norm_q)

        # FAISS requires 2D input: (n_queries, dim)
        emb_2d = np.expand_dims(emb, axis=0)

        # Search wider for dynasty/place queries
        search_k = min(TOP_K * 3, 50) if (dynasty_filter or place_filter) else min(TOP_K * 2, 30)
        scores, ids = startup.index.search(emb_2d, search_k)

        # Use configured threshold — lowered to catch broader queries
        threshold = SIM_THRESHOLD

        results = []
        
        # If we have a dynasty filter, also scan ALL documents for dynasty matches
        # (FAISS may miss them due to low semantic similarity)
        if dynasty_filter:
            for doc in startup.DOCUMENTS:
                doc_dynasty = doc.get("dynasty", "")
                if dynasty_filter.lower() in doc_dynasty.lower():
                    if doc not in results:
                        results.append(doc)
        
        # If we have a place filter, scan for place matches
        if place_filter:
            place_low = place_filter.lower()
            for doc in startup.DOCUMENTS:
                doc_text = " ".join([
                    str(doc.get("story", "")),
                    str(doc.get("event", "")),
                    " ".join(doc.get("places", [])),
                ]).lower()
                if place_low in doc_text and doc not in results:
                    results.append(doc)

        # Then add FAISS semantic results
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            
            # Score must meet threshold
            if score < threshold:
                continue
            
            # Use startup.DOCUMENTS
            if idx < len(startup.DOCUMENTS):
                doc = startup.DOCUMENTS[idx]
                
                # High-confidence results bypass keyword check
                if score >= HIGH_CONFIDENCE_SCORE:
                    if doc not in results:
                        results.append(doc)
                elif check_query_relevance(query, doc, dynasty_filter):
                    if doc not in results:
                        results.append(doc)
            
            # Limit results
            if len(results) >= TOP_K:
                break

        # --- MULTI-QUERY SEARCH (NEW) ---
        # When primary search yields few results, try query variations
        if len(results) < 3:
            resolved = resolve_query_entities(query)
            variations = generate_search_variations(query, resolved)
            for var_query in variations[:4]:  # Max 4 variations
                try:
                    var_norm = normalize_query(var_query)
                    var_emb = get_cached_embedding(var_norm)
                    var_emb_2d = np.expand_dims(var_emb, axis=0)
                    var_scores, var_ids = startup.index.search(var_emb_2d, TOP_K)
                    for v_score, v_idx in zip(var_scores[0], var_ids[0]):
                        if v_idx == -1 or v_score < threshold:
                            continue
                        if v_idx < len(startup.DOCUMENTS):
                            doc = startup.DOCUMENTS[v_idx]
                            if doc not in results:
                                results.append(doc)
                    if len(results) >= TOP_K:
                        break
                except Exception:
                    continue  # Skip failed variations silently

        return results
    except Exception as e:
        print(f"[ERROR] Semantic search failed: {e}")
        return []


def scan_by_year(year: int):
    """
    Returns events for a specific year using an O(1) indexed lookup.
    """
    if startup.DOCUMENTS_BY_YEAR is None:
        return []
    return startup.DOCUMENTS_BY_YEAR.get(year, [])


def scan_by_year_range(start_year: int, end_year: int):
    """
    Returns events for a year range using indexed lookup.
    Scans all years from start_year to end_year (inclusive).
    """
    if startup.DOCUMENTS_BY_YEAR is None:
        return []
    results = []
    for year in range(start_year, end_year + 1):
        events = startup.DOCUMENTS_BY_YEAR.get(year, [])
        results.extend(events)
    return results

