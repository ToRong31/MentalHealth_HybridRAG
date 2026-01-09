"""
Test script để kiểm tra query rewriting với prompt mới
"""
import requests
import json
import uuid

# API endpoint
BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{BASE_URL}/api/v1/chat/"

# Tạo session ID mới để test
session_id = str(uuid.uuid4())

print("="*80)
print("🧪 TESTING QUERY REWRITE PROMPT")
print("="*80)
print(f"Session ID: {session_id}")
print()

# Test case: Câu hỏi về triệu chứng trầm cảm
test_message = "Tôi cảm thấy rất buồn và mệt mỏi suốt hơn một tháng nay, khó ngủ và không tập trung được"

print(f"📝 Test message: {test_message}")
print()
print("Sending request...")
print()

try:
    response = requests.post(
        CHAT_ENDPOINT,
        json={
            "message": test_message,
            "session_id": session_id
        },
        headers={
            "Content-Type": "application/json"
        },
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Response received:")
        print("-"*80)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("-"*80)
        print()
        print("🔍 Now check the Docker logs above to see:")
        print("   1. ✅ Successfully loaded query rewrite prompt")
        print("   2. 📝 Prompt preview")
        print("   3. 🔧 Prompt template first 300 chars")
        print("   4. ✅ Rewritten query output")
        print()
        print("The rewritten query should be NATURAL, not formal/listing style!")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Exception: {e}")
    
print()
print("="*80)
