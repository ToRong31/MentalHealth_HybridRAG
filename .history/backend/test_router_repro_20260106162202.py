
import asyncio
import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

load_dotenv()

from src.rag.llm.answer_nodes.router import router

async def test_router():
    # Case 1: Short answer to duration question
    question = "Khoảng 2 tháng rồi bạn ạ"
    conversation_buffer = [
        {"user": "Tôi bị mất ngủ", "bot": "Bạn bị bao lâu rồi?"}
    ]
    query_type = "follow_up"
    
    print(f"\n--- Testing Case 1: {question} ---")
    result = await router(
        question=question, 
        query_type=query_type,
        conversation_buffer=conversation_buffer,
        awaiting_treatment_confirmation=False
    )
    
    print(f"Result: {result}")
    
    # Case 2: Short answer to emotion question
    question = "Buồn và mệt mỏi"
    conversation_buffer = [
        {"user": "Tôi thấy lạ lắm", "bot": "Bạn đang cảm thấy thế nào?"}
    ]
    query_type = "follow_up"
    
    print(f"\n--- Testing Case 2: {question} ---")
    result = await router(
        question=question, 
        query_type=query_type,
        conversation_buffer=conversation_buffer,
        awaiting_treatment_confirmation=False
    )
    
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test_router())
