"""
Test API với prompt mới qua HTTP request
"""
import requests
import json

API_URL = "http://localhost:8000/api/v1/chat"

# Test cases
test_messages = [
    {
        "name": "Depression Test",
        "message": "Tôi buồn và mệt mỏi suốt 2 tuần, không muốn làm gì cả"
    },
    {
        "name": "Anxiety Test", 
        "message": "Tôi lo lắng liên tục, khó kiểm soát"
    },
    {
        "name": "OCD Test",
        "message": "Tôi phải rửa tay nhiều lần mới yên tâm"
    },
    {
        "name": "Panic Test",
        "message": "Tôi hay bị cơn hồi hộp, khó thở đột ngột"
    },
    {
        "name": "PTSD Test",
        "message": "Sau tai nạn, tôi hay giật mình và tránh đi qua chỗ đó"
    },
    {
        "name": "Tic Disorders Test",
        "message": "Con tôi hay nhấp nháy mắt và khạc họng"
    }
]

print("="*80)
print("🧪 TESTING API WITH NEW REWRITER PROMPT")
print("="*80)
print()

for i, test in enumerate(test_messages, 1):
    print(f"📝 Test {i}/{len(test_messages)}: {test['name']}")
    print(f"   Message: {test['message']}")
    
    try:
        # Gửi request
        response = requests.post(
            API_URL,
            json={
                "message": test['message'],
                "thread_id": f"test_prompt_{i}"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Kiểm tra response
            if "response" in data:
                print(f"   ✅ Status: {response.status_code}")
                print(f"   Response preview: {data['response'][:200]}...")
                print()
            else:
                print(f"   ⚠️  Status: {response.status_code} but no response field")
                print(f"   Data: {json.dumps(data, ensure_ascii=False)[:200]}")
                print()
        else:
            print(f"   ❌ Status: {response.status_code}")
            print(f"   Error: {response.text[:200]}")
            print()
            
    except requests.exceptions.Timeout:
        print(f"   ⏱️  TIMEOUT: Request took longer than 30 seconds")
        print()
    except Exception as e:
        print(f"   ❌ ERROR: {str(e)}")
        print()

print("="*80)
print("✅ API Testing Complete")
print("="*80)
print()
print("💡 Next Steps:")
print("   1. Check LangSmith dashboard for trace details")
print("   2. Review query rewriting quality in traces")
print("   3. Verify retrieval scores improved")
print()
