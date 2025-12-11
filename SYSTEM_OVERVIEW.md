# System Overview - Mental Health Hybrid RAG

## Overview
- Chatbot hỗ trợ sức khỏe tâm thần sử dụng Hybrid RAG (Knowledge Graph + Vector Search).
- Backend: FastAPI (Python), kiến trúc clean layered; Frontend: React + TypeScript (Vite).
- Lưu trữ: PostgreSQL (users/conversations/messages), Neo4j (knowledge graph), Milvus (vector embeddings).

## Workflow (LangGraph)
1) translate_question: phát hiện VI/EN, dịch sang EN nếu cần.
2) safety_check: xác định `is_mental_health_related` và `is_high_risk`.
3) route:
   - high-risk → crisis_response → END
   - not mental health → not_mental_health → END
   - safe → graph_retrieval → answer → translate_answer → END
4) graph_retrieval:
   - Encode query (E5) → Milvus search anchors → Cohere rerank → Neo4j expand subgraph → build context.
5) answer: Gemini sinh câu trả lời từ graph context, sau đó dịch về ngôn ngữ gốc nếu cần.

## Dataflow (per chat request)
Frontend → POST /api/v1/chat (JWT) → ChatService:
1) Lấy/tạo conversation; lưu user message (PostgreSQL).
2) Chạy RAG workflow (LangGraph) qua `run_graph`.
3) Lưu bot response cùng flags (PostgreSQL); trả kết quả cho frontend.
4) UI cập nhật state theo conversation hiện tại.

## Technologies
- Backend: FastAPI, SQLAlchemy async, LangGraph, LangChain, Pydantic.
- Databases: PostgreSQL, Neo4j, Milvus (etcd + MinIO).
- Models/AI: E5-large-v2 embeddings, Gemini (LLM), Cohere (reranker).
- Frontend: React 19, TypeScript, Vite, Axios, React Router.
- Auth/Security: JWT, bcrypt; session management với inactivity timeout; CORS middleware.
- Infra: Docker Compose (services: postgres, pgadmin, neo4j, milvus stack, backend, frontend).

## Model Loading & Reuse
- E5 Embedding Model (`intfloat/e5-large-v2`):
  - Loaded once at startup in `src/rag/vectors/embeddings.py`.
  - Device auto-select (CUDA nếu có, else CPU).
  - Singleton dùng chung cho mọi request.
- RAG Graph Workflow:
  - Build & compile tại startup (`build_kg_graph`), inject vào chat endpoint.
  - Async execution via LangGraph `ainvoke`.
- Gemini LLM:
  - Client với API key rotation (`llm_gemini.py`).
  - Lazy per-call, retry + rotate key; model default `gemini-2.5-flash-lite`.
- Cohere Reranker:
  - Dùng để rerank candidates từ Milvus.

## APIs (chính)
- Auth: POST /api/v1/auth/register, /login; GET /me.
- Conversations: GET/POST /api/v1/conversations, GET/DELETE /api/v1/conversations/{id}.
- Chat: POST /api/v1/chat (tự tạo conversation nếu chưa có).
- Health: GET /, /health.

## Frontend UX
- Dark theme, sidebar conversations, multi-conversation support.
- Per-conversation state (messages/input/loading) tránh nhiễu giữa các tab chat.
- Session expiry modal + activity tracker (reset timer mỗi tương tác).

## Configuration (chính)
- `.env` backend: DB configs, JWT secrets, token expiry, RAG configs (E5, Milvus, Neo4j, Gemini).
- `.env` frontend: VITE_API_URL, optional VITE_INACTIVITY_TIMEOUT_MINUTES.

## Key Strengths (ngắn gọn)
- Kiến trúc rõ ràng (clean layers, LangGraph).
- Hybrid retrieval (graph + vector + rerank).
- Model reuse (E5 singleton), async pipeline.
- Safety routing (high-risk handling) và multilingual (VI/EN).

## Ghi chú đường dẫn
- Backend entry: `backend/main.py`
- Workflow: `backend/src/rag/workflow/workflow.py`
- Embeddings: `backend/src/rag/vectors/embeddings.py`
- LLM client: `backend/src/rag/llm/llm_gemini.py`
- Chat service: `backend/src/services/chat_service.py`
- Frontend: `frontend/src/App.tsx`, `frontend/src/api.ts`

