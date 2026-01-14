# 📮 Hướng Dẫn Test API với Postman

## 🚨 Khắc Phục Lỗi "Failed to fetch"

### Nguyên nhân lỗi:
1. **Backend chưa được khởi động**
2. **PostgreSQL chưa sẵn sàng**
3. **Port 8000 đã được sử dụng bởi service khác**
4. **CORS hoặc network issues**

### Các bước kiểm tra:

#### 1️⃣ Kiểm tra Docker Services
```powershell
# Kiểm tra các container đang chạy
docker ps

# Kiểm tra logs của backend
docker logs chatbot-backend

# Kiểm tra logs của postgres
docker logs mental_health_db
```

#### 2️⃣ Kiểm tra Backend đang chạy
```powershell
# Test health endpoint
curl http://localhost:8000/

# Hoặc truy cập trên browser
Start-Process "http://localhost:8000/health"
```

#### 3️⃣ Khởi động lại services nếu cần
```powershell
# Dừng tất cả
docker-compose down

# Khởi động lại
docker-compose up -d postgres neo4j

# Đợi 10 giây cho DB sẵn sàng
Start-Sleep -Seconds 10

# Khởi động backend
docker-compose up -d backend

# Xem logs
docker-compose logs -f backend
```

#### 4️⃣ Nếu chạy backend local (không dùng Docker)
```powershell
# Di chuyển vào thư mục backend
cd d:\UIT\Nam3\HK1\RAG\app\backend

# Activate virtual environment (nếu có)
.\venv\Scripts\Activate.ps1

# Chạy backend
python main.py
```

---

## 📦 Import Postman Collection

### Bước 1: Mở Postman
1. Mở ứng dụng Postman
2. Click **Import** (góc trên bên trái)
3. Chọn **File** 
4. Browse đến file: `d:\UIT\Nam3\HK1\RAG\app\Mental_Health_API.postman_collection.json`
5. Click **Import**

### Bước 2: Kiểm tra Collection
- Bạn sẽ thấy collection **"Mental Health Chatbot API"** ở sidebar bên trái
- Collection có 4 folders chính:
  - 0. Health Check
  - 1. Authentication
  - 2. Conversations
  - 3. Chat Messages
  - 4. Complete Test Flow

---

## 🧪 Test Cases Chi Tiết

### ✅ Test 1: Health Check (Kiểm tra backend hoạt động)

#### Request 1.1: Root Health Check
```
GET http://localhost:8000/
```

**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "Mental Health Chatbot API",
  "version": "2.0.0"
}
```

#### Request 1.2: Detailed Health Check
```
GET http://localhost:8000/health
```

**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "graph_initialized": true,
  "database": "connected"
}
```

---

### 🔐 Test 2: Authentication

#### Request 2.1: Register User 1
```
POST http://localhost:8000/auth/register
Content-Type: application/json

{
  "username": "testuser1",
  "email": "test1@example.com",
  "password": "password123"
}
```

**Expected Response (201 Created):**
```json
{
  "user": {
    "id": 1,
    "username": "testuser1",
    "email": "test1@example.com",
    "created_at": "2025-11-27T15:08:42.123456+07:00"
  },
  "token": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
}
```

> **📝 Note:** Token sẽ được tự động lưu vào biến `{{token}}` để sử dụng cho các request tiếp theo

#### Request 2.2: Register User 2 (Alice)
```
POST http://localhost:8000/auth/register
Content-Type: application/json

{
  "username": "alice",
  "email": "alice@example.com",
  "password": "secure123"
}
```

#### Request 2.3: Register User 3 (Admin - Email của bạn)
```
POST http://localhost:8000/auth/register
Content-Type: application/json

{
  "username": "admin",
  "email": "trongprokik114@gmail.com",
  "password": "admin123"
}
```

**Expected Error (400 Bad Request) - nếu user đã tồn tại:**
```json
{
  "detail": "Email already registered"
}
```

#### Request 2.4: Login User
```
POST http://localhost:8000/auth/login
Content-Type: application/json

{
  "email": "test1@example.com",
  "password": "password123"
}
```

**Expected Response (200 OK):**
```json
{
  "user": {
    "id": 1,
    "username": "testuser1",
    "email": "test1@example.com",
    "created_at": "2025-11-27T15:08:42.123456+07:00"
  },
  "token": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
}
```

#### Request 2.5: Get Current User Info
```
GET http://localhost:8000/auth/me
Authorization: Bearer {{token}}
```

**Expected Response (200 OK):**
```json
{
  "id": 1,
  "username": "testuser1",
  "email": "test1@example.com",
  "created_at": "2025-11-27T15:08:42.123456+07:00"
}
```

#### Request 2.6: Login with Invalid Credentials
```
POST http://localhost:8000/auth/login
Content-Type: application/json

{
  "email": "wrong@example.com",
  "password": "wrongpassword"
}
```

**Expected Error (401 Unauthorized):**
```json
{
  "detail": "Incorrect email or password"
}
```

---

### 💬 Test 3: Conversations

> **⚠️ Important:** Bạn phải có token hợp lệ (đã login) để test các endpoints này

#### Request 3.1: Create Conversation 1
```
POST http://localhost:8000/conversations
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "title": "My First Conversation"
}
```

**Expected Response (201 Created):**
```json
{
  "id": 1,
  "user_id": 1,
  "title": "My First Conversation",
  "created_at": "2025-11-27T15:10:00.123456+07:00",
  "updated_at": "2025-11-27T15:10:00.123456+07:00"
}
```

> **📝 Note:** Conversation ID sẽ được tự động lưu vào biến `{{conversation_id}}`

#### Request 3.2: Create Conversation 2
```
POST http://localhost:8000/conversations
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "title": "Mental Health Support Session"
}
```

#### Request 3.3: List All Conversations
```
GET http://localhost:8000/conversations
Authorization: Bearer {{token}}
```

**Expected Response (200 OK):**
```json
[
  {
    "id": 2,
    "user_id": 1,
    "title": "Mental Health Support Session",
    "created_at": "2025-11-27T15:12:00.123456+07:00",
    "updated_at": "2025-11-27T15:12:00.123456+07:00"
  },
  {
    "id": 1,
    "user_id": 1,
    "title": "My First Conversation",
    "created_at": "2025-11-27T15:10:00.123456+07:00",
    "updated_at": "2025-11-27T15:10:00.123456+07:00"
  }
]
```

#### Request 3.4: Get Conversation by ID
```
GET http://localhost:8000/conversations/{{conversation_id}}
Authorization: Bearer {{token}}
```

**Expected Response (200 OK):**
```json
{
  "id": 1,
  "user_id": 1,
  "title": "My First Conversation",
  "created_at": "2025-11-27T15:10:00.123456+07:00",
  "updated_at": "2025-11-27T15:10:00.123456+07:00",
  "messages": []
}
```

#### Request 3.5: Delete Conversation
```
DELETE http://localhost:8000/conversations/{{conversation_id}}
Authorization: Bearer {{token}}
```

**Expected Response (204 No Content):**
- No response body
- Status code: 204

---

### 💭 Test 4: Chat Messages

#### Request 4.1: Send Message - New Conversation
```
POST http://localhost:8000/chat
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "message": "I'm feeling anxious today. Can you help me?",
  "conversation_title": "Anxiety Help Session"
}
```

**Expected Response (200 OK):**
```json
{
  "answer": "I understand you're feeling anxious. Anxiety is a common experience...",
  "is_mental_health_related": true,
  "is_high_risk": false,
  "conversation_id": 3,
  "message_id": 2
}
```

> **📝 Note:** 
> - Conversation ID mới sẽ được tạo tự động
> - Message ID được trả về cho cả user message và bot response

#### Request 4.2: Send Message - Existing Conversation
```
POST http://localhost:8000/chat
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "message": "What are some breathing exercises I can try?",
  "conversation_id": {{conversation_id}}
}
```

**Expected Response (200 OK):**
```json
{
  "answer": "Here are some effective breathing exercises you can try...",
  "is_mental_health_related": true,
  "is_high_risk": false,
  "conversation_id": 3,
  "message_id": 4
}
```

#### Request 4.3: Send Message - Depression Topic
```
POST http://localhost:8000/chat
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "message": "I've been feeling very sad and unmotivated lately. What should I do?",
  "conversation_id": {{conversation_id}}
}
```

#### Request 4.4: Send Message - Stress Management
```
POST http://localhost:8000/chat
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "message": "How can I manage stress from work?",
  "conversation_id": {{conversation_id}}
}
```

#### Request 4.5: Send Message - Non Mental Health
```
POST http://localhost:8000/chat
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "message": "What is the capital of France?",
  "conversation_id": {{conversation_id}}
}
```

**Expected Response (200 OK):**
```json
{
  "answer": "I'm here to provide mental health support. Your question doesn't seem related to mental health...",
  "is_mental_health_related": false,
  "is_high_risk": false,
  "conversation_id": 3,
  "message_id": 6
}
```

---

## 🔄 Test 5: Complete Test Flow (Automated)

Folder **"4. Complete Test Flow"** chứa một bộ test tự động hoàn chỉnh:

### Chạy toàn bộ flow:
1. Click vào folder **"4. Complete Test Flow"**
2. Click nút **"Run"** ở góc trên bên phải
3. Click **"Run Mental Health Chatbot API"**
4. Xem kết quả test

### Flow bao gồm:
1. ✅ **Step 1:** Register new user với random username/email
2. ✅ **Step 2:** Create conversation
3. ✅ **Step 3:** Send chat message
4. ✅ **Step 4:** View conversation history

---

## 📊 Postman Variables (Tự động)

Collection sử dụng các biến sau (được tự động set):

| Variable | Description | Example |
|----------|-------------|---------|
| `{{base_url}}` | API base URL | `http://localhost:8000` |
| `{{token}}` | JWT access token | `eyJhbGciOiJIUzI1NiIs...` |
| `{{user_id}}` | Current user ID | `1` |
| `{{conversation_id}}` | Current conversation ID | `3` |

### Xem/Edit Variables:
1. Click vào collection name
2. Click tab **"Variables"**
3. Xem **Current Value** column

---

## 🐛 Common Error Responses

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```
**Fix:** Login lại để lấy token mới

### 404 Not Found
```json
{
  "detail": "Conversation not found"
}
```
**Fix:** Kiểm tra `conversation_id` có đúng không

### 400 Bad Request
```json
{
  "detail": "Email already registered"
}
```
**Fix:** Sử dụng email khác hoặc login với email đó

### 503 Service Unavailable
```json
{
  "detail": "Graph not initialized. Please try again later."
}
```
**Fix:** Đợi backend khởi động xong (xem logs)

---

## 🎯 Thứ tự Test Khuyến Nghị

### Lần đầu test:
1. ✅ **Health Check** - Đảm bảo backend đang chạy
2. ✅ **Register User** - Tạo tài khoản mới
3. ✅ **Get Current User** - Xác nhận đã đăng nhập
4. ✅ **Create Conversation** - Tạo cuộc hội thoại
5. ✅ **Send Message** - Gửi tin nhắn
6. ✅ **List Conversations** - Xem danh sách
7. ✅ **Get Conversation** - Xem chi tiết + messages
8. ✅ **Delete Conversation** - Xóa cuộc hội thoại

### Test lại (đã có user):
1. ✅ **Health Check**
2. ✅ **Login** - Đăng nhập với tài khoản có sẵn
3. ✅ **List Conversations** - Xem danh sách cũ
4. ✅ Tiếp tục test các chức năng khác...

---

## 🔍 Debug Tips

### Xem Request Details
1. Click vào request đã chạy
2. Xem tab **"Body"** - Request data
3. Xem tab **"Headers"** - Request headers

### Xem Response Details
1. Xem tab **"Body"** - Response data
2. Xem tab **"Headers"** - Response headers
3. Xem **Status** - HTTP status code

### Xem Console
1. Click **View** menu
2. Click **Show Postman Console** (Alt+Ctrl+C)
3. Xem tất cả request/response logs

### Test Scripts
Một số request có **Test Scripts** tự động:
- Kiểm tra status code
- Lưu token vào biến
- Lưu conversation_id vào biến
- Validate response structure

---

## 📞 Support

Nếu gặp vấn đề:
1. Kiểm tra backend logs: `docker logs chatbot-backend -f`
2. Kiểm tra postgres logs: `docker logs mental_health_db -f`
3. Đảm bảo `.env` file có đúng config
4. Restart services: `docker-compose restart backend`

---

## 🎉 Happy Testing!

Collection này đã bao gồm tất cả các test cases cần thiết. Bạn có thể:
- Chạy từng request riêng lẻ
- Chạy cả folder cùng lúc
- Customize và thêm test cases mới
- Export kết quả test

**Chúc bạn test thành công! 🚀**
