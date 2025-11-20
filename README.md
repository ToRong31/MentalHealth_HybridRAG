# Mental Health Chatbot - RAG Application

Ứng dụng chatbot hỗ trợ sức khỏe tâm thần sử dụng React, FastAPI, Neo4j, và Milvus với RAG (Retrieval-Augmented Generation).

## 🏗️ Kiến trúc

- **Frontend**: React + TypeScript + Vite
- **Backend**: FastAPI (Python)
- **Graph Database**: Neo4j
- **Vector Database**: Milvus
- **LLM**: Google Gemini

## 📋 Yêu cầu

- Docker & Docker Compose
- Node.js 20+ (cho development)
- Python 3.11+ (cho development)
- Google Gemini API Key

## 🚀 Khởi động nhanh với Docker

### 1. Cấu hình biến môi trường

File `.env` đã có sẵn trong thư mục `backend/src/`.

Chỉnh sửa file `backend/src/.env` với các thông tin:

```env
# Google Gemini API
GEMINI_API_KEY=your_actual_gemini_api_key_here

# Milvus Cloud (Zilliz Cloud)
MILVUS_URI=https://your-cluster.aws-us-west-2.vectordb.zillizcloud.com:19530
MILVUS_TOKEN=your_cloud_token_here
```

**Lấy API keys tại**:
- Gemini API: https://makersuite.google.com/app/apikey
- Zilliz Cloud: https://cloud.zilliz.com/

⚠️ **Lưu ý**: Docker compose đã được cấu hình để sử dụng **Milvus Cloud**. Nếu muốn dùng Milvus local, uncomment phần `milvus` service trong `docker-compose.yaml`.

### 2. Khởi động tất cả services

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**Hoặc chạy trực tiếp:**
```bash
docker-compose up -d
```

Các services sẽ được khởi động:
- Neo4j (ports 7474, 7687) - Local Docker
- Backend API (port 8000) - Kết nối với Milvus Cloud
- Frontend (port 80)

### 3. Truy cập ứng dụng

- **Chatbot UI**: http://localhost
- **API Documentation**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474 
  - Username: `neo4j`
  - Password: `kguser2005`

### 4. Kiểm tra trạng thái services

```bash
# Kiểm tra tất cả containers
docker-compose ps

# Xem logs backend
docker-compose logs -f backend

# Xem logs frontend
docker-compose logs -f frontend

# Xem logs tất cả services
docker-compose logs -f
```

### 5. Dừng services

```bash
# Dừng containers
docker-compose down

# Dừng và xóa volumes
docker-compose down -v
```

## 🛠️ Development Setup (Chạy local)

### Backend

```bash
cd backend

# Tạo virtual environment
python -m venv venv

# Kích hoạt virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt

# Đảm bảo file .env đã được cấu hình
# backend/src/.env (và thêm GEMINI_API_KEY)

# Khởi động Neo4j trước
cd ..
docker-compose up -d neo4j

# Quay lại backend và chạy
cd backend
python main.py
```

Backend sẽ chạy tại: http://localhost:8000

### Frontend

```bash
cd frontend

# Cài đặt dependencies
npm install

# Chạy development server
npm run dev
```

Frontend sẽ chạy tại: http://localhost:5173

⚠️ **Lưu ý**: API URL trong `frontend/src/App.tsx`:
```typescript
const response = await fetch('http://localhost:8000/chat', {
```

## 📁 Cấu trúc thư mục

```
app/
├── docker-compose.yaml         # Docker compose cho tất cả services
├── .env.example                # Template biến môi trường
├── start.sh                    # Script khởi động (Linux/Mac)
├── start.bat                   # Script khởi động (Windows)
├── README.md                   # Tài liệu này
│
├── backend/
│   ├── src/                    # Source code backend
│   │   ├── api/                # API routes
│   │   ├── graph/              # Neo4j operations
│   │   ├── vectors/            # Milvus operations
│   │   ├── llm/                # LLM integrations
│   │   ├── retrieval/          # Retrieval strategies
│   │   ├── workflow/           # LangGraph workflows
│   │   ├── prompts/            # Prompt templates
│   │   └── config.py           # Configuration
│   ├── data/                   # Data directory
│   ├── main.py                 # FastAPI application
│   ├── Dockerfile              # Backend Docker image
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # Backend environment vars (tạo từ .env.example)
│
└── frontend/
    ├── src/
    │   ├── App.tsx             # Main chat component
    │   ├── App.css             # Chatbot styles
    │   └── main.tsx            # Entry point
    ├── Dockerfile              # Frontend Docker image
    ├── nginx.conf              # Nginx configuration
    └── package.json            # Node dependencies
```

## 🔧 Cấu hình

### Biến môi trường (backend/src/.env)

```env
# Embedding Model
E5_MODEL_NAME=intfloat/e5-large-v2

# Milvus Cloud (Zilliz Cloud)
MILVUS_URI=https://your-cluster.aws-us-west-2.vectordb.zillizcloud.com:19530
MILVUS_TOKEN=your_cloud_token_here
MILVUS_DB=default
MILVUS_COLLECTION=kg_entities

# For Local Milvus (uncomment if using local):
# MILVUS_URI=http://localhost:19530
# MILVUS_TOKEN=

# Neo4j (Graph Database)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=kguser2005

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-2.0-flash-exp

# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Docker Compose

File `docker-compose.yaml` bao gồm:

1. **Neo4j**: Graph database cho knowledge graph (local)
2. **Backend**: FastAPI application (kết nối Milvus Cloud qua API)
3. **Frontend**: React application với Nginx

**Lưu ý về Milvus**: Dự án này sử dụng **Milvus Cloud (Zilliz)** thay vì local Milvus để tiết kiệm tài nguyên. Nếu muốn dùng local Milvus, uncomment service `milvus` trong `docker-compose.yaml`.

## 📡 API Endpoints

### Health Check
```bash
GET http://localhost:8000/health
```

### Chat
```bash
POST http://localhost:8000/chat
Content-Type: application/json

{
  "message": "Tôi đang cảm thấy lo lắng, tôi nên làm gì?",
  "session_id": "optional-session-id"
}
```

Response:
```json
{
  "answer": "Tôi hiểu bạn đang cảm thấy lo lắng...",
  "is_mental_health_related": true,
  "is_high_risk": false,
  "session_id": "optional-session-id"
}
```

## 🎨 Tính năng Frontend

- Giao diện chat hiện đại, đơn giản
- Hiển thị tin nhắn real-time
- Phát hiện và cảnh báo high-risk
- Responsive design cho mobile và desktop
- Typing indicators
- Timestamp cho mỗi tin nhắn
- Gradient UI đẹp mắt

## 🔒 Lưu ý bảo mật

- **KHÔNG** commit file `.env` lên Git
- Sử dụng mật khẩu mạnh cho production databases
- Cấu hình CORS đúng cho production
- Sử dụng API keys riêng cho mỗi môi trường
- Bật HTTPS cho production

## 🐛 Xử lý lỗi

### Backend không khởi động
- Kiểm tra Neo4j và Milvus đã chạy chưa
- Xác nhận file `.env` tồn tại trong `backend/src/` và đã có GEMINI_API_KEY
- Xem logs: `docker-compose logs backend`

### Frontend không kết nối được backend
- Xác nhận backend đang chạy trên port 8000
- Kiểm tra CORS settings trong `backend/main.py`
- Đảm bảo API URL trong frontend khớp với backend URL

### Lỗi kết nối database
- Chờ databases khởi tạo hoàn tất (30-60 giây)
- Kiểm tra trạng thái: `docker-compose ps`
- Xác nhận credentials trong `.env` khớp với docker-compose

### Port bị conflict
Nếu port đã được sử dụng, sửa trong `docker-compose.yaml`:
```yaml
ports:
  - "8001:8000"  # Đổi port host từ 8000 sang 8001
```

## 📚 Rebuild containers

Nếu bạn thay đổi code hoặc dependencies:

```bash
# Rebuild tất cả
docker-compose up -d --build

# Rebuild chỉ backend
docker-compose up -d --build backend

# Rebuild chỉ frontend
docker-compose up -d --build frontend
```

## 🔄 Xóa dữ liệu và khởi động lại

```bash
# Dừng và xóa tất cả (bao gồm volumes)
docker-compose down -v

# Khởi động lại từ đầu
docker-compose up -d
```

## 📚 Tài liệu tham khảo

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [Milvus Documentation](https://milvus.io/docs)
- [LangChain Documentation](https://python.langchain.com/)

## 🤝 Hỗ trợ

Nếu gặp vấn đề, hãy kiểm tra:
1. Logs của services: `docker-compose logs [service-name]`
2. API docs: http://localhost:8000/docs
3. Kết nối database trong Neo4j Browser

## 📝 License

Dự án này dành cho mục đích giáo dục.

---

Made with ❤️ for mental health support
