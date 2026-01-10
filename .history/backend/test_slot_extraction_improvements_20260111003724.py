"""
Test Slot Extraction Improvements
Verify that improved extraction logic catches information from previous conversation
"""
import sys
import asyncio
sys.path.insert(0, "/app/src")

from rag.workflow.graph_nodes.slot_filling import slot_filling_node, _post_process_slot_extraction
from rag.utils.slots import get_default_slots

async def test_case_1_self_care():
    """
    Test Case 1: Self-care functioning slot
    User mentioned "lazy to chew, weight loss, struggle to shower" in turn 1
    Bot asks about eating in turn 2 → should NOT ask again in turn 3
    """
    print("\n" + "="*80)
    print("TEST CASE 1: Self-care functioning (slot 10)")
    print("="*80)
    
    state = {
        "question": "What about your eating habits?",
        "conversation_buffer": [
            {
                "user": "How are you doing?",
                "bot": "I'm lazy to chew food, losing weight, and have to struggle to take a shower."
            }
        ],
        "summary_context": "",
        "slots": get_default_slots()
    }
    
    print("\nConversation history:")
    print("Turn 1 User: I'm lazy to chew food, losing weight, and have to struggle to take a shower.")
    print("Turn 2 Bot: What about your eating habits?")
    
    result = await slot_filling_node(state)
    
    slots = result.get("slots", {})
    follow_ups = result.get("follow_up_questions", [])
    
    print("\n✅ Extracted slots:")
    if slots.get("self_care_functioning"):
        print(f"   self_care_functioning: {slots['self_care_functioning']}")
    else:
        print("   ❌ self_care_functioning: EMPTY (FAILED)")
    
    if slots.get("appetite_changes"):
        print(f"   appetite_changes: {slots['appetite_changes']}")
    
    print(f"\n💬 Follow-up questions ({len(follow_ups)}):")
    for i, q in enumerate(follow_ups, 1):
        print(f"   {i}. {q}")
        # Check if asking about self-care again
        if any(kw in q.lower() for kw in ["ăn uống", "vệ sinh", "tắm"]):
            print("      ⚠️ ASKING ABOUT SELF-CARE AGAIN (should not happen!)")
    
    return slots.get("self_care_functioning") is not None and len(slots.get("self_care_functioning", [])) > 0


async def test_case_2_medical_history():
    """
    Test Case 2: Medical history slot
    User said "no underlying medical conditions" in turn 1
    Bot asks about medical history in turn 2 → should NOT ask again in turn 3
    """
    print("\n" + "="*80)
    print("TEST CASE 2: Medical history (slot 12)")
    print("="*80)
    
    state = {
        "question": "Do you have any medical history?",
        "conversation_buffer": [
            {
                "user": "Tell me about yourself",
                "bot": "I don't have any underlying medical conditions and don't use any stimulants."
            }
        ],
        "summary_context": "",
        "slots": get_default_slots()
    }
    
    print("\nConversation history:")
    print("Turn 1 User: I don't have any underlying medical conditions and don't use any stimulants.")
    print("Turn 2 Bot: Do you have any medical history?")
    
    result = await slot_filling_node(state)
    
    slots = result.get("slots", {})
    follow_ups = result.get("follow_up_questions", [])
    
    print("\n✅ Extracted slots:")
    if slots.get("medical_history_any") != "unknown":
        print(f"   medical_history_any: {slots['medical_history_any']}")
    else:
        print("   ❌ medical_history_any: UNKNOWN (FAILED)")
    
    if slots.get("substance_use_any") != "unknown":
        print(f"   substance_use_any: {slots['substance_use_any']}")
    else:
        print("   ⚠️ substance_use_any: UNKNOWN")
    
    print(f"\n💬 Follow-up questions ({len(follow_ups)}):")
    for i, q in enumerate(follow_ups, 1):
        print(f"   {i}. {q}")
        # Check if asking about medical history or substance again
        if any(kw in q.lower() for kw in ["bệnh nền", "tiền sử", "chất kích thích"]):
            print("      ⚠️ ASKING ABOUT MEDICAL/SUBSTANCE AGAIN (should not happen!)")
    
    return slots.get("medical_history_any") == "no" and slots.get("substance_use_any") == "no"


async def test_case_3_frequency():
    """
    Test Case 3: Frequency slot
    User said "every day, almost all day" in turn 1
    Bot asks about trigger in turn 2 → should NOT ask about frequency again
    """
    print("\n" + "="*80)
    print("TEST CASE 3: Frequency (slot 15)")
    print("="*80)
    
    state = {
        "question": "What triggers your anxiety?",
        "conversation_buffer": [
            {
                "user": "How are you feeling?",
                "bot": "I feel anxious every day, almost all day long."
            }
        ],
        "summary_context": "",
        "slots": get_default_slots()
    }
    
    print("\nConversation history:")
    print("Turn 1 User: I feel anxious every day, almost all day long.")
    print("Turn 2 Bot: What triggers your anxiety?")
    
    result = await slot_filling_node(state)
    
    slots = result.get("slots", {})
    follow_ups = result.get("follow_up_questions", [])
    
    print("\n✅ Extracted slots:")
    if slots.get("frequency"):
        print(f"   frequency: {slots['frequency']}")
    else:
        print("   ❌ frequency: EMPTY (FAILED)")
    
    if slots.get("emotion"):
        print(f"   emotion: {slots['emotion']}")
    
    print(f"\n💬 Follow-up questions ({len(follow_ups)}):")
    for i, q in enumerate(follow_ups, 1):
        print(f"   {i}. {q}")
        # Check if asking about frequency again
        if any(kw in q.lower() for kw in ["tần suất", "bao lâu một lần", "mỗi ngày"]):
            print("      ⚠️ ASKING ABOUT FREQUENCY AGAIN (should not happen!)")
    
    return slots.get("frequency") is not None and len(slots.get("frequency", [])) > 0


async def test_post_processing():
    """
    Test post-processing function directly
    """
    print("\n" + "="*80)
    print("TEST: Post-processing function")
    print("="*80)
    
    slots = get_default_slots()
    conversation_buffer = [
        {
            "user": "I don't have any medical conditions",
            "bot": "OK"
        },
        {
            "user": "I don't use any stimulants",
            "bot": "Got it"
        }
    ]
    current_question = "How are you feeling?"
    
    processed_slots = _post_process_slot_extraction(slots, conversation_buffer, current_question)
    
    print("\n✅ Post-processed slots:")
    print(f"   medical_history_any: {processed_slots.get('medical_history_any')}")
    print(f"   substance_use_any: {processed_slots.get('substance_use_any')}")
    
    success = (
        processed_slots.get("medical_history_any") == "no" and
        processed_slots.get("substance_use_any") == "no"
    )
    
    return success


async def main():
    print("\n" + "="*80)
    print("🧪 TESTING SLOT EXTRACTION IMPROVEMENTS")
    print("="*80)
    print("\nTesting if improved extraction logic catches information from previous turns")
    print("and prevents redundant questions about already-answered slots.")
    
    results = []
    
    # Test 1
    try:
        test1_pass = await test_case_1_self_care()
        results.append(("Self-care functioning", test1_pass))
    except Exception as e:
        print(f"\n❌ Test 1 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Self-care functioning", False))
    
    # Test 2
    try:
        test2_pass = await test_case_2_medical_history()
        results.append(("Medical history", test2_pass))
    except Exception as e:
        print(f"\n❌ Test 2 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Medical history", False))
    
    # Test 3
    try:
        test3_pass = await test_case_3_frequency()
        results.append(("Frequency", test3_pass))
    except Exception as e:
        print(f"\n❌ Test 3 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Frequency", False))
    
    # Test 4
    try:
        test4_pass = await test_post_processing()
        results.append(("Post-processing", test4_pass))
    except Exception as e:
        print(f"\n❌ Test 4 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Post-processing", False))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Slot extraction improvements working correctly.")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Check logs above for details.")


if __name__ == "__main__":
    asyncio.run(main())
