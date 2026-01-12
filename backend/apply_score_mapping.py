#!/usr/bin/env python3
"""
Script to apply score mapping to normal_responses.jsonl according to DATA_SCORE_ADJUSTMENT_PLAN.md
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mapping rules from DATA_SCORE_ADJUSTMENT_PLAN.md

# Adjustment Reaction: 5 → 3 (Generic Mood/Affect)
ADJUSTMENT_5_TO_3 = {
    "MB24.5",  # Depressed mood
    "MB24.3",  # Anxiety
    "MB24.7",  # Dysphoria
    "MB24.4",  # Apathy
    "MB24.6",  # Disturbance of affect
}

# Adjustment Reaction: 5 → 4 (Severe Mood/Affect)
ADJUSTMENT_5_TO_4 = {
    "MB24.2",  # Anhedonia
    "MB22.2",  # Demoralization
    "MB22.3",  # Hopelessness
    "MB22.0",  # Avolition
}

# Normal Stress: -1 → 2 (Stress Events Nặng)
NORMAL_STRESS_MINUS1_TO_2 = {
    "QE62",    # Uncomplicated bereavement
    "QE84",    # Acute stress reaction
    "QE80",    # Victim of crime or terrorism
    "QE81",    # Exposure to disaster, war or other hostilities
    "QE61.0",  # Loss or death of child
}

# Normal Stress: -1 → 1 (Stress Context)
NORMAL_STRESS_MINUS1_TO_1 = {
    "QE30.0",  # Insufficient social insurance support, aged
    "QE30.1",  # Insufficient social insurance support, disability
    "QE30.2",  # Insufficient social insurance support, unemployment
    "QE30.3",  # Insufficient social insurance support, family support
    "QE31.0",  # Insufficient social welfare support, child protection
    "QE31.1",  # Insufficient social welfare support, protection against domestic violence
    "QE31.2",  # Insufficient social welfare support, protection against homelessness
    "QE31.3",  # Insufficient social welfare support, post prison services
    "QE40",    # Problem associated with conviction in civil or criminal proceedings
    "QE41",    # Problem associated with imprisonment and other incarceration
    "QE42",    # Problem associated with release from prison
    "QE82.0",  # Personal history of physical abuse
    "QE82.1",  # Personal history of sexual abuse
    "QE82.2",  # Personal history of psychological abuse
    "QE82.3",  # Personal history of neglect
    "QE83",    # Personal frightening experience in childhood
    "QE90",    # Inadequate parental supervision or control
    "QE91",    # Parental overprotection
    "QE92",    # Altered pattern of family relationships in childhood
    "QE93",    # Removal from home in childhood
    "QE94",    # Institutional upbringing
    "QE95",    # Inappropriate parental pressure
    "QE96",    # Events resulting in loss of self-esteem in childhood
    "QE60",    # Absence of family member
    "QE52.1",  # Loss of love relationship in childhood
}


def apply_mapping(item: dict) -> dict:
    """
    Apply score mapping to a single item.
    
    Returns:
        Modified item dict (new object, doesn't modify original)
    """
    chunk_id = item.get("chunk_id", "")
    item_type = item.get("type", "").lower()
    current_score = item.get("score", 0)
    
    # Create a copy to avoid modifying original
    new_item = item.copy()
    
    # Adjustment Reaction: 5 → 3
    if chunk_id in ADJUSTMENT_5_TO_3 and current_score == 5:
        new_item["score"] = 3
        logger.debug(f"  {chunk_id}: 5 → 3 (generic mood/affect)")
        return new_item
    
    # Adjustment Reaction: 5 → 4
    if chunk_id in ADJUSTMENT_5_TO_4 and current_score == 5:
        new_item["score"] = 4
        logger.debug(f"  {chunk_id}: 5 → 4 (severe mood/affect)")
        return new_item
    
    # Normal Stress: -1 → 2
    if chunk_id in NORMAL_STRESS_MINUS1_TO_2 and current_score == -1:
        new_item["score"] = 2
        logger.debug(f"  {chunk_id}: -1 → 2 (stress events nặng)")
        return new_item
    
    # Normal Stress: -1 → 1
    if chunk_id in NORMAL_STRESS_MINUS1_TO_1 and current_score == -1:
        new_item["score"] = 1
        logger.debug(f"  {chunk_id}: -1 → 1 (stress context)")
        return new_item
    
    # No change needed
    return new_item


def process_file(input_path: Path, output_path: Path):
    """
    Process normal_responses.jsonl and apply score mapping.
    """
    logger.info(f"Reading from: {input_path}")
    
    items = []
    changes = {
        "adjustment_5_to_3": 0,
        "adjustment_5_to_4": 0,
        "normal_stress_minus1_to_2": 0,
        "normal_stress_minus1_to_1": 0,
        "unchanged": 0,
    }
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    item = json.loads(line)
                    original_score = item.get("score", 0)
                    chunk_id = item.get("chunk_id", "")
                    
                    # Apply mapping
                    new_item = apply_mapping(item)
                    new_score = new_item.get("score", 0)
                    
                    # Track changes
                    if chunk_id in ADJUSTMENT_5_TO_3 and original_score == 5 and new_score == 3:
                        changes["adjustment_5_to_3"] += 1
                    elif chunk_id in ADJUSTMENT_5_TO_4 and original_score == 5 and new_score == 4:
                        changes["adjustment_5_to_4"] += 1
                    elif chunk_id in NORMAL_STRESS_MINUS1_TO_2 and original_score == -1 and new_score == 2:
                        changes["normal_stress_minus1_to_2"] += 1
                    elif chunk_id in NORMAL_STRESS_MINUS1_TO_1 and original_score == -1 and new_score == 1:
                        changes["normal_stress_minus1_to_1"] += 1
                    else:
                        changes["unchanged"] += 1
                    
                    items.append(new_item)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: JSON decode error: {e}")
                    continue
        
        logger.info(f"Loaded {len(items)} items")
        
        # Write output
        logger.info(f"Writing to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        logger.info("=" * 80)
        logger.info("CHANGES SUMMARY:")
        logger.info(f"  Adjustment Reaction 5 → 3: {changes['adjustment_5_to_3']} items")
        logger.info(f"  Adjustment Reaction 5 → 4: {changes['adjustment_5_to_4']} items")
        logger.info(f"  Normal Stress -1 → 2: {changes['normal_stress_minus1_to_2']} items")
        logger.info(f"  Normal Stress -1 → 1: {changes['normal_stress_minus1_to_1']} items")
        logger.info(f"  Unchanged: {changes['unchanged']} items")
        logger.info(f"  Total: {len(items)} items")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing file: {e}", exc_info=True)
        return False


def main():
    base_dir = Path(__file__).parent
    input_path = base_dir / "data" / "raw" / "normal_responses.jsonl"
    output_path = base_dir / "data" / "raw" / "normal_responses_v2.jsonl"
    
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1
    
    logger.info("=" * 80)
    logger.info("APPLYING SCORE MAPPING")
    logger.info("=" * 80)
    
    success = process_file(input_path, output_path)
    
    if success:
        logger.info("✅ Mapping applied successfully!")
        logger.info(f"Output file: {output_path}")
        logger.info("\nNext steps:")
        logger.info("1. Review the output file")
        logger.info("2. Test with your test cases")
        logger.info("3. If OK, replace original file or update code to use v2")
        return 0
    else:
        logger.error("❌ Failed to apply mapping")
        return 1


if __name__ == "__main__":
    exit(main())

