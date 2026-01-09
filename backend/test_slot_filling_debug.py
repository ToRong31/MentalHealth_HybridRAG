"""
Debug Slot Filling - Test direct call to understand why no follow-up questions
"""
import sys
import asyncio
import json
sys.path.insert(0, "/app/src")

from rag.llm.answer_nodes.slot_filling import process_slot_filling

async def main():
    print("="*80)
    print("🔍 DEBUGGING SLOT FILLING - WHY NO FOLLOW-UP QUESTIONS?")
    print("="*80)
    print()
    
    # Test với câu hỏi đơn giản
    test_cases = [
        {
            "question": "I feel sad and tired for 2 weeks",
            "expected": "Should ask about: trigger, intensity, impairment"
        },
        {
            "question": "I'm anxious continuously, hard to control",
            "expected": "Should ask about: when it started, physical symptoms, work impact"
        },
        {
            "question": "I have to wash hands many times to feel safe",
            "expected": "Should ask about: duration, how long per ritual, work/life impact"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST CASE #{i}")
        print(f"{'='*80}")
        print(f"Question: {test['question']}")
        print(f"Expected: {test['expected']}")
        print()
        
        try:
            # Call slot filling directly
            result = await process_slot_filling(test['question'], existing_slots=None)
            
            slots = result.get("slots", {})
            missing_slots = result.get("missing_slots", [])
            relevant_missing = result.get("relevant_missing_slots", [])
            follow_ups = result.get("follow_up_questions", [])
            
            # Show filled slots
            filled = {k: v for k, v in slots.items() if v and v != [] and v != "unknown"}
            print(f"✅ Filled slots ({len(filled)}):")
            for k, v in filled.items():
                print(f"   • {k}: {v}")
            
            print(f"\n❌ Missing slots total: {len(missing_slots)}")
            print(f"🎯 Relevant missing slots: {len(relevant_missing)}")
            if relevant_missing:
                print(f"   {relevant_missing}")
            
            print(f"\n💬 Follow-up questions: {len(follow_ups)}")
            if follow_ups:
                for j, q in enumerate(follow_ups, 1):
                    print(f"   {j}. {q}")
            else:
                print("   ⚠️  NO FOLLOW-UP QUESTIONS GENERATED!")
                print("   This is the problem!")
            
            # Analyze
            print(f"\n📊 Analysis:")
            if not follow_ups and relevant_missing:
                print(f"   🔴 PROBLEM: {len(relevant_missing)} relevant missing slots but NO questions generated")
                print(f"   Missing: {relevant_missing}")
            elif not follow_ups and not relevant_missing:
                print(f"   ⚠️  LLM thinks all relevant slots are filled (none in relevant_missing_slots)")
            elif follow_ups:
                print(f"   ✅ Follow-up questions generated correctly")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print("="*80)
    print("🎯 CONCLUSION")
    print("="*80)
    print("""
If follow_up_questions is empty [], the issue could be:
1. LLM not following prompt format (not generating follow_up_questions field)
2. Prompt may have conflicting instructions
3. LLM thinks no follow-up needed (relevant_missing_slots = [])
4. JSON parsing failing silently

Check the raw LLM response to see what's being generated.
    """)

if __name__ == "__main__":
    asyncio.run(main())
