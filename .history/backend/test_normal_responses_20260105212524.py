"""
Test script to verify normal_responses.jsonl loading and matching
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from src.rag.utils.normal_response_matcher import load_normal_responses_database, match_symptoms_to_database
from src.rag.utils.assessment import assess_disorder_likelihood, parse_duration_score


def test_load_database():
    """Test loading the database"""
    print("=" * 80)
    print("TEST 1: Load normal_responses.jsonl database")
    print("=" * 80)
    
    database = load_normal_responses_database()
    
    print(f"✓ Loaded {len(database)} items")
    
    if database:
        print("\nFirst 5 items:")
        for i, item in enumerate(database[:5]):
            print(f"{i+1}. {item['chunk_id']}: {item['title']} (type={item['type']}, score={item['score']})")
    
    return len(database) > 0


def test_symptom_matching():
    """Test symptom matching"""
    print("\n" + "=" * 80)
    print("TEST 2: Match symptoms to database")
    print("=" * 80)
    
    # Test case 1: Work stress (should be normal_stress)
    test_slots_1 = {
        "primary_symptoms": ["lo lắng", "căng thẳng"],
        "recent_life_events": "Sắp có buổi thuyết trình quan trọng",
        "duration": "3 ngày",
        "emotion": "anxiety"
    }
    
    print("\nTest Case 1: Work stress (thuyết trình)")
    print(f"Slots: {test_slots_1}")
    
    matched_1 = match_symptoms_to_database(test_slots_1)
    print(f"✓ Matched {len(matched_1)} items:")
    for item in matched_1:
        print(f"  - {item['title']} (type={item['type']}, score={item['score']})")
    
    # Test case 2: Bereavement (should be normal_stress)
    test_slots_2 = {
        "primary_symptoms": ["buồn", "khóc nhiều"],
        "recent_life_events": "Mất người thân gần đây",
        "duration": "2 tuần",
        "emotion": "sadness"
    }
    
    print("\nTest Case 2: Bereavement")
    print(f"Slots: {test_slots_2}")
    
    matched_2 = match_symptoms_to_database(test_slots_2)
    print(f"✓ Matched {len(matched_2)} items:")
    for item in matched_2:
        print(f"  - {item['title']} (type={item['type']}, score={item['score']})")
    
    return len(matched_1) > 0 or len(matched_2) > 0


def test_duration_parsing():
    """Test duration parsing"""
    print("\n" + "=" * 80)
    print("TEST 3: Duration parsing")
    print("=" * 80)
    
    test_cases = [
        ("3 ngày", 0),
        ("1 tuần", 0),
        ("2 tuần", 1),
        ("1 tháng", 2),
        ("3 tháng", 2),
        ("6 tháng", 3),
        ("1 năm", 3)
    ]
    
    all_passed = True
    for duration_text, expected_d in test_cases:
        d = parse_duration_score(duration_text)
        status = "✓" if d == expected_d else "✗"
        print(f"{status} '{duration_text}' → D={d} (expected {expected_d})")
        if d != expected_d:
            all_passed = False
    
    return all_passed


def test_assessment_scoring():
    """Test complete assessment with scoring"""
    print("\n" + "=" * 80)
    print("TEST 4: Complete assessment with scoring")
    print("=" * 80)
    
    # Test case: Short-term work stress (should be normal_stress)
    test_slots = {
        "primary_symptoms": ["lo lắng", "mất ngủ"],
        "recent_life_events": "Deadline project quan trọng",
        "duration": "5 ngày",
        "emotion": "anxiety",
        "daily_functioning": "mild",
        "work_school_impact": "mild"
    }
    
    print("Test Case: Short-term work stress")
    print(f"Slots: {test_slots}")
    
    # Match symptoms
    matched_items = match_symptoms_to_database(test_slots)
    print(f"\n✓ Matched {len(matched_items)} items:")
    for item in matched_items:
        print(f"  - {item['title']} (type={item['type']}, score={item['score']})")
    
    # Run assessment
    category, explanation, confidence = assess_disorder_likelihood(test_slots, matched_items)
    
    print(f"\n✓ Assessment Result:")
    print(f"  Category: {category}")
    print(f"  Confidence: {confidence:.2f}")
    print(f"  Explanation: {explanation[:150]}...")
    
    # Should be normal_stress or adjustment_reaction
    return category in ["normal_stress", "adjustment_reaction"]


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "NORMAL RESPONSES DATABASE TEST" + " " * 32 + "║")
    print("╚" + "=" * 78 + "╝")
    
    results = []
    
    try:
        results.append(("Load Database", test_load_database()))
    except Exception as e:
        print(f"✗ ERROR: {e}")
        results.append(("Load Database", False))
    
    try:
        results.append(("Symptom Matching", test_symptom_matching()))
    except Exception as e:
        print(f"✗ ERROR: {e}")
        results.append(("Symptom Matching", False))
    
    try:
        results.append(("Duration Parsing", test_duration_parsing()))
    except Exception as e:
        print(f"✗ ERROR: {e}")
        results.append(("Duration Parsing", False))
    
    try:
        results.append(("Assessment Scoring", test_assessment_scoring()))
    except Exception as e:
        print(f"✗ ERROR: {e}")
        results.append(("Assessment Scoring", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
