# Persistent State Implementation Guide

## 📋 Overview

Workflow hiện tại đã được upgrade để support **persistent state** qua các lần chat bằng **PostgreSQL Checkpointer** của LangGraph.

### ✅ Changes Summary

1. **Created** [`backend/src/rag/workflow/checkpointer.py`](backend/src/rag/workflow/checkpointer.py) - PostgreSQL checkpointer manager
2. **Updated** [`backend/src/rag/workflow/workflow.py`](backend/src/rag/workflow/workflow.py) - Added checkpointer support + new functions
3. **Refactored** [`backend/src/rag/engine.py`](backend/src/rag/engine.py) - New conversation-based API
4. **Updated** [`backend/requirements.txt`](backend/requirements.txt) - Added psycopg dependencies

---

## 🔑 Key Features

### State Persistence
- ✅ **State tự động lưu** sau mỗi node execution
- ✅ **State persist qua server restarts** (PostgreSQL)
- ✅ **Thread-based isolation** (mỗi conversation_id = 1 thread)
- ✅ **No manual state management** needed

### What Gets Persisted
- `filled_slots` - Extracted structured information
- `conversation_buffer` - Last 3 conversation pairs
- `conversation_summary` - Summary of older messages
- `detected_disease` - Diagnosed disease (if any)
- `query_type` - follow_up, topic_change, off_topic
- All other KGState fields

---

## 📦 Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs:
- `psycopg>=3.1.0` - PostgreSQL adapter for Python
- `psycopg-pool>=3.1.0` - Connection pooling

### 2. Environment Variables

Add to your `.env` file:

```bash
# PostgreSQL Checkpoint Configuration
# Option 1: Use same database as main app (recommended for simplicity)
POSTGRES_CHECKPOINT_URI=${DATABASE_URL}

# Option 2: Use separate database for checkpoints (recommended for production)
# POSTGRES_CHECKPOINT_URI=postgresql://user:password@localhost:5432/langgraph_checkpoints
```

### 3. Database Setup

The checkpointer will **automatically create** required tables on first run:

```sql
-- Tables created automatically by checkpointer.setup()
CREATE TABLE checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,  -- ← State stored here
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    value JSONB,  -- ← Incremental state changes
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
```

**No manual migration needed!** Tables are created automatically.

---

## 🚀 Usage

### New API (Recommended)

```python
from src.rag.engine import run_rag_workflow

# Turn 1: User's first message
result1 = await run_rag_workflow(
    conversation_id="abc-123-def-456",  # From database
    user_message="Tôi buồn quá",
    user_id="user_001"
)

print(result1["answer"])
print(result1["filled_slots"])  # {"emotion": "buồn", ...}

# Turn 2: Follow-up message (SAME conversation_id)
result2 = await run_rag_workflow(
    conversation_id="abc-123-def-456",  # ← Same ID!
    user_message="Tôi ngủ không được"
)

# State restored automatically from PostgreSQL checkpoint!
print(result2["filled_slots"])  
# {"emotion": "buồn", "sleep": "không được", ...}
```

### How It Works

```
Turn 1: conversation_id="abc-123"
├─ thread_id = "conversation_abc-123"
├─ Checkpointer: No existing checkpoint → Create new
├─ translate_question → Save checkpoint to PostgreSQL
├─ query_similarity_check → Save checkpoint
├─ slot_filling → Save checkpoint (filled_slots: {emotion: "buồn"})
├─ ... (all nodes save checkpoints)
└─ conversation_memory → Final checkpoint saved

Turn 2: conversation_id="abc-123" (SAME!)
├─ thread_id = "conversation_abc-123"
├─ Checkpointer: Load checkpoint from PostgreSQL
│   ├─ filled_slots: {emotion: "buồn"}  ← RESTORED!
│   ├─ conversation_buffer: [...]  ← RESTORED!
│   └─ conversation_summary: "..."  ← RESTORED!
├─ Merge with new initial_state: {question: "Tôi ngủ không được"}
├─ Continue workflow with full context
├─ slot_filling → Update filled_slots: {emotion: "buồn", sleep: "không được"}
└─ ... (workflow continues with full state)

[Server Restart]

Turn 3: conversation_id="abc-123" (SAME!)
├─ State still intact in PostgreSQL! ✅
└─ All previous data restored automatically
```

---

## 📝 API Reference

### Main Functions

#### `run_rag_workflow()`

**Main entry point** for conversational RAG with persistent state.

```python
async def run_rag_workflow(
    conversation_id: str,
    user_message: str,
    user_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
```

**Parameters:**
- `conversation_id` - UUID from database (maps to thread_id)
- `user_message` - User's message
- `user_id` - Optional user ID
- `**kwargs` - Additional initial state fields

**Returns:** Final state dict with:
- `answer` - Generated response
- `filled_slots` - Extracted slots
- `conversation_buffer` - Recent history
- `conversation_summary` - Summary
- `detected_language` - "vi" or "en"
- `is_high_risk` - Risk flag
- `detected_disease` - Disease name (if any)

#### `get_current_conversation_state()`

Get current checkpoint state for debugging/UI.

```python
state = await get_current_conversation_state(conversation_id)
if state:
    print("Slots:", state.get("filled_slots"))
    print("Buffer:", state.get("conversation_buffer"))
```

#### `get_full_conversation_history()`

Get all checkpoints (for debugging/auditing).

```python
history = await get_full_conversation_history(conversation_id, limit=10)
for checkpoint in history:
    print("Node:", checkpoint["metadata"]["source"])
    print("State:", checkpoint["channel_values"])
```

---

## 🔄 Migration from Old API

### Before (Manual State Management)

```python
from src.rag.workflow.workflow import build_kg_graph
from src.rag.engine import run_graph

# Manual buffer/summary management
graph = build_kg_graph()
result = await run_graph(
    graph,
    question="User message",
    conversation_buffer=manually_managed_buffer,
    summary_context=manually_managed_summary
)

# You need to manually save buffer/summary to database
# State is lost on server restart
```

### After (Automatic Persistence)

```python
from src.rag.engine import run_rag_workflow

# Everything automatic!
result = await run_rag_workflow(
    conversation_id=conversation_id,  # From database
    user_message="User message"
)

# State automatically saved to PostgreSQL
# State survives server restarts
# No manual management needed
```

---

## 🎯 Integration with Chat Service

### Update your chat endpoint:

```python
from fastapi import APIRouter, HTTPException
from src.rag.engine import run_rag_workflow
from src.schemas.chat import ChatRequest

router = APIRouter()

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint with persistent state
    
    Request body:
    {
        "conversation_id": "uuid-from-database",
        "message": "User message",
        "user_id": "optional-user-id"
    }
    """
    try:
        result = await run_rag_workflow(
            conversation_id=request.conversation_id,
            user_message=request.message,
            user_id=request.user_id,
        )
        
        return {
            "answer": result.get("answer"),
            "conversation_id": request.conversation_id,
            "detected_language": result.get("detected_language"),
            "is_high_risk": result.get("is_high_risk", False),
            "filled_slots": result.get("filled_slots", {}),
            "detected_disease": result.get("detected_disease", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/state/{conversation_id}")
async def get_state(conversation_id: str):
    """Get current conversation state"""
    from src.rag.engine import get_current_conversation_state
    
    state = await get_current_conversation_state(conversation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "conversation_id": conversation_id,
        "state": state,
    }
```

---

## 🐛 Debugging

### Check if checkpointer is working:

```python
import logging
logging.basicConfig(level=logging.INFO)

# Run workflow - you should see:
# INFO: Initializing PostgreSQL checkpointer...
# INFO: ✓ Database tables verified: checkpoints, checkpoint_writes
# INFO: Compiling workflow graph with PostgreSQL checkpointer
# INFO: [WORKFLOW] Starting execution for conversation_id=...
```

### Query checkpoints directly:

```sql
-- See all active conversations
SELECT DISTINCT thread_id, COUNT(*) as checkpoint_count
FROM checkpoints
GROUP BY thread_id
ORDER BY MAX(checkpoint::jsonb->>'created_at') DESC;

-- See checkpoints for specific conversation
SELECT 
    checkpoint_id,
    checkpoint::jsonb->>'channel_values' as state,
    metadata::jsonb->>'source' as node_name
FROM checkpoints
WHERE thread_id = 'conversation_abc-123'
ORDER BY checkpoint_id DESC
LIMIT 10;
```

### Common Issues:

1. **Tables not created**: Check DATABASE_URL or POSTGRES_CHECKPOINT_URI
2. **State not persisting**: Verify thread_id format (`conversation_{uuid}`)
3. **Connection errors**: Check PostgreSQL connection pool settings

---

## 📊 Performance Considerations

### Connection Pooling

Default settings in checkpointer:

```python
ConnectionPool(
    max_size=20,      # Max connections
    min_size=5,       # Min connections kept alive
    timeout=30,       # Connection timeout (seconds)
    max_idle=300,     # Max idle time (5 min)
    max_lifetime=3600 # Max lifetime (1 hour)
)
```

### Database Size Management

Checkpoints can grow over time. Consider:

1. **TTL cleanup** (periodic cleanup job):
```sql
-- Delete checkpoints older than 30 days
DELETE FROM checkpoints
WHERE (checkpoint::jsonb->>'created_at')::timestamp < NOW() - INTERVAL '30 days';

DELETE FROM checkpoint_writes
WHERE (thread_id, checkpoint_id) NOT IN (
    SELECT thread_id, checkpoint_id FROM checkpoints
);
```

2. **Archive old conversations**:
```sql
-- Archive to separate table
CREATE TABLE checkpoints_archive AS
SELECT * FROM checkpoints
WHERE (checkpoint::jsonb->>'created_at')::timestamp < NOW() - INTERVAL '90 days';

DELETE FROM checkpoints
WHERE checkpoint_id IN (SELECT checkpoint_id FROM checkpoints_archive);
```

---

## ✅ Testing

### Test persistent state:

```python
import asyncio
from src.rag.engine import run_rag_workflow, get_current_conversation_state

async def test_persistent_state():
    conv_id = "test-123-456"
    
    # Turn 1
    result1 = await run_rag_workflow(
        conversation_id=conv_id,
        user_message="Tôi buồn quá"
    )
    print("Turn 1 slots:", result1.get("filled_slots"))
    
    # Check state
    state = await get_current_conversation_state(conv_id)
    print("Saved state:", state.get("filled_slots"))
    
    # Turn 2
    result2 = await run_rag_workflow(
        conversation_id=conv_id,
        user_message="Tôi ngủ không được"
    )
    print("Turn 2 slots:", result2.get("filled_slots"))
    # Should include both turns!
    
asyncio.run(test_persistent_state())
```

---

## 📚 Additional Resources

- [LangGraph Checkpointer Docs](https://langchain-ai.github.io/langgraph/how-tos/persistence/)
- [PostgresSaver API](https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.postgres.PostgresSaver)
- [State Management Guide](STATE_MANAGEMENT_GUIDE.md)

---

## 🎉 Summary

✅ State now persists across conversation turns  
✅ State survives server restarts (PostgreSQL)  
✅ Thread-based isolation per conversation  
✅ No manual state management needed  
✅ Backward compatible (old API still works)  

**Ready to use!** Chỉ cần gọi `run_rag_workflow()` với `conversation_id` và mọi thứ tự động!
