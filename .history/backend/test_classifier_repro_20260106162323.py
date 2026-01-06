
import asyncio
import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

load_dotenv()

from src.rag.llm.answer_nodes.query_type_classifier import classify_query

async def test_classifier():
    # Case 1: Short answer to duration question
    question = "Khoảng 2 tháng rồi bạn ạ"
    conversation_buffer = [
        {"user": "Tôi bị mất ngủ", "bot": "Bạn bị bao lâu rồi?"}
    ]
    
    print(f"\n--- Testing Case 1: {question} ---")
    result = await classify_query(
        question=question, 
        conversation_buffer=conversation_buffer
    )
    
    print(f"Result: {result}")
    
    # Case 2: Short answer to emotion question
    question = "Buồn và mệt mỏi"
    conversation_buffer = [
        {"user": "Tôi thấy lạ lắm", "bot": "Bạn đang cảm thấy thế nào?"}
    ]
    
    print(f"\n--- Testing Case 2: {question} ---")
    result = await classify_query(
        question=question, 
        conversation_buffer=conversation_buffer
    )
    
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(test_classifier())
