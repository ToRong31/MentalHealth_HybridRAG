# Mental Health Chatbot - RAG Application

Ứng dụng chatbot hỗ trợ sức khỏe tâm thần sử dụng React, FastAPI, Neo4j, PostgreSQL và Milvus với RAG (Retrieval-Augmented Generation).

## 🏗️ Kiến trúc

- **Frontend**: React + TypeScript + Vite
- **Backend**: FastAPI (Python)
- **Graph Database**: Neo4j (Knowledge Graph)
- **Vector Database**: Milvus (Vector Search)
- **Relational Database**: PostgreSQL (User & Conversation Data)
- **LLM**: Google Gemini

## 📋 Yêu cầu

- **Docker Desktop** (đã cài đặt và đang chạy)
- **Git**
- **Google Gemini API Key**
- **Milvus Cloud Credentials** (URI & Token)

## 🚀 Hướng dẫn chạy bằng Docker (Khuyên dùng)

Đây là cách nhanh nhất để khởi chạy toàn bộ hệ thống.

### 1. Clone dự án

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Cấu hình biến môi trường

Hệ thống cần một số API key để hoạt động. Bạn cần tạo file `.env` trong thư mục `backend/src/`.

1.  Di chuyển vào thư mục backend src:
    ```bash
    cd backend/src
    ```
2.  Tạo file `.env` (hoặc copy từ `.env.example` nếu có) và điền các thông tin sau:

    ```env
    # Google Gemini API (Bắt buộc)
    GEMINI_API_KEY=your_actual_gemini_api_key_here

    # Milvus Cloud (Zilliz Cloud) (Bắt buộc)
    MILVUS_URI=https://your-cluster.aws-us-west-2.vectordb.zillizcloud.com:19530
    MILVUS_TOKEN=your_cloud_token_here
    
    # Cấu hình khác (Tùy chọn - Docker đã tự cấu hình các giá trị này)
    # NEO4J_URI=bolt://neo4j:7687
    # DATABASE_URL=...
    ```

    *Lưu ý: Các cấu hình kết nối Database (Neo4j, Postgres) đã được Docker Compose tự động xử lý, bạn không cần sửa trừ khi muốn thay đổi.*

3.  Quay lại thư mục gốc của dự án:
    ```bash
    cd ../..
    ```

### 3. Khởi động ứng dụng

Chạy lệnh sau tại thư mục gốc của dự án:

```bash
docker-compose up -d
```

Lệnh này sẽ:
- Tải và build các Docker image cho Frontend và Backend.
- Khởi động Neo4j, PostgreSQL, PgAdmin.
- Kết nối các service với nhau.

*Lần đầu chạy có thể mất vài phút để build và khởi tạo database.*

### 4. Truy cập ứng dụng

Sau khi khởi động thành công, bạn có thể truy cập các dịch vụ tại:

| Dịch vụ | URL | Tài khoản mặc định (nếu có) |
|---------|-----|-----------------------------|
| **Chatbot UI** | http://localhost | - |
| **Backend API** | http://localhost:8000/docs | - |
| **Neo4j Browser** | http://localhost:7474 | User: `neo4j` / Pass: `kguser2005` |
| **PgAdmin** | http://localhost:5050 | Email: `admin@admin.com` / Pass: `admin123` |

### 5. Quản lý Docker

- **Xem trạng thái các containers:**
  ```bash
  docker-compose ps
  ```

- **Xem logs (để debug):**
  ```bash
  docker-compose logs -f backend    # Xem log backend
  docker-compose logs -f frontend   # Xem log frontend
  ```

- **Dừng ứng dụng:**
  ```bash
  docker-compose down
  ```

- **Dừng và xóa dữ liệu (Reset):**
  ```bash
  docker-compose down -v
  ```

## 🛠️ Development (Chạy Local không dùng Docker toàn bộ)

Nếu bạn muốn phát triển code và chạy từng phần riêng lẻ:

### Backend
1.  Cài đặt Python 3.11+.
2.  Tạo venv: `python -m venv venv`
3.  Activate venv.
4.  Cài requirements: `pip install -r backend/requirements.txt`
5.  Chạy các service phụ trợ bằng Docker: `docker-compose up -d neo4j postgres`
6.  Cấu hình `.env` trong `backend/src` (bao gồm cả DB credentials trỏ về localhost).
7.  Chạy backend: `python backend/main.py`

### Frontend
1.  Cài đặt Node.js 20+.
2.  `cd frontend`
3.  `npm install`
4.  `npm run dev`

## � Cấu trúc thư mục chính

```
app/
├── docker-compose.yaml         # File cấu hình Docker toàn bộ hệ thống
├── backend/                    # Mã nguồn Backend (FastAPI)
│   ├── src/
│   │   ├── .env                # File cấu hình (Cần tạo)
│   │   └── ...
│   └── Dockerfile
├── frontend/                   # Mã nguồn Frontend (React)
│   └── Dockerfile
├── init-db.sql                 # Script khởi tạo Database
└── README.md                   # Hướng dẫn sử dụng
```
