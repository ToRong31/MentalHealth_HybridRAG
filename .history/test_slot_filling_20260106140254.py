"""
Test script để debug slot filling issue
"""
import requests
import json

# API endpoint
BASE_URL = "http://localhost:8000"

# Step 1: Register/Login to get token
def get_auth_token():
    """Get authentication token"""
    # Try login first
    login_data = {
        "username": "testuser",
        "password": "testpass123"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    
    if response.status_code == 200:
        return response.json()["access_token"]
    
    # If login fails, try another user
    print(f"Login failed: {response.text}")
    print("Trying alternative user...")
    login_data = {
        "username": "debuguser",
        "password": "debug123"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    
    if response.status_code == 200:
        return response.json()["access_token"]
    
    # Register new user
    print("Alternative login failed, registering new user...")
    register_data = {
        "username": "debuguser",
        "password": "debug123",
        "email": "debug@example.com"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_data)
    
    if response.status_code == 201:
        return response.json()["access_token"]
    
    raise Exception(f"Failed to authenticate: {response.text}")


# Step 2: Send chat message to test slot filling
def send_chat_message(token, message, conversation_id=None):
    """Send chat message"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "message": message
    }
    
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    response = requests.post(f"{BASE_URL}/api/v1/chat", json=payload, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Chat request failed: {response.status_code} - {response.text}")


def main():
    """Main test flow"""
    print("="*80)
    print("SLOT FILLING DEBUG TEST")
    print("="*80)
    
    # Step 1: Authenticate
    print("\n[1] Authenticating...")
    token = get_auth_token()
    print(f"✅ Got token: {token[:20]}...")
    
    # Step 2: Send first message (trigger slot filling)
    print("\n[2] Sending first message...")
    message1 = "Dạo gần đây tôi cảm thấy buồn và mệt mỏi"
    response1 = send_chat_message(token, message1)
    
    print(f"Bot response: {response1['answer']}")
    print(f"Conversation ID: {response1['conversation_id']}")
    
    # Step 3: Send second message with slot information
    print("\n[3] Sending second message with slot information...")
    message2 = "Tôi cảm thấy buồn chán, không có động lực làm việc. Tình trạng này kéo dài khoảng 2 tuần rồi. Nguyên nhân có thể là do áp lực công việc quá lớn."
    response2 = send_chat_message(token, message2, response1['conversation_id'])
    
    print(f"Bot response: {response2['answer']}")
    
    # Step 4: Check if slots were extracted
    print("\n[4] Checking backend logs for slot extraction...")
    print("⚠️ Please check Docker logs: docker compose logs backend | Select-String 'SLOT FILLING'")
    
    print("\n" + "="*80)
    print("TEST COMPLETE - Check logs above for slot extraction results")
    print("="*80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
