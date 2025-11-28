# Mental Health Chatbot - Complete Setup Guide

## 🎯 Overview

This application now includes:
- ✅ **User Authentication** - JWT-based login/register system
- ✅ **Multi-Conversation Support** - Create and manage multiple chat sessions
- ✅ **PostgreSQL Database** - Persistent storage for users, conversations, and messages
- ✅ **Modern UI** - Beautiful dark theme with sidebar navigation
- ✅ **Docker Support** - Easy setup with Docker Compose

---

## 🚀 Quick Start

### Prerequisites
- Docker Desktop (running)
- Python 3.10+
- Node.js 16+
- PostgreSQL (via Docker or local)

### 1. Start PostgreSQL Database

```bash
# Start PostgreSQL and PgAdmin
docker-compose up -d postgres pgadmin

# Verify it's running
docker-compose ps
```

**PgAdmin Access:** http://localhost:5050
- Email: `admin@admin.com`
- Password: `admin123`

### 2. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Run Backend API

```bash
cd backend
python main.py
```

The API will be available at **http://localhost:8000**

**API Documentation:** http://localhost:8000/docs

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 5. Run Frontend

```bash
cd frontend
npm run dev
```

The frontend will be available at **http://localhost**

---

## 📚 Features ## Usage

### 1. Register/Login
- Open http://localhost
- Click **Register** tab
- Create an account with username, email, and password
- You'll be automatically logged in

### 2. Create Conversations
- Click **+ New Conversation** button
- Start chatting!
- Each conversation is saved automatically

### 3. Switch Between Conversations
- Click any conversation in the sidebar
- All message history is loaded
- Continue where you left off

### 4. Delete Conversations
- Hover over a conversation in the sidebar
- Click the 🗑️ icon
- Confirm deletion

---

## 🗂️ Project Structure

```
app/
├── backend/
│   ├── main.py                 # FastAPI application with all endpoints
│   ├── src/
│   │   ├── database.py         # Database connection & session management
│   │   ├── models.py           # SQLAlchemy models (User, Conversation, Message)
│   │   ├── schemas.py          # Pydantic schemas for validation
│   │   ├── auth.py             # Authentication utilities (JWT, password hashing)
│   │   └── workflow.py         # RAG workflow (existing)
│   └── requirements.txt        # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Main application with auth & conversation UI
│   │   ├── App.css             # Styling for the application
│   │   ├── api.ts              # API client for backend calls
│   │   └── types.ts            # TypeScript interfaces
│   └── package.json
├── docker-compose.yaml         # Docker services (PostgreSQL, PgAdmin, Neo4j)
├── init-db.sql                 # Database initialization script
├── .env                        # Environment variables
└── DOCKER_SETUP.md             # Docker setup instructions
```

---

## 🔐 Authentication Flow

1. **Register:** `POST /auth/register`
   - Creates user with hashed password
   - Returns JWT token + user info

2. **Login:** `POST /auth/login`
   - Validates credentials
   - Returns JWT token + user info

3. **Protected Routes:**
   - All conversation and chat endpoints require JWT token
   - Token sent in `Authorization: Bearer <token>` header
   - Frontend automatically includes token in all requests

---

## 💾 Database Schema

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Conversations Table
```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Messages Table
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    sender VARCHAR(10) NOT NULL, -- 'user' or 'bot'
    is_high_risk BOOLEAN DEFAULT FALSE,
    is_mental_health_related BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🛠️ API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login user
- `GET /auth/me` - Get current user info (requires auth)

### Conversations
- `GET /conversations` - List all user's conversations (requires auth)
- `POST /conversations` - Create new conversation (requires auth)
- `GET /conversations/{id}` - Get conversation with messages (requires auth)
- `DELETE /conversations/{id}` - Delete conversation (requires auth)

### Chat
- `POST /chat` - Send message and get response (requires auth)
  - Auto-creates conversation if not provided
  - Saves both user and bot messages

---

## 🧪 Testing

### Test Demo User (From init-db.sql)
- Email: `demo@example.com`
- Password: `demo123`

### Manual Testing Checklist

1. **Authentication**
   - [ ] Register new user
   - [ ] Login with correct credentials
   - [ ] Login fails with wrong credentials
   - [ ] Logout works

2. **Conversations**
   - [ ] Create new conversation
   - [ ] List shows all conversations
   - [ ] Switch between conversations
   - [ ] Delete conversation

3. **Chat**
   - [ ] Send message in conversation
   - [ ] Bot responds correctly
   - [ ] Messages persist after page refresh
   - [ ] High-risk messages are highlighted

4. **Security**
   - [ ] Cannot access chat without login
   - [ ] Cannot view other users' conversations
   - [ ] Token expires correctly

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres123@localhost:5432/mental_health_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mental_health_db
DB_USER=postgres
DB_PASSWORD=postgres123

# JWT
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_DAYS=7

# API
API_HOST=0.0.0.0
API_PORT=8000
```

**⚠️ IMPORTANT:** Change `SECRET_KEY` in production!

---

## 🐛 Troubleshooting

### Frontend Cannot Connect to Backend
- Check backend is running on port 8000
- Check CORS settings in `main.py`
- Verify API_BASE_URL in `frontend/src/api.ts`

### Database Connection Failed
- Ensure PostgreSQL is running: `docker-compose ps`
- Check DATABASE_URL in `.env`
- View logs: `docker-compose logs postgres`

### Authentication Not Working
- Clear browser localStorage
- Check JWT token in browser DevTools > Application > Local Storage
- Verify SECRET_KEY is same between restarts

### Messages Not Saving
- Check database tables exist: Connect via PgAdmin
- View backend logs for errors
- Verify user has active conversation

---

## 📝 Development Notes

### Adding New Features

1. **New Database Table:**
   - Add model in `backend/src/models.py`
   - Add schema in `backend/src/schemas.py`
   - Create migration if needed

2. **New API Endpoint:**
   - Add route in `backend/main.py`
   - Add function in `frontend/src/api.ts`
   - Update TypeScript types in `frontend/src/types.ts`

3. **New UI Component:**
   - Add to `frontend/src/App.tsx`
   - Style in `frontend/src/App.css`

---

## 🚢 Deployment

### Production Checklist

- [ ] Change `SECRET_KEY` to random value
- [ ] Update CORS origins in `main.py`
- [ ] Use strong database password
- [ ] Enable HTTPS
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure proper logging
- [ ] Set up database backups

---

## 📄 License

This project is for educational purposes.

---

## 🙏 Support

For issues or questions:
1. Check the troubleshooting section
2. Review API documentation at http://localhost:8000/docs
3. Inspect browser console and backend logs

---

**Happy Chatting! 💚**
