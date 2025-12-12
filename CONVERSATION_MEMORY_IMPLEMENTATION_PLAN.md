# Conversation Memory Implementation Plan

## ⚠️ QUAN TRỌNG: Nguyên tắc Implementation

**MỖI PHASE CHỈ LÀM ĐÚNG TÁC VỤ CỦA PHASE ĐÓ:**

1. **Đúng folder:** Mỗi tác vụ chỉ sửa/tạo files trong folder tương ứng
   - `utils/` → chỉ helper functions (KHÔNG gọi LLM)
   - `llm/answer_nodes/` → chỉ LLM nodes
   - `workflow/` → chỉ workflow nodes và state
   - `services/` → chỉ business logic
   - `retrieval/` → chỉ retrieval logic
   - `prompts/` → chỉ prompt files

2. **Không dồn hàm:** Không tạo thêm file mới hoặc thêm hàm vào file khác của folder khác mà không đúng tác vụ của nó.

3. **Không mix tasks:** Mỗi phase chỉ làm đúng tasks của phase đó, không làm trước tasks của phase sau

**LUÔN KIỂM TRA TRƯỚC KHI IMPLEMENT:**
- File này thuộc folder nào?
- Task này thuộc phase nào?
- Có đang làm đúng phase không?

---


## Tổng quan

Mục tiêu: Thêm conversation memory để chatbot có thể trả lời liên tục, xử lý follow-up answers, topic change, và off-topic questions.

---

## Files sẽ tạo mới

1. `backend/src/rag/utils/memory.py` - Helper functions
2. `backend/src/rag/llm/answer_nodes/query_classifier_node.py` - LLM classify query type
3. `backend/src/rag/llm/answer_nodes/conversation_memory_node.py` - Update buffer + summary
4. `backend/src/rag/prompts/query_classifier_prompt.yaml` - Prompt để classify
5. `backend/src/rag/prompts/conversation_summarize_prompt.yaml` - Prompts để summarize

---

## Files sẽ sửa đổi

1. `backend/src/rag/workflow/state.py` - Thêm conversation memory fields
2. `backend/src/services/chat_service.py` - Init buffer + summary
3. `backend/src/rag/engine.py` - Nhận buffer + summary parameters
4. `backend/src/rag/workflow/graph_nodes.py` - Thêm query_similarity_check_node, sửa graph_retrieval_node
5. `backend/src/rag/llm/answer_nodes/safety_check.py` - Conditional enhancement
6. `backend/src/rag/retrieval/graph_retrieval.py` - Support original_query parameter
7. `backend/src/rag/llm/answer_nodes/answer_with_graph.py` - Thêm buffer + summary vào prompt
8. `backend/src/rag/workflow/workflow.py` - Thêm nodes và update edges

---

## Implementation Phases

### Phase 1: Setup & Infrastructure ✅

**Mục đích:** Tạo buffer và summary_context, setup infrastructure

#### Task 1.1: Tạo `utils/memory.py`
- Helper functions (không gọi LLM)
- Format buffer, summary
- Tính similarity (embedding)
- Build enhanced query
- Quản lý buffer

#### Task 1.2: Update `state.py`
- Thêm fields: `conversation_buffer`, `summary_context`, `previous_follow_up_questions`, `query_type`, `should_enhance_query`, `query_similarity`, `is_topic_change`, `is_off_topic`

#### Task 1.3: Update `chat_service.py`
- Lấy messages từ DB trước khi save current message
- Init buffer + summary từ existing messages
- Truyền buffer + summary vào `run_graph()`

#### Task 1.4: Update `engine.py`
- Thêm parameters: `conversation_buffer`, `summary_context`
- Init state với buffer + summary

---

### Phase 2: Query Similarity Check (Task 1)

#### Task 2.1: Tạo `query_similarity_check_node` trong `graph_nodes.py`
- Tính similarity (embedding)
- Nếu >= 0.8 → `follow_up` (skip LLM)
- Nếu < 0.8 → gọi `classify_query_node` (LLM)

#### Task 2.2: Tạo `query_classifier_node.py`
- LLM classify: `topic_change` vs `off_topic` vs `follow_up`
- Chỉ chạy khi similarity < 0.8

#### Task 2.3: Tạo `query_classifier_prompt.yaml`
- Prompt để classify query type

---

### Phase 3: Conditional Safety Check (Task 2)

#### Task 3.1: Sửa `safety_check.py`
- Check `should_enhance_query` và `query_type`
- Enhance query nếu `follow_up` hoặc `topic_change`
- Không enhance nếu `off_topic`

---

### Phase 4: Conditional Query Enhancement (Task 1 cont.)

#### Task 4.1: Sửa `graph_retrieval_node` trong `graph_nodes.py`
- Conditional enhancement dựa trên `should_enhance_query` và `query_type`

#### Task 4.2: Sửa `graph_retrieval.py`
- Support `original_query` parameter
- Encode enhanced query cho Milvus
- Rerank với original query

---

### Phase 5: Enhance Context (Task 3)

#### Task 5.1: Sửa `answer_with_graph.py`
- Thêm buffer + summary vào prompt
- Combine: graph_context + slot_info + summary + buffer

---

### Phase 6: Topic Change Handling (Task 5)

#### Task 6.1: Tạo `conversation_memory_node.py`
- Update buffer + summary
- Handle topic change: summarize & clear buffer
- Normal flow: add to buffer, summarize if full

#### Task 6.2: Tạo summarize functions trong `conversation_memory_node.py`
- `summarize_pair()` - Summarize 1 Q&A pair
- `summarize_buffer()` - Summarize nhiều Q&A pairs

#### Task 6.3: Tạo `conversation_summarize_prompt.yaml`
- Prompts cho summarize pair và buffer

---

### Phase 7: Workflow Integration

#### Task 7.1: Sửa `workflow.py`
- Thêm nodes: `query_similarity_check`, `classify_query`, `conversation_memory`
- Update edges theo workflow mới

---

## Workflow cuối cùng

```
1. translate_question
   ↓
2. query_similarity_check_node
   - Nếu không có buffer/summary → skip, không enhance
   - Nếu có buffer/summary:
     * Tính similarity (embedding)
     * >= 0.8 → follow_up (skip LLM)
     * < 0.8 → classify_query_node (LLM)
   ↓
3. classify_query_node (conditional, chỉ chạy nếu similarity < 0.8)
   - Classify: topic_change vs off_topic vs follow_up
   ↓
4. safety_check_node
   - follow_up/topic_change → enhanced query
   - off_topic → original query
   ↓
5. route_after_safety_check
   - off_topic → not_mental_health → END
   - mental health → slot_filling
   ↓
6. slot_filling
   ↓
7. graph_retrieval_node
   - follow_up/topic_change → enhanced query
   - off_topic → original query (nhưng đã bị reject)
   ↓
8. answer_with_graph_node
   - Thêm buffer + summary vào prompt
   ↓
9. conversation_memory_node
   - topic_change → summarize & clear buffer
   - follow_up → add to buffer
   - off_topic → không add (đã reject)
   ↓
10. translate_answer
```

---

## Key Points

1. **Hybrid similarity check:** >= 0.8 skip LLM, < 0.8 gọi LLM
2. **Chỉ 3 query types:** `follow_up`, `topic_change`, `off_topic`
3. **First message:** không check similarity, không enhance query
4. **Topic change:** summarize old buffer, clear, start new topic
5. **Off-topic:** không enhance query, reject ở safety check, không add vào buffer

---

## Checklist

- [x] Phase 1: Setup & Infrastructure ✅ COMPLETED
  - [x] Task 1.1: Tạo utils/memory.py
  - [x] Task 1.2: Update state.py
  - [x] Task 1.3: Update chat_service.py
  - [x] Task 1.4: Update engine.py
- [ ] Phase 2: Query Similarity Check
- [ ] Phase 3: Conditional Safety Check
- [ ] Phase 4: Conditional Query Enhancement
- [ ] Phase 5: Enhance Context
- [ ] Phase 6: Topic Change Handling
- [ ] Phase 7: Workflow Integration

