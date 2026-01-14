# 📋 KẾ HOẠCH TRIỂN KHAI: OPTION 3 - Persist + Smart Reset (Simplified)

**Version:** 1.0  
**Date:** December 21, 2025  
**Scope:** Slot persistence với topic tracking (không có topic fallback)

---

## 🎯 MỤC TIÊU

### Features Implement:
- ✅ Lưu slots theo topic vào Database
- ✅ Topic change → Archive old topic → Start new topic với fresh slots
- ✅ Slots accumulate trong cùng 1 topic
- ✅ Persist slots qua nhiều turns/sessions

### Features KHÔNG Implement (Simplified):
- ❌ Topic fallback (quay lại topic cũ)
- ❌ Topic switching detection nâng cao
- ❌ Multi-topic trong 1 query
- ❌ Topic merging

---

## 📐 KIẾN TRÚC

```
┌─────────────────────────────────────────────────────────────┐
│ DATABASE LAYER                                               │
├─────────────────────────────────────────────────────────────┤
│ Conversation Table:                                          │
│   - current_topic_id: String (nullable)                     │
│   - topics: JSON (nullable)                                 │
│                                                             │
│ Topics Structure:                                           │
│ {                                                           │
│   "topic_1": {                                              │
│     "name": "work stress",                                  │
│     "slots": {"emotion": "stressed", "trigger": "work"},    │
│     "created_turn": 1,                                      │
│     "ended_turn": 5,                                        │
│     "active": false                                         │
│   },                                                        │
│   "topic_2": {                                              │
│     "name": "family issue",                                 │
│     "slots": {"emotion": "anxious"},                        │
│     "created_turn": 6,                                      │
│     "ended_turn": null,                                     │
│     "active": true                                          │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│ SERVICE LAYER (ChatService)                                  │
├─────────────────────────────────────────────────────────────┤
│ - Load current_topic_id + topics from DB                    │
│ - Get active topic's slots                                  │
│ - Pass to workflow                                          │
│ - Save updated topics after workflow                        │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│ WORKFLOW LAYER (LangGraph)                                   │
├─────────────────────────────────────────────────────────────┤
│ query_classifier → query_type = "topic_change"              │
│                                                             │
│ slot_filling → Use current topic's slots                    │
│                                                             │
│ conversation_memory → If topic_change:                      │
│   - Archive current topic (active=False)                    │
│   - Create new topic with fresh slots                       │
│   - Update current_topic_id                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 KẾ HOẠCH TRIỂN KHAI (6 BƯỚC)

### **BƯỚC 1: Database Migration** ⏱️ 30 phút

#### Công việc:
1. Tạo migration file
2. Thêm 2 columns vào `conversations` table:
   - `current_topic_id`: String, nullable
   - `topics`: JSON, nullable
3. Run migration

#### Files cần tạo/sửa:
- `backend/alembic/versions/xxx_add_topic_tracking.py` (NEW)

#### Commands:
```bash
cd backend
alembic revision -m "add_topic_tracking_to_conversation"
# Edit migration file
alembic upgrade head
```

#### Migration Script Template:
```python
"""add_topic_tracking_to_conversation

Revision ID: xxx
Revises: yyy
Create Date: 2025-12-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

def upgrade():
    op.add_column('conversations', 
        sa.Column('current_topic_id', sa.String(), nullable=True)
    )
    op.add_column('conversations',
        sa.Column('topics', JSON, nullable=True)
    )

def downgrade():
    op.drop_column('conversations', 'topics')
    op.drop_column('conversations', 'current_topic_id')
```

---

### **BƯỚC 2: Update DB Models** ⏱️ 15 phút

#### Công việc:
1. Thêm 2 fields vào Conversation model
2. (Optional) Thêm helper methods

#### Files cần sửa:
- `backend/src/db/db_models/conversation.py`

#### Changes:
```python
from sqlalchemy import Column, JSON, String

class Conversation(Base):
    __tablename__ = "conversations"
    
    # ... existing fields ...
    
    # ✨ NEW
    current_topic_id = Column(String, nullable=True)
    topics = Column(JSON, nullable=True)
    
    # ✨ OPTIONAL: Helper methods
    def get_active_topic(self):
        """Get currently active topic"""
        if not self.current_topic_id or not self.topics:
            return None
        return self.topics.get(self.current_topic_id)
    
    def get_active_slots(self):
        """Get slots from active topic"""
        topic = self.get_active_topic()
        return topic["slots"] if topic else {}
```

---

### **BƯỚC 3: Modify Workflow State** ⏱️ 15 phút

#### Công việc:
1. Add TopicInfo TypedDict
2. Add topic-related fields to KGState

#### Files cần sửa:
- `backend/src/rag/workflow/state.py`

#### Changes:
```python
from typing import TypedDict, Dict, Optional, List, Tuple

class TopicInfo(TypedDict):
    """Structure for a single topic"""
    name: str  # "work stress", "family issue"
    slots: Dict[str, str]  # {"emotion": "stressed", "trigger": "work"}
    created_turn: int  # Turn number when topic was created
    ended_turn: Optional[int]  # None if active, else turn number
    active: bool  # True if current topic, False if archived

class KGState(TypedDict):
    # ... existing fields ...
    
    # ✨ NEW: Topic tracking
    current_topic_id: Optional[str]  # "topic_1", "topic_2", etc.
    topics: Dict[str, TopicInfo]  # {"topic_1": {...}, "topic_2": {...}}
    current_turn: int  # Track turn number for topic lifecycle
```

---

### **BƯỚC 4: Modify Workflow Nodes** ⏱️ 1.5 giờ

#### 4.1. Update `slot_filling_node` ⏱️ 30 phút

**File:** `backend/src/rag/workflow/graph_nodes/slot_filling.py`

**Changes:**

**A. Load slots từ current topic:**
```python
async def slot_filling_node(state: KGState) -> dict:
    """
    Extract slots từ query + conversation context
    
    NEW: Load existing slots từ current topic (instead of empty dict)
    """
    # ✨ NEW: Load từ current topic
    current_topic_id = state.get("current_topic_id")
    topics = state.get("topics", {})
    
    if current_topic_id and current_topic_id in topics:
        filled_slots = topics[current_topic_id]["slots"].copy()
        logger.info(f"[SLOT] Loaded {len(filled_slots)} slots from {current_topic_id}")
    else:
        filled_slots = {}
        logger.info("[SLOT] No active topic, starting with empty slots")
    
    # ... existing extraction logic ...
    # (extract new slots, merge, check sufficiency)
    
    # ✨ NEW: Update topic's slots
    if current_topic_id and current_topic_id in topics:
        topics[current_topic_id]["slots"] = filled_slots
        logger.info(f"[SLOT] Updated {current_topic_id} with {len(filled_slots)} slots")
    
    return {
        "filled_slots": filled_slots,
        "topics": topics,  # ✨ Return updated topics
        "missing_required_slots": missing_required,
        "missing_optional_slots": missing_optional,
        "has_sufficient_slots": has_sufficient,
    }
```

---

#### 4.2. Update `conversation_memory_node` ⏱️ 45 phút

**File:** `backend/src/rag/workflow/graph_nodes/conversation_memory.py`

**Changes:**

**A. Handle topic_change (archive + create new):**
```python
async def conversation_memory_node(state: KGState) -> dict:
    """
    Update conversation buffer and summary based on query type
    
    NEW: Handle topic lifecycle (archive old, create new)
    """
    query_type = state.get("query_type")
    current_query = state.get("query")
    current_answer = state.get("answer")
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
    
    # ✨ NEW: Topic tracking
    current_topic_id = state.get("current_topic_id")
    topics = state.get("topics", {})
    current_turn = state.get("current_turn", 0)
    
    # Topic change: Archive old topic, create new topic
    if query_type == "topic_change":
        logger.info("[MEMORY] Topic changed detected")
        
        # 1. Archive old topic (if exists)
        if current_topic_id and current_topic_id in topics:
            topics[current_topic_id]["active"] = False
            topics[current_topic_id]["ended_turn"] = current_turn
            logger.info(f"[MEMORY] Archived {current_topic_id} at turn {current_turn}")
        
        # 2. Create new topic
        new_topic_id = f"topic_{len(topics) + 1}"
        new_topic_name = await extract_topic_name(current_query, buffer)
        
        topics[new_topic_id] = {
            "name": new_topic_name,
            "slots": {},  # Fresh slots for new topic
            "created_turn": current_turn,
            "ended_turn": None,
            "active": True,
        }
        logger.info(f"[MEMORY] Created {new_topic_id}: '{new_topic_name}'")
        
        # 3. Summarize all buffer + current pair
        all_pairs = buffer + [(current_query, current_answer)]
        new_summary = await summarize_conversation(all_pairs, summary)
        
        return {
            "conversation_buffer": [],  # Clear buffer
            "summary_context": new_summary,
            "current_topic_id": new_topic_id,  # ✨ Switch to new topic
            "topics": topics,  # ✨ Updated topics dict
            "filled_slots": {},  # ✨ Clear slots for new topic
            "missing_required_slots": list(REQUIRED_SLOTS),
            "missing_optional_slots": list(OPTIONAL_SLOTS),
            "has_sufficient_slots": False,
        }
    
    # Normal flow: Keep current topic, accumulate buffer
    new_buffer = buffer + [(current_query, current_answer)]
    
    # Summarize if buffer > 3
    if len(new_buffer) > 3:
        to_summarize = new_buffer[:-3]
        new_summary = await summarize_conversation(to_summarize, summary)
        new_buffer = new_buffer[-3:]
    else:
        new_summary = summary
    
    return {
        "conversation_buffer": new_buffer,
        "summary_context": new_summary,
        "current_topic_id": current_topic_id,  # ✨ Preserve
        "topics": topics,  # ✨ Preserve
        "filled_slots": state.get("filled_slots", {}),  # ✨ Preserve
    }
```

**B. Add helper function:**
```python
async def extract_topic_name(query: str, buffer: List[Tuple[str, str]]) -> str:
    """
    Extract short topic name từ query + buffer context using LLM
    
    Example:
      query = "Giờ tôi muốn nói về vấn đề gia đình"
      buffer = [("Stress công việc...", "...")]
      → return "family issue"
    """
    from ...llm.gemini_model import model as gemini_model
    
    # Build context
    context = f"Current query: {query}\n"
    if buffer:
        last_queries = [q for q, _ in buffer[-3:]]
        context += f"Previous queries: {', '.join(last_queries)}"
    
    prompt = f"""
Extract a SHORT topic name (2-4 words) from the following conversation context.

{context}

Return ONLY the topic name in English, lowercase, no explanation.
Examples: "work stress", "family issue", "relationship problem", "anxiety management"

Topic name:"""
    
    try:
        response = await gemini_model.agenerate_content(prompt)
        topic_name = response.text.strip().lower()
        logger.info(f"[MEMORY] Extracted topic name: {topic_name}")
        return topic_name
    except Exception as e:
        logger.error(f"[MEMORY] Error extracting topic name: {e}")
        return "general mental health"  # Fallback
```

---

#### 4.3. Update `query_rewriter_node` ⏱️ 15 phút

**File:** `backend/src/rag/workflow/graph_nodes/query_rewriter.py`

**Changes:**

**Add topic context to rewriting prompt:**
```python
async def query_rewriter_node(state: KGState) -> dict:
    """
    Rewrite query combining slots + conversation context
    
    NEW: Add topic context for better rewriting
    """
    enhanced_query = state.get("enhanced_query") or state.get("query_en")
    filled_slots = state.get("filled_slots", {})
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
    
    # ✨ NEW: Add topic context
    current_topic_id = state.get("current_topic_id")
    topics = state.get("topics", {})
    
    topic_context = ""
    if current_topic_id and current_topic_id in topics:
        topic_name = topics[current_topic_id]["name"]
        topic_context = f"Current topic: {topic_name}\n"
    
    # Build slot context
    slot_context = "\n".join([f"- {k}: {v}" for k, v in filled_slots.items()])
    
    # Build conversation context
    conv_context = ""
    if buffer:
        conv_context = "Recent conversation:\n" + "\n".join(
            [f"Q: {q}\nA: {a}" for q, a in buffer[-3:]]
        )
    
    # LLM rewrite với topic context
    prompt = f"""
{topic_context}
Original query: {enhanced_query}

User's situation:
{slot_context}

{conv_context}

Summary of older conversation: {summary}

Rewrite the query to be more comprehensive and detailed for retrieval...
"""
    
    rewritten = await llm_rewrite(prompt)
    
    return {"rewritten_query": rewritten}
```

---

### **BƯỚC 5: Modify ChatService** ⏱️ 1 giờ

#### 5.1. Update `create_message()` method

**File:** `backend/src/services/chat_service.py`

**Changes:**

```python
async def create_message(
    self,
    conversation_id: str,
    content: str,
    user_id: str,
):
    """
    Create new message and run workflow
    
    NEW: Load and save topics for slot persistence
    """
    # 1. Load conversation
    conversation = await self.conversation_repo.get_by_id(conversation_id)
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found")
    
    # ✨ NEW: Load topics
    current_topic_id = conversation.current_topic_id
    topics = conversation.topics or {}
    
    logger.info(f"[CHAT] Loaded topics: current={current_topic_id}, total={len(topics)}")
    
    # Get active topic's slots
    active_slots = {}
    if current_topic_id and current_topic_id in topics:
        active_slots = topics[current_topic_id]["slots"]
        logger.info(f"[CHAT] Active topic '{topics[current_topic_id]['name']}' has {len(active_slots)} slots")
    
    # 2. Load messages for buffer
    messages = await self.message_repo.get_by_conversation(conversation_id)
    buffer, summary = self._build_conversation_buffer(messages)
    
    # ✨ NEW: Calculate current turn
    current_turn = len(messages) + 1
    logger.info(f"[CHAT] Current turn: {current_turn}")
    
    # 3. Run workflow with topics
    result = await run_graph(
        question=content,
        conversation_buffer=buffer,
        summary_context=summary,
        current_topic_id=current_topic_id,  # ✨ NEW
        topics=topics,  # ✨ NEW
        current_turn=current_turn,  # ✨ NEW
    )
    
    # 4. ✨ NEW: Save updated topics to DB
    updated_topic_id = result["state"].get("current_topic_id")
    updated_topics = result["state"].get("topics", {})
    
    if updated_topic_id != current_topic_id or updated_topics != topics:
        conversation.current_topic_id = updated_topic_id
        conversation.topics = updated_topics
        conversation.updated_at = datetime.now()
        await self.db.commit()
        logger.info(f"[CHAT] Saved topics: current={updated_topic_id}, total={len(updated_topics)}")
    
    # 5. Save messages (existing logic)
    user_message = await self.message_repo.create(
        conversation_id=conversation_id,
        role="user",
        content=content,
    )
    
    bot_message = await self.message_repo.create(
        conversation_id=conversation_id,
        role="assistant",
        content=result["answer"],
    )
    
    return result
```

---

#### 5.2. Update `run_graph()` signature

**File:** `backend/src/rag/engine.py`

**Changes:**

```python
async def run_graph(
    question: str,
    conversation_buffer: List[Tuple[str, str]] = None,
    summary_context: str = None,
    current_topic_id: str = None,  # ✨ NEW
    topics: Dict = None,  # ✨ NEW
    current_turn: int = 0,  # ✨ NEW
):
    """
    Run the Knowledge Graph RAG workflow
    
    NEW: Accept topic tracking parameters
    """
    state = {
        "query": question,
        "conversation_buffer": conversation_buffer or [],
        "summary_context": summary_context or "",
        "current_topic_id": current_topic_id,  # ✨ NEW
        "topics": topics or {},  # ✨ NEW
        "current_turn": current_turn,  # ✨ NEW
    }
    
    logger.info(f"[ENGINE] Running workflow with topic: {current_topic_id}, turn: {current_turn}")
    
    result = await kg_graph.ainvoke(state)
    
    return {
        "answer": result.get("answer", ""),
        "state": result,
    }
```

---

### **BƯỚC 6: Testing** ⏱️ 1 giờ

#### 6.1. Unit Tests

**File:** `backend/tests/test_topic_tracking.py` (NEW)

**Test cases:**
```python
import pytest
from backend.src.rag.workflow.graph_nodes.conversation_memory import extract_topic_name

@pytest.mark.asyncio
async def test_first_message_creates_topic():
    """Test: First message creates topic_1"""
    # Setup: Empty conversation
    # Action: Send "Tôi stress vì công việc"
    # Assert: 
    #   - topics["topic_1"] exists
    #   - current_topic_id = "topic_1"
    #   - topic_1.active = True

@pytest.mark.asyncio
async def test_follow_up_accumulates_slots():
    """Test: Follow-up stays in same topic, accumulates slots"""
    # Setup: topic_1 with {"emotion": "stressed"}
    # Action: Send "Kéo dài 2 tuần rồi"
    # Assert:
    #   - Still in topic_1
    #   - Slots = {"emotion": "stressed", "duration": "2 weeks"}

@pytest.mark.asyncio
async def test_topic_change_archives_and_creates_new():
    """Test: Topic change archives old, creates new topic"""
    # Setup: topic_1 with 5 turns
    # Action: Send "Giờ tôi muốn nói về gia đình"
    # Assert:
    #   - topic_1.active = False
    #   - topic_1.ended_turn = 6
    #   - topic_2 exists
    #   - topic_2.active = True
    #   - topic_2.slots = {} (empty)

@pytest.mark.asyncio
async def test_new_topic_starts_with_empty_slots():
    """Test: New topic has empty slots"""
    # Setup: topic_1 with {"emotion": "stressed", "trigger": "work"}
    # Action: Topic change to topic_2
    # Assert:
    #   - topic_2.slots = {}
    #   - topic_1.slots unchanged (archived)

@pytest.mark.asyncio
async def test_topics_persist_across_requests():
    """Test: Topics persist in DB"""
    # Action 1: Create topic_1
    # Action 2: New request, add slots
    # Assert: Slots from Action 1 still present
```

---

#### 6.2. Integration Test (Manual)

**Test Scenario:**
```
Turn 1: "Tôi stress vì công việc"
Expected:
  - Create topic_1: "work stress"
  - Slots: {"emotion": "stressed", "trigger": "work"}
  - current_topic_id = "topic_1"
  - topics = {"topic_1": {...}}

Turn 2: "Kéo dài 2 tuần rồi"
Expected:
  - Stay in topic_1
  - Slots: {"emotion": "stressed", "trigger": "work", "duration": "2 weeks"}
  - current_topic_id = "topic_1" (unchanged)

Turn 3: "Giờ tôi muốn nói về vấn đề gia đình"
Expected:
  - topic_1.active = False, ended_turn = 3
  - Create topic_2: "family issue"
  - Slots: {} (empty)
  - current_topic_id = "topic_2"
  - topics = {"topic_1": {...}, "topic_2": {...}}

Turn 4: "Tôi cảm thấy cô đơn"
Expected:
  - Stay in topic_2
  - Slots: {"emotion": "lonely"}
  - current_topic_id = "topic_2" (unchanged)

Turn 5: Restart server, send "Vẫn còn cô đơn"
Expected:
  - Load topic_2 from DB
  - Slots: {"emotion": "lonely"} (persisted!)
```

**How to test:**
```bash
# 1. Start server
cd backend
python main.py

# 2. Use Postman or curl
# Turn 1
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "test_123", "message": "Tôi stress vì công việc"}'

# Check DB:
# SELECT current_topic_id, topics FROM conversations WHERE id = 'test_123';

# Turn 2-5: Continue testing...
```

---

## 📊 CHECKLIST TỔNG HỢP

### Phase 1: Database Setup
- [ ] Create migration file
- [ ] Add `current_topic_id` column (String, nullable)
- [ ] Add `topics` column (JSON, nullable)
- [ ] Run `alembic upgrade head`
- [ ] Verify columns exist in DB

### Phase 2: Models & State
- [ ] Update `Conversation` model with 2 new fields
- [ ] (Optional) Add helper methods: `get_active_topic()`, `get_active_slots()`
- [ ] Add `TopicInfo` TypedDict to `state.py`
- [ ] Add `current_topic_id`, `topics`, `current_turn` to `KGState`

### Phase 3: Workflow Nodes
- [ ] **slot_filling_node**
  - [ ] Load slots from `topics[current_topic_id]["slots"]`
  - [ ] Update topic's slots after extraction
  - [ ] Return updated `topics` dict
- [ ] **conversation_memory_node**
  - [ ] Handle `topic_change`: archive old + create new
  - [ ] Implement `extract_topic_name()` helper
  - [ ] Preserve topics on normal flow
  - [ ] Clear slots on topic change
- [ ] **query_rewriter_node**
  - [ ] Add topic context to rewriting prompt

### Phase 4: Service Layer
- [ ] **ChatService.create_message()**
  - [ ] Load `current_topic_id` and `topics` from DB
  - [ ] Get active topic's slots
  - [ ] Calculate `current_turn`
  - [ ] Pass topics to `run_graph()`
  - [ ] Save updated topics to DB after workflow
- [ ] **engine.py**
  - [ ] Update `run_graph()` signature with 3 new params
  - [ ] Initialize state with topic fields

### Phase 5: Testing
- [ ] Write unit tests for topic lifecycle
- [ ] Test 4-turn integration scenario
- [ ] Verify topics persist in DB (check with SQL)
- [ ] Verify slots accumulate within topic
- [ ] Verify slots reset on topic change
- [ ] Test server restart (persistence across sessions)

---

## ⏱️ TIMELINE ESTIMATE

| Phase | Time | Notes |
|-------|------|-------|
| Migration + Models | 45 min | Straightforward DB work |
| State + slot_filling | 30 min | Simple changes |
| conversation_memory | 45 min | Most complex (topic lifecycle) |
| query_rewriter | 15 min | Minor enhancement |
| ChatService + Engine | 1 hour | Integration work |
| Testing | 1 hour | Write + run tests |
| Buffer | 30 min | Debug + fixes |
| **TOTAL** | **4.5-5 hours** | Full implementation |

---

## 🚀 RECOMMENDED ORDER

```
1. Migration → Models
   (Can test DB access immediately)

2. State → slot_filling_node
   (Can test in-memory slot loading)

3. conversation_memory_node
   (Test topic creation/archiving)

4. query_rewriter_node
   (Minor change, quick win)

5. ChatService + Engine
   (Integration, test end-to-end)

6. Testing
   (Verify all scenarios)
```

---

## 🎯 SUCCESS CRITERIA

### ✅ Database
- Conversations table có 2 fields mới: `current_topic_id`, `topics`
- Topics structure đúng format JSON
- Data persists sau restart server

### ✅ Workflow
- Topic change → Archive old topic (active=False, ended_turn set)
- Topic change → Create new topic (active=True, slots={})
- Normal flow → Slots accumulate trong same topic
- Slots reset khi topic change

### ✅ Integration
- ChatService load topics từ DB
- ChatService save topics sau workflow
- Topics pass correctly qua workflow nodes
- State correctly updated ở mỗi node

### ✅ Testing
- 4-turn scenario pass
- Topics persist trong DB
- Slots accumulate correctly
- No data loss sau restart

---

## ⚠️ KNOWN LIMITATIONS

### Features KHÔNG Implement (By Design):
- ❌ **Topic fallback**: Không thể quay lại topic cũ
- ❌ **Topic switching detection nâng cao**: Chỉ rely on `query_classifier_node`
- ❌ **Multi-topic queries**: "Công việc stress và gia đình cũng vậy" → Chỉ handle 1 topic
- ❌ **Topic merging**: Không merge 2 topics thành 1
- ❌ **Keyword-based topic matching**: Không dùng keywords để match topics

### Lý do:
Đây là **simplified version** để:
- Giảm complexity (no multi-tier evaluation)
- Focus on core functionality (persistence + topic lifecycle)
- Easy to debug và maintain
- Có thể mở rộng sau (add topic fallback là Phase 2)

---

## 🔧 IMPLEMENTATION NOTES

### 1. Topic Name Extraction
- Dùng Gemini LLM để extract topic name
- Fallback: `"general mental health"` nếu LLM fail
- Format: lowercase, 2-4 words, English
- Examples: "work stress", "family issue", "relationship problem"

### 2. First Message Behavior
- Conversation mới: `topics = None`, `current_topic_id = None`
- Turn 1 sẽ tự động tạo `topic_1` (handled by workflow)
- Không cần special case trong ChatService

### 3. Topic ID Generation
- Simple counter: `topic_1`, `topic_2`, `topic_3`, ...
- ID trong scope của conversation (không global)
- Không reuse ID (kể cả khi archived)

### 4. Backward Compatibility
- Conversations cũ: `current_topic_id = None`, `topics = None`
- First message sau migration → Auto create `topic_1`
- Không cần data migration (lazy initialization)

### 5. Error Handling
- If topic extraction fails → Use fallback name
- If topic_id not found → Log warning, treat as new topic
- If DB save fails → Rollback transaction (existing behavior)

---

## 📚 RELATED DOCUMENTS

- **Current workflow:** `/backend/src/rag/workflow/workflow.py`
- **Slot definitions:** `/backend/src/rag/utils/slots.py`
- **State definition:** `/backend/src/rag/workflow/state.py`
- **Conversation memory:** `/backend/src/rag/workflow/graph_nodes/conversation_memory.py`
- **Slot filling:** `/backend/src/rag/workflow/graph_nodes/slot_filling.py`

---

## 🔄 NEXT STEPS (After Implementation)

### Phase 2 (Optional Future Enhancements):
1. **Topic fallback detection**
   - Add keyword matching
   - Add embedding similarity
   - Implement multi-tier evaluation

2. **Topic analytics**
   - Track topic frequency
   - Analyze slot extraction patterns
   - User journey mapping

3. **Advanced features**
   - Multi-topic queries
   - Topic merging
   - Smart topic suggestions

---

## ❓ QUESTIONS TO CLARIFY

Before implementation, confirm:

1. **Topic name language**: English or Vietnamese?
   - Current plan: English (for consistency)

2. **First message**: Always create topic_1?
   - Current plan: Yes

3. **Topic ID reuse**: Never reuse IDs?
   - Current plan: Never reuse (use counter)

4. **Migration strategy**: Lazy initialization OK?
   - Current plan: Yes (no data migration needed)

5. **Topic extraction failures**: Use fallback name?
   - Current plan: Yes ("general mental health")

---

**End of Plan**

Prepared by: AI Assistant  
For: Mental Health Hybrid RAG System  
Version: 1.0 - Simplified (No Topic Fallback)
