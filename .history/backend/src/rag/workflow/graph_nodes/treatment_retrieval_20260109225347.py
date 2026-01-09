"""
Treatment Retrieval Node
Retrieves treatment guidance by disease keyword from Milvus
Uses cosine similarity search with exact disease-to-title mapping
"""
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Set
from functools import lru_cache

from pymilvus import Collection, connections

from ..state import KGState
from src.rag.config import rag_settings
from src.rag.vectors.embeddings import encode_e5

logger = logging.getLogger(__name__)

# Cache mapping file in memory
_TREATMENT_MAPPING_CACHE = None


def _load_treatment_mapping_sync() -> Dict[str, List[str]]:
    """
    Synchronous function to load disease-to-treatment-title mapping from JSON file.
    Used with asyncio.to_thread() for async context.
    
    Returns:
        Dict mapping disease names to list of treatment titles
    """
    global _TREATMENT_MAPPING_CACHE
    
    if _TREATMENT_MAPPING_CACHE is not None:
        return _TREATMENT_MAPPING_CACHE
    
    mapping_path = Path("data/raw/treatment_mapping.json")
    try:
        with mapping_path.open("r", encoding="utf-8") as f:
            _TREATMENT_MAPPING_CACHE = json.load(f)
            logger.info(f"✅ Loaded treatment mapping: {len(_TREATMENT_MAPPING_CACHE)} diseases")
            return _TREATMENT_MAPPING_CACHE
    except Exception as e:
        logger.error(f"❌ Failed to load treatment mapping: {e}")
        return {}


async def load_treatment_mapping() -> Dict[str, List[str]]:
    """
    Load disease-to-treatment-title mapping from JSON file (async wrapper).
    
    Returns:
        Dict mapping disease names to list of treatment titles
    """
    return await asyncio.to_thread(_load_treatment_mapping_sync)


def normalize_disease_name(name: str) -> str:
    """
    Normalize disease name for better matching.
    - Convert to lowercase
    - Remove extra spaces
    - Handle common variations (singular/plural, with/without hyphens)
    """
    normalized = name.lower().strip()
    # Remove common suffixes/prefixes for core matching
    normalized = normalized.replace('-related', '').replace(' related', '')
    return normalized


def find_treatment_titles(disease_name: str, mapping: Dict[str, List[str]]) -> List[str]:
    """
    Find treatment titles for a given disease using fuzzy matching.
    
    Strategy:
    1. Abbreviation expansion (PTSD → Posttraumatic Stress Disorder)
    2. Exact match (case-insensitive)
    3. Singular/Plural variants (disorder vs disorders)
    4. Partial match (disease name contains mapping key or vice versa)
    5. Core keyword match (main disorder terms)
    
    Args:
        disease_name: Detected disease name (e.g., "Depressive Disorder")
        mapping: Disease-to-titles mapping dict
    
    Returns:
        List of treatment titles for the disease
    """
    # Abbreviation mapping
    ABBREVIATIONS = {
        "ptsd": "Posttraumatic Stress Disorder",
        "ocd": "Obsessive-Compulsive Disorder",
        "adhd": "Attention-Deficit/Hyperactivity Disorder",
        "gad": "Generalized Anxiety Disorder",
        "sad": "Social Anxiety Disorder",
        "mdd": "Major Depressive Disorder",
        "bpd": "Borderline Personality Disorder",
        "aspd": "Antisocial Personality Disorder",
    }
    
    disease_lower = normalize_disease_name(disease_name)
    
    # Handle abbreviations
    if disease_lower in ABBREVIATIONS:
        expanded = ABBREVIATIONS[disease_lower]
        logger.info(f"🔤 Abbreviation expansion: '{disease_name}' → '{expanded}'")
        disease_name = expanded
        disease_lower = normalize_disease_name(expanded)
    
    # Try exact match first
    for key in mapping.keys():
        key_normalized = normalize_disease_name(key)
        if key_normalized == disease_lower:
            logger.info(f"📋 Exact match: '{disease_name}' → '{key}' → {len(mapping[key])} titles")
            return mapping[key]
    
    # Try singular/plural variants
    # "Depressive Disorder" should match "Depressive Disorders"
    # "Anxiety Disorders" should match "Anxiety Disorder"
    disease_singular = disease_lower.rstrip('s') if disease_lower.endswith('disorders') else disease_lower
    disease_plural = disease_lower + 's' if not disease_lower.endswith('s') else disease_lower
    
    for key in mapping.keys():
        key_normalized = normalize_disease_name(key)
        key_singular = key_normalized.rstrip('s') if key_normalized.endswith('disorders') else key_normalized
        
        # Check singular match
        if disease_singular == key_singular or disease_singular == key_normalized or disease_lower == key_singular:
            logger.info(f"📋 Singular/Plural match: '{disease_name}' → '{key}' → {len(mapping[key])} titles")
            return mapping[key]
    
    # Try partial match (contains) - more lenient
    for key in mapping.keys():
        key_normalized = normalize_disease_name(key)
        
        # Check if disease name contains mapping key (or vice versa)
        # "Major Depressive Disorder" contains "Depressive Disorder"
        if key_normalized in disease_lower or disease_lower in key_normalized:
            logger.info(f"📋 Partial match: '{disease_name}' → '{key}' → {len(mapping[key])} titles")
            return mapping[key]
        
        # Also check with singular forms
        key_singular = key_normalized.rstrip('s') if key_normalized.endswith('disorders') else key_normalized
        disease_singular = disease_lower.rstrip('s') if disease_lower.endswith('disorders') else disease_lower
        
        if key_singular in disease_singular or disease_singular in key_singular:
            logger.info(f"📋 Partial (singular) match: '{disease_name}' → '{key}' → {len(mapping[key])} titles")
            return mapping[key]
    
    # Try keyword-based matching (check main disorder words)
    # Extract key disorder terms
    disorder_keywords = {
        'depression', 'depressive', 'anxiety', 'panic', 'ptsd', 'ocd', 
        'bipolar', 'schizophrenia', 'psychotic', 'eating', 'substance',
        'autism', 'adhd', 'personality', 'trauma', 'stress', 'phobia',
        'obsessive', 'compulsive', 'dissociative', 'somatic', 'sleep'
    }
    
    disease_words = set(disease_lower.replace('-', ' ').replace('/', ' ').split())
    matching_keywords = disease_words & disorder_keywords
    
    if matching_keywords:
        for key in mapping.keys():
            key_words = set(key.lower().replace('-', ' ').replace('/', ' ').split())
            key_keywords = key_words & disorder_keywords
            
            # Need at least one common disorder keyword
            if matching_keywords & key_keywords:
                logger.info(f"📋 Keyword match: '{disease_name}' → '{key}' (keywords: {matching_keywords & key_keywords}) → {len(mapping[key])} titles")
                return mapping[key]
    
    logger.warning(f"⚠️ No mapping found for disease: '{disease_name}'")
    logger.debug(f"   Tried variants: '{disease_lower}', singular: '{disease_singular}', plural: '{disease_plural}'")
    return []


async def treatment_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve treatment chunks using vector search + exact title mapping.
    
    NEW LOGIC:
    1. Load disease-to-treatment-title mapping from JSON
    2. Map detected diseases → treatment titles (exact match)
    3. Build Milvus filter: disease in [title1, title2, ...]
    4. Vector search with exact filter
    5. Load full text from JSONL
    
    IMPROVEMENTS:
    - Exact matching instead of fuzzy LIKE
    - Multi-disease support (retrieve for all detected diseases)
    - Dynamic limit based on number of titles
    - Better error handling
    
    Args:
        state: KGState with detected_disease or disease_detected list
    
    Returns:
        Updated state with treatment_chunks, treatment_node_ids
    """
    # Get disease from state - prioritize disease_detected list
    disease_list = state.get("disease_detected", [])
    if not disease_list:
        # Fallback to detected_disease
        detected_disease = state.get("detected_disease", "")
        disease_list = [detected_disease] if detected_disease else []
    
    if not disease_list:
        logger.warning("⚠️ No disease detected for treatment retrieval")
        state["treatment_chunks"] = []
        state["treatment_node_ids"] = []
        return state
    
    logger.info(f"💊 Retrieving treatment guidance for {len(disease_list)} disease(s): {disease_list}")
    
    try:
        # Load treatment mapping (async)
        mapping = await load_treatment_mapping()
        if not mapping:
            logger.error("❌ Treatment mapping is empty, cannot retrieve")
            state["treatment_chunks"] = []
            state["treatment_node_ids"] = []
            return state
        
        # Collect all treatment titles for all detected diseases
        all_treatment_titles: Set[str] = set()
        disease_title_map: Dict[str, List[str]] = {}  # Track which titles come from which disease
        
        for disease in disease_list:
            titles = find_treatment_titles(disease, mapping)
            if titles:
                all_treatment_titles.update(titles)
                disease_title_map[disease] = titles
                logger.info(f"   '{disease}' → {len(titles)} treatment titles")
            else:
                logger.warning(f"   '{disease}' → No treatment titles found")
        
        if not all_treatment_titles:
            logger.warning(f"⚠️ No treatment titles found for any disease: {disease_list}")
            state["treatment_chunks"] = []
            state["treatment_node_ids"] = []
            return state
        
        logger.info(f"📚 Total unique treatment titles: {len(all_treatment_titles)}")
        
        # Get rewritten query for embedding
        query = state.get("rewritten_query", state.get("question", f"Cách điều trị {disease_list[0]}"))
        
        # Encode query to vector
        encoded_query = encode_e5([f"query: {query}"])
        query_vector = encoded_query[0].tolist()
        
        # Connect to Milvus
        connections.connect(
            alias="default",
            host=rag_settings.MILVUS_HOST,
            port=rag_settings.MILVUS_PORT
        )
        
        # Get collection and load
        col = Collection("mental_health_treatment_guidance")
        col.load()
        
        # Build EXACT filter expression using IN operator
        # Escape quotes in titles
        escaped_titles = [title.replace('"', '\\"').replace("'", "\\'") for title in all_treatment_titles]
        
        # For Milvus IN expression, need to format as: disease in ["title1", "title2", ...]
        # NOTE: Field name is "disease" in Milvus (stores treatment titles)
        title_list_str = ", ".join([f'"{title}"' for title in escaped_titles])
        expr = f'disease in [{title_list_str}]'
        
        logger.info(f"🔍 Milvus filter: {len(escaped_titles)} exact titles")
        logger.debug(f"   First 3 titles: {list(all_treatment_titles)[:3]}")
        
        # Dynamic limit based on number of titles
        # More titles → retrieve more chunks to cover all treatment aspects
        limit = min(15, max(5, len(all_treatment_titles) * 2))
        logger.info(f"   Retrieval limit: {limit} chunks")
        
        # Vector search with exact title filter
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 64}
        }
        
        results = col.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            expr=expr,  # Exact IN filter on "disease" field
            output_fields=["node_id", "disease"]
        )
        
        # Extract results
        hits = results[0] if results else []
        logger.info(f"✅ Found {len(hits)} treatment records with exact title matching")
        
        if not hits:
            logger.warning(f"⚠️ No treatment records found for titles: {list(all_treatment_titles)[:5]}...")
            state["treatment_chunks"] = []
            state["treatment_node_ids"] = []
            return state
        
        # Log which titles were retrieved
        retrieved_titles = set()
        for hit in hits:
            title = hit.entity.get("disease", "")  # Field name is "disease" in Milvus
            if title:
                retrieved_titles.add(title)
        logger.info(f"📊 Retrieved from {len(retrieved_titles)} unique titles:")
        for title in list(retrieved_titles)[:5]:
            logger.info(f"   • {title}")
        
        # Load full text from JSONL file
        treatment_chunks = []
        treatment_node_ids = []
        
        file_path = Path("data/raw/mental_health_treatment_guidance.jsonl")
        if file_path.exists():
            node_id_set = {hit.entity.get("node_id") for hit in hits}
            
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        chunk_id = int(item.get("chunk_id", -1))
                        if chunk_id in node_id_set:
                            text = item.get("text", "").strip()
                            title = item.get("title", "")
                            if text:
                                # Add title prefix for clarity
                                treatment_chunks.append(f"[Treatment: {title}]\n{text}")
                                treatment_node_ids.append(chunk_id)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse line in treatment file: {e}")
                        continue
        else:
            logger.error(f"❌ Treatment guidance file not found: {file_path}")
        
        logger.info(f"✅ Loaded {len(treatment_chunks)} treatment texts")
        
        # Store additional metadata for answer generation
        state["treatment_chunks"] = treatment_chunks
        state["treatment_node_ids"] = treatment_node_ids
        state["treatment_titles_used"] = list(retrieved_titles)  # Track which titles were used
        
    except Exception as e:
        logger.error(f"❌ Error in treatment retrieval: {e}", exc_info=True)
        state["treatment_chunks"] = []
        state["treatment_node_ids"] = []
    
    return state
