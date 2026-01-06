
import asyncio
import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

load_dotenv()

from src.rag.llm.answer_nodes.slot_filling import process_slot_filling
from src.rag.utils.slots import get_default_slots

async def test_repro():
    # Simulate a scenario where the user provides information but it might be missed
    
    # Case 1: Direct statement
    question = "Tôi cảm thấy lo lắng 1 tuần nay vì công việc quá tải"
    print(f"\n--- Testing Case 1: {question} ---")
    result = await process_slot_filling(question, existing_slots=get_default_slots())
    
    print("Slots extracted:")
    for k, v in result["slots"].items():
        if v and v != "none" and v != []:
             print(f"  {k}: {v}")
    
    # Case 2: Answering questions with context
    # Simulate that this is passed as "question" to the function
    context_question = """Recent conversation:
Q1: Bạn có thể cho biết cụ thể hơn về thời gian không?
A1: (Request for info)

Current question: Khoảng 2 tháng rồi bạn ạ"""
    
    print(f"\n--- Testing Case 2 (Contextual): {context_question} ---")
    
    # Pre-fill emotion to simulate ongoing conversation
    existing_slots = get_default_slots()
    existing_slots["emotion"] = "mệt mỏi"
    
    result = await process_slot_filling(context_question, existing_slots=existing_slots)
    
    print("Slots extracted:")
    for k, v in result["slots"].items():
        if v and v != "none" and v != []:
             print(f"  {k}: {v}")

if __name__ == "__main__":
    asyncio.run(test_repro())
