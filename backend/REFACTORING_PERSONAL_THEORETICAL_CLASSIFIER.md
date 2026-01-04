# Refactoring: Personal/Theoretical Classifier

## 🎯 Mục đích

Tách logic phân loại **Personal/Theoretical** ra khỏi node `classify_query` để:
1. **Separation of Concerns**: Tách biệt 2 concerns khác nhau
2. **Clearer Logic**: Dễ hiểu và maintain hơn
3. **Handle Edge Cases**: Xử lý được các trường hợp phức tạp

---

## 📊 Thay đổi

### **Trước khi refactor:**

```
translate_question
↓
classify_query (4 loại: theoretical, follow_up, topic_change, off_topic)
↓
if off_topic → not_mental_health
↓
safety_check
↓
if query_type == "theoretical" → theoretical_retrieval
if personal → slot_filling
```

**Vấn đề:**
- Node `classify_query` làm 2 việc: phân loại conversation flow + query nature
- Không thể biểu diễn "follow-up theoretical" hoặc "topic_change personal"
- Logic routing phức tạp

---

### **Sau khi refactor:**

```
translate_question
↓
classify_query (3 loại: follow_up, topic_change, off_topic)
↓
if off_topic → not_mental_health
↓
personal_theoretical_classifier (2 loại: personal, theoretical) ⭐ NEW
↓
if theoretical → theoretical_retrieval (skip safety + slots)
if personal → safety_check → slot_filling → diagnostic flow
```

**Lợi ích:**
- ✅ Mỗi node có 1 trách nhiệm rõ ràng
- ✅ Có thể kết hợp: follow_up + theoretical, topic_change + personal
- ✅ Routing logic đơn giản hơn

---

## 📝 Chi tiết thay đổi

### **1. File mới:**

#### `src/rag/prompts/personal_theoretical_classifier_prompt.yaml`
- Prompt để phân loại personal vs theoretical
- Xử lý edge cases (follow-up theoretical, implicit personal)

#### `src/rag/llm/answer_nodes/personal_theoretical_classifier.py`
- Logic function gọi LLM với prompt mới
- Trả về `query_nature` và `reasoning`

#### `src/rag/workflow/graph_nodes/personal_theoretical_classifier.py`
- Node wrapper cho logic function
- Tích hợp vào workflow

---

### **2. File đã sửa:**

#### `src/rag/prompts/query_classifier_prompt.yaml`
**Thay đổi:**
- Bỏ `theoretical` khỏi danh sách query_type
- Chỉ còn 3 loại: `follow_up`, `topic_change`, `off_topic`
- Cập nhật priority rules

**Trước:**
```yaml
Valid values: "theoretical", "follow_up", "topic_change", "off_topic"
```

**Sau:**
```yaml
Valid values: "follow_up", "topic_change", "off_topic"
```

---

#### `src/rag/llm/answer_nodes/query_classifier.py`
**Thay đổi:**
- Bỏ `"theoretical"` khỏi `should_enhance_query` logic

**Trước:**
```python
should_enhance_query = (query_type in ["follow_up", "topic_change", "theoretical"])
```

**Sau:**
```python
should_enhance_query = (query_type in ["follow_up", "topic_change"])
```

---

#### `src/rag/workflow/state.py`
**Thay đổi:**
- Thêm field `query_nature` vào KGState

**Trước:**
```python
query_type: Optional[str]  # "follow_up" | "topic_change" | "off_topic"
```

**Sau:**
```python
query_type: Optional[str]  # "follow_up" | "topic_change" | "off_topic"
query_nature: Optional[str]  # "personal" | "theoretical"
```

---

#### `src/rag/workflow/workflow.py`
**Thay đổi:**

1. **Import node mới:**
```python
from .graph_nodes import (
    ...
    personal_theoretical_classifier_node,  # NEW
    ...
)
```

2. **Routing functions:**

**Bỏ `route_after_classify_query` cũ:**
```python
def route_after_classify_query(...) -> Literal["safety_check", "not_mental_health"]:
    if query_type == "off_topic":
        return "not_mental_health"
    return "safety_check"
```

**Thay bằng 2 routing functions:**
```python
def route_after_classify_query(...) -> Literal["personal_theoretical_classifier", "not_mental_health"]:
    if query_type == "off_topic":
        return "not_mental_health"
    return "personal_theoretical_classifier"  # NEW

def route_after_personal_theoretical(...) -> Literal["theoretical_retrieval", "safety_check"]:
    if query_nature == "theoretical":
        return "theoretical_retrieval"
    return "safety_check"
```

**Đơn giản hóa `route_after_safety_check`:**
```python
# Trước:
def route_after_safety_check(...) -> Literal["crisis_response", "slot_filling", "theoretical_retrieval"]:
    if is_high_risk:
        return "crisis_response"
    if query_type == "theoretical":  # ← Check này đã di chuyển
        return "theoretical_retrieval"
    return "slot_filling"

# Sau:
def route_after_safety_check(...) -> Literal["crisis_response", "slot_filling"]:
    if is_high_risk:
        return "crisis_response"
    return "slot_filling"
```

3. **Workflow builder:**

**Thêm node:**
```python
builder.add_node("personal_theoretical_classifier", personal_theoretical_classifier_node)
```

**Cập nhật edges:**
```python
# Trước:
builder.add_conditional_edges(
    "classify_query",
    route_after_classify_query,
    {
        "safety_check": "safety_check",
        "not_mental_health": "not_mental_health",
    },
)

# Sau:
builder.add_conditional_edges(
    "classify_query",
    route_after_classify_query,
    {
        "personal_theoretical_classifier": "personal_theoretical_classifier",  # NEW
        "not_mental_health": "not_mental_health",
    },
)

# Thêm routing mới:
builder.add_conditional_edges(
    "personal_theoretical_classifier",
    route_after_personal_theoretical,
    {
        "theoretical_retrieval": "theoretical_retrieval",
        "safety_check": "safety_check",
    },
)
```

---

#### `src/rag/workflow/graph_nodes/__init__.py`
**Thay đổi:**
- Export node mới

```python
from .personal_theoretical_classifier import personal_theoretical_classifier_node

__all__ = [
    ...
    'personal_theoretical_classifier_node',
    ...
]
```

---

## 🎬 Kịch bản test

### **Kịch bản 1: Câu hỏi lý thuyết thuần túy**
**Input:** "Trầm cảm là gì?"
```
translate_question → EN
classify_query → topic_change (không có context trước)
personal_theoretical_classifier → theoretical (không có "tôi")
theoretical_retrieval → lấy chunks lý thuyết
answer_with_theoretical → trả lời định nghĩa
```

### **Kịch bản 2: Câu hỏi cá nhân**
**Input:** "Tôi đang cảm thấy buồn"
```
translate_question → EN
classify_query → follow_up (hoặc topic_change)
personal_theoretical_classifier → personal (có "tôi")
safety_check → không high-risk
slot_filling → extract emotion="buồn"
diagnostic_retrieval → tìm bệnh
```

### **Kịch bản 3: Follow-up theoretical (Edge case)**
**Previous:** "Tôi đang lo âu về công việc" (personal)
**Input:** "Lo âu là gì?"
```
classify_query → follow_up (liên quan context trước)
personal_theoretical_classifier → theoretical (hỏi định nghĩa)
theoretical_retrieval → trả lời định nghĩa lo âu
(Không slot_filling vì theoretical)
```

### **Kịch bản 4: Topic change personal**
**Previous:** "Trầm cảm là gì?" (theoretical)
**Input:** "Tôi nghĩ tôi bị trầm cảm"
```
classify_query → topic_change (đổi từ lý thuyết sang cá nhân)
personal_theoretical_classifier → personal (có "tôi")
safety_check → slot_filling → diagnostic
```

### **Kịch bản 5: Off-topic**
**Input:** "Công thức nấu phở là gì?"
```
classify_query → off_topic
not_mental_health → reject lịch sự
(END ngay, không chạy personal_theoretical_classifier)
```

---

## ✅ Testing checklist

- [ ] Theoretical question được route đúng (skip safety + slots)
- [ ] Personal question đi qua full flow (safety → slots → diagnostic)
- [ ] Follow-up theoretical xử lý đúng (trả lời lý thuyết, giữ context)
- [ ] Topic change personal xử lý đúng (bắt đầu slot filling mới)
- [ ] Off-topic END sớm (không chạy personal_theoretical_classifier)
- [ ] High-risk personal vẫn được detect (qua safety_check)
- [ ] State `query_nature` được lưu vào checkpointer
- [ ] Logs rõ ràng cho mỗi routing decision

---

## 🔧 Migration notes

**Không cần migration database** vì:
- State schema compatible (chỉ thêm field mới)
- Checkpointer tự động handle missing fields
- Backward compatible với old conversations

**Cần restart server** để load:
- Node mới
- Routing logic mới
- Prompt mới

---

## 📚 Related files

### Core files:
- `src/rag/workflow/workflow.py` - Main workflow definition
- `src/rag/workflow/state.py` - State schema
- `src/rag/workflow/graph_nodes/personal_theoretical_classifier.py` - New node

### Prompt files:
- `src/rag/prompts/personal_theoretical_classifier_prompt.yaml` - New prompt
- `src/rag/prompts/query_classifier_prompt.yaml` - Updated prompt

### Logic files:
- `src/rag/llm/answer_nodes/personal_theoretical_classifier.py` - New logic
- `src/rag/llm/answer_nodes/query_classifier.py` - Updated logic

---

## 🎯 Kết luận

Refactoring này:
- ✅ **Tách biệt concerns**: Conversation flow vs Query nature
- ✅ **Dễ maintain**: Mỗi node có 1 trách nhiệm rõ ràng
- ✅ **Handle edge cases**: Follow-up theoretical, topic_change personal
- ✅ **Giảm complexity**: Routing logic đơn giản hơn
- ✅ **Backward compatible**: Không breaking changes

**Result:** Workflow rõ ràng hơn, dễ debug hơn, dễ mở rộng hơn! 🚀
