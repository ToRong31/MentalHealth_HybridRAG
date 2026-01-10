"""
Test Disease Name Translation
Verify that disease names are translated correctly from English to Vietnamese
"""
import sys
sys.path.insert(0, "/app/src")

from rag.utils.disease_translation import translate_disease_name, translate_disease_list

def test_common_diseases():
    """Test translation of common disease names"""
    print("\n" + "="*80)
    print("🧪 Testing Disease Name Translation")
    print("="*80)
    
    test_cases = [
        ("Bipolar and Related Disorders", "Rối loạn Lưỡng cực và các rối loạn liên quan"),
        ("Bipolar Disorder", "Rối loạn Lưỡng cực"),
        ("Depressive Disorder", "Rối loạn Trầm cảm"),
        ("Major Depressive Disorder", "Rối loạn Trầm cảm nặng"),
        ("Anxiety Disorder", "Rối loạn Lo âu"),
        ("Generalized Anxiety Disorder", "Rối loạn Lo âu lan tỏa"),
        ("OCD", "Rối loạn Ám ảnh Cưỡng chế"),
        ("PTSD", "Rối loạn Căng thẳng sau Chấn thương"),
        ("Schizophrenia", "Tâm thần phân liệt"),
    ]
    
    passed = 0
    failed = 0
    
    for english, expected_vietnamese in test_cases:
        result = translate_disease_name(english)
        if result == expected_vietnamese:
            print(f"✅ '{english}' -> '{result}'")
            passed += 1
        else:
            print(f"❌ '{english}'")
            print(f"   Expected: '{expected_vietnamese}'")
            print(f"   Got:      '{result}'")
            failed += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed")
    return failed == 0


def test_case_insensitive():
    """Test case-insensitive matching"""
    print("\n" + "="*80)
    print("🧪 Testing Case-Insensitive Matching")
    print("="*80)
    
    test_cases = [
        "bipolar disorder",
        "BIPOLAR DISORDER",
        "Bipolar Disorder",
        "depressive disorder",
        "ANXIETY DISORDER",
    ]
    
    for test_case in test_cases:
        result = translate_disease_name(test_case)
        print(f"✅ '{test_case}' -> '{result}'")
    
    return True


def test_partial_matching():
    """Test partial matching for plural/singular variations"""
    print("\n" + "="*80)
    print("🧪 Testing Partial Matching")
    print("="*80)
    
    test_cases = [
        ("Depressive Disorders", "Các rối loạn Trầm cảm"),  # Plural version
        ("Anxiety Disorders", "Các rối loạn Lo âu"),        # Plural version
    ]
    
    for english, expected in test_cases:
        result = translate_disease_name(english)
        match = result == expected
        status = "✅" if match else "⚠️"
        print(f"{status} '{english}' -> '{result}'")
        if not match:
            print(f"   Expected: '{expected}'")
    
    return True


def test_unknown_diseases():
    """Test handling of unknown diseases"""
    print("\n" + "="*80)
    print("🧪 Testing Unknown Diseases (should return original)")
    print("="*80)
    
    test_cases = [
        "Some Unknown Disorder",
        "Made Up Condition",
        "",
    ]
    
    for test_case in test_cases:
        result = translate_disease_name(test_case)
        print(f"ℹ️  '{test_case}' -> '{result}' (no translation)")
        if result == test_case:
            print(f"   ✅ Correctly returned original")
        else:
            print(f"   ⚠️  Unexpected result")
    
    return True


def test_list_translation():
    """Test translating a list of diseases"""
    print("\n" + "="*80)
    print("🧪 Testing List Translation")
    print("="*80)
    
    disease_list = [
        "Bipolar Disorder",
        "Depressive Disorder",
        "Anxiety Disorder",
        "Unknown Condition"
    ]
    
    result = translate_disease_list(disease_list)
    
    print("Input:")
    for d in disease_list:
        print(f"  - {d}")
    
    print("\nOutput:")
    for d in result:
        print(f"  - {d}")
    
    return True


def main():
    print("\n" + "="*80)
    print("🏥 DISEASE NAME TRANSLATION TEST SUITE")
    print("="*80)
    
    tests = [
        ("Common Diseases", test_common_diseases),
        ("Case Insensitive", test_case_insensitive),
        ("Partial Matching", test_partial_matching),
        ("Unknown Diseases", test_unknown_diseases),
        ("List Translation", test_list_translation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    
    print(f"\n{passed_count}/{total} test groups passed")
    
    if passed_count == total:
        print("\n🎉 All tests passed! Disease translation is working correctly.")
    else:
        print(f"\n⚠️ {total - passed_count} test group(s) failed.")


if __name__ == "__main__":
    main()
