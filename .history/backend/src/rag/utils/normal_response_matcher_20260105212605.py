"""
Normal Response Matcher - Load and Match from normal_responses.jsonl

This module loads the normal_responses.jsonl database and matches
symptoms/factors from user slots to calculate assessment scores.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Cache the database in memory
_NORMAL_RESPONSES_DB = None


def load_normal_responses_database() -> List[Dict[str, Any]]:
    """
    Load normal_responses.jsonl database into memory.
    
    Returns:
        List of dictionaries with keys: chunk_id, title, type, score, text
    """
    global _NORMAL_RESPONSES_DB
    
    if _NORMAL_RESPONSES_DB is not None:
        return _NORMAL_RESPONSES_DB
    
    # Path to normal_responses.jsonl
    base_dir = Path(__file__).parent.parent.parent.parent  # backend/
    jsonl_path = base_dir / "data" / "raw" / "normal_responses.jsonl"
    
    if not jsonl_path.exists():
        logger.error(f"[LOAD ERROR] normal_responses.jsonl not found at: {jsonl_path}")
        return []
    
    logger.info(f"[LOADING] Reading normal_responses.jsonl from: {jsonl_path}")
    
    database = []
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    database.append(item)
                except json.JSONDecodeError as e:
                    logger.warning(f"[PARSE ERROR] Line {line_num}: {e}")
        
        _NORMAL_RESPONSES_DB = database
        logger.info(f"[LOADED] {len(database)} items from normal_responses.jsonl")
        
    except Exception as e:
        logger.error(f"[LOAD ERROR] Failed to load normal_responses.jsonl: {e}", exc_info=True)
        return []
    
    return database


def match_symptoms_to_database(slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Match symptoms/factors from slots to normal_responses.jsonl database.
    
    This function searches for matches based on:
    - Primary symptoms (main complaint)
    - Secondary symptoms
    - Physical symptoms
    - Recent life events / triggers
    - Emotions
    
    IMPORTANT: Prioritize low-score items (stressors/life events) over high-score
    clinical symptoms to avoid over-pathologizing normal experiences.
    
    Args:
        slots: Dictionary containing extracted slot information
    
    Returns:
        List of matched items from database, each with: chunk_id, title, type, score, text
    """
    database = load_normal_responses_database()
    
    if not database:
        logger.warning("[MATCH] Database is empty, returning no matches")
        return []
    
    matched_items = []
    matched_ids = set()  # Prevent duplicates
    
    # Separate database into categories by score
    stressors = [item for item in database if item.get("score", 0) <= 0]  # Negative or 0
    behavioral_issues = [item for item in database if 1 <= item.get("score", 0) <= 4]
    clinical_symptoms = [item for item in database if item.get("score", 0) >= 5]
    
    logger.info(f"[DATABASE] {len(stressors)} stressors, {len(behavioral_issues)} behavioral, {len(clinical_symptoms)} clinical")
    
    # Extract searchable fields from slots
    search_terms = []
    
    # 1. Recent life events / triggers (HIGHEST PRIORITY - match with stressors first)
    recent_events = slots.get("recent_life_events", "")
    if recent_events:
        search_terms.insert(0, ("trigger", recent_events))  # Tag as trigger
    
    # 2. Primary symptoms (could be clinical or normal stress)
    primary_symptoms = slots.get("primary_symptoms", [])
    if isinstance(primary_symptoms, list):
        for symptom in primary_symptoms:
            search_terms.append(("symptom", symptom))
    elif isinstance(primary_symptoms, str) and primary_symptoms:
        search_terms.append(("symptom", primary_symptoms))
    
    # 3. Secondary symptoms
    secondary_symptoms = slots.get("secondary_symptoms", [])
    if isinstance(secondary_symptoms, list):
        for symptom in secondary_symptoms:
            search_terms.append(("symptom", symptom))
    elif isinstance(secondary_symptoms, str) and secondary_symptoms:
        search_terms.append(("symptom", secondary_symptoms))
    
    # 4. Physical symptoms
    physical_symptoms = slots.get("physical_symptoms", [])
    if isinstance(physical_symptoms, list):
        for symptom in physical_symptoms:
            search_terms.append(("physical", symptom))
    
    # 5. Emotions (be careful - could be normal or pathological)
    emotion = slots.get("emotion", "")
    if emotion:
        search_terms.append(("emotion", emotion))
    
    # 6. Daily functioning issues
    daily_functioning = slots.get("daily_functioning", "")
    if daily_functioning:
        search_terms.append(("functioning", daily_functioning))
    
    # 7. Work/school impact
    work_impact = slots.get("work_school_impact", "")
    if work_impact:
        search_terms.append(("work", work_impact))
    
    # 8. Social relationships
    social_relationships = slots.get("social_relationships", "")
    if social_relationships:
        search_terms.append(("social", social_relationships))
    
    logger.info(f"[MATCH] Searching for {len(search_terms)} terms in database")
    logger.debug(f"[SEARCH TERMS] {search_terms}")
    
    # Match with PRIORITY SYSTEM:
    # 1. First, match triggers/life events with stressors (score ≤ 0)
    # 2. Then, match symptoms cautiously
    
    for term_type, term in search_terms:
        if not term or not isinstance(term, str):
            continue
        
        term_lower = term.lower()
        
        # For triggers: Match with stressors ONLY
        if term_type == "trigger":
            for item in stressors:
                if item["chunk_id"] in matched_ids:
                    continue
                
                title_lower = item.get("title", "").lower()
                text_lower = item.get("text", "").lower()
                
                if term_lower in title_lower or term_lower in text_lower or _keyword_match(term_lower, title_lower):
                    matched_items.append(item)
                    matched_ids.add(item["chunk_id"])
                    logger.debug(f"[TRIGGER MATCH] '{term}' → '{item['title']}' (score={item['score']})")
        
        # For symptoms: Be more selective
        else:
            # First try to match with stressors and behavioral issues
            for item in stressors + behavioral_issues:
                if item["chunk_id"] in matched_ids:
                    continue
                
                title_lower = item.get("title", "").lower()
                text_lower = item.get("text", "").lower()
                
                if term_lower in title_lower or term_lower in text_lower:
                    matched_items.append(item)
                    matched_ids.add(item["chunk_id"])
                    logger.debug(f"[SYMPTOM MATCH] '{term}' → '{item['title']}' (score={item['score']})")
                    break  # Stop after first match to avoid over-matching
    
    # Additional matching: Check for common patterns
    _match_common_patterns(slots, database, matched_items, matched_ids)
    
    # IMPORTANT: Filter out high-score clinical symptoms if:
    # - Duration is very short (< 2 weeks)
    # - Clear trigger present
    duration = slots.get("duration", "")
    has_clear_trigger = bool(slots.get("recent_life_events", ""))
    
    if duration and has_clear_trigger:
        from .assessment import parse_duration_score
        D = parse_duration_score(duration)
        
        if D <= 1:  # Less than 1 month
            # Remove high clinical scores (≥5)
            filtered_items = []
            for item in matched_items:
                if item.get("score", 0) >= 5:
                    logger.info(f"[FILTER] Removed clinical symptom '{item['title']}' (score={item['score']}) due to short duration + clear trigger")
                else:
                    filtered_items.append(item)
            
            matched_items = filtered_items
    
    logger.info(f"[MATCH RESULT] Found {len(matched_items)} matched items after filtering")
    
    return matched_items


def _keyword_match(term: str, text: str) -> bool:
    """
    Check if term matches text using keyword patterns.
    """
    # Common trigger keywords
    trigger_patterns = {
        "thuyết trình": ["presentation", "speak", "talk"],
        "thi": ["exam", "test"],
        "deadline": ["deadline", "due date"],
        "chia tay": ["breakup", "separation"],
        "mất người thân": ["loss", "death", "bereavement"],
        "mất việc": ["job loss", "unemployment"],
    }
    
    for vietnamese_term, english_terms in trigger_patterns.items():
        if vietnamese_term in term:
            return any(eng in text for eng in english_terms)
    
    return False


def _match_common_patterns(slots: Dict[str, Any], database: List[Dict[str, Any]], 
                           matched_items: List[Dict[str, Any]], matched_ids: set):
    """
    Match common patterns that might not be explicitly mentioned in symptoms.
    """
    
    # Pattern 1: Stress-related keywords
    stress_keywords = ["stress", "áp lực", "lo lắng", "anxiety", "căng thẳng", "tension"]
    recent_events = str(slots.get("recent_life_events", "")).lower()
    emotion = str(slots.get("emotion", "")).lower()
    
    has_stress_indicators = any(kw in recent_events or kw in emotion for kw in stress_keywords)
    
    if has_stress_indicators:
        for item in database:
            if item["chunk_id"] in matched_ids:
                continue
            
            # Match stress-related items
            if "stress" in item["title"].lower() or item["chunk_id"] in ["QE01"]:
                matched_items.append(item)
                matched_ids.add(item["chunk_id"])
                logger.debug(f"[PATTERN MATCH] Stress pattern → '{item['title']}'")
    
    # Pattern 2: Relationship issues
    relationship_keywords = ["chia tay", "breakup", "cãi nhau", "conflict", "tranh cãi", "mất người thân", "loss"]
    
    has_relationship_issues = any(kw in recent_events for kw in relationship_keywords)
    
    if has_relationship_issues:
        for item in database:
            if item["chunk_id"] in matched_ids:
                continue
            
            # Match relationship-related items
            if "relationship" in item["title"].lower() or "family" in item["title"].lower():
                matched_items.append(item)
                matched_ids.add(item["chunk_id"])
                logger.debug(f"[PATTERN MATCH] Relationship pattern → '{item['title']}'")
    
    # Pattern 3: Bereavement / Loss
    loss_keywords = ["mất người thân", "qua đời", "death", "loss", "bereavement"]
    
    has_loss = any(kw in recent_events for kw in loss_keywords)
    
    if has_loss:
        for item in database:
            if item["chunk_id"] in matched_ids:
                continue
            
            if "bereavement" in item["title"].lower() or "death" in item["title"].lower() or item["chunk_id"] in ["QE61.0", "QE62"]:
                matched_items.append(item)
                matched_ids.add(item["chunk_id"])
                logger.debug(f"[PATTERN MATCH] Loss/bereavement pattern → '{item['title']}'")
    
    # Pattern 4: Work/School stress
    work_keywords = ["thi", "exam", "deadline", "thuyết trình", "presentation", "kiểm tra", "test", "project"]
    
    has_work_stress = any(kw in recent_events for kw in work_keywords)
    
    if has_work_stress:
        for item in database:
            if item["chunk_id"] in matched_ids:
                continue
            
            if "work" in item["title"].lower() or "school" in item["title"].lower() or item["chunk_id"] == "QE50.2":
                matched_items.append(item)
                matched_ids.add(item["chunk_id"])
                logger.debug(f"[PATTERN MATCH] Work/school pattern → '{item['title']}'")
