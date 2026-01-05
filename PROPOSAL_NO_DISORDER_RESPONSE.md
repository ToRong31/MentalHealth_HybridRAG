# Đề Xuất: Hỗ Trợ Bot Kết Luận "Không Bệnh" / "Stress Bình Thường"

## 📋 TÓM TẮT: Đã Có Gì vs Cần Làm Gì

### ✅ Đã Implement (Có Sẵn Trong Code)

#### 1. `is_diagnosis_ready()` - Gate Function (slots.py)
**Vị trí**: `backend/src/rag/utils/slots.py` (lines 415-480)

**Chức năng**: Binary gate để check xem CÓ THỂ chẩn đoán bệnh CHƯA (timing gate)
- ✅ Check duration ≥ 2 weeks và specific
- ✅ Check impairment rõ ràng
- ✅ Check differential diagnosis (medical, substance) đã excluded
- ✅ Check không phải stress cấp tính (recent_life_events)

**Limitation**: Chỉ trả về True/False, không phân loại "normal vs disorder"

#### 2. Differential Diagnosis Slots (slots.py)
**Có sẵn**:
- `medical_history`, `substance_use`, `recent_life_events`
- Workflow đã check các slot này trong `is_diagnosis_ready()`

#### 3. Answer Generation Prompts
**File hiện tại**: 
- `answer_nodes_prompt_vie.yaml` - Có instruction "không làm quá vấn đề", "không bịa thêm"
- `treatment_answer_prompt.yaml` - Cho treatment retrieval

**Limitation**: Chưa có instruction rõ ràng về "khi nào KHÔNG nên mention disorder"

---

### ❌ Chưa Có (Cần Implement Mới)

#### 1. `assess_disorder_likelihood()` - Classification Function (PROPOSAL)
**Khác biệt với `is_diagnosis_ready()`**:
- `is_diagnosis_ready()`: "Đủ thời gian chưa? Đủ thông tin chưa?" → Binary True/False
- `assess_disorder_likelihood()`: "Đây là gì? Normal? Disorder?" → 4 categories

**4 Categories Cần Phân Loại**:
1. `normal_response` - Stress bình thường, có trigger rõ, ngắn hạn
2. `adjustment_reaction` - Phản ứng điều chỉnh với biến cố
3. `possible_disorder` - Có dấu hiệu, cần theo dõi
4. `likely_disorder` - Đủ tiêu chuẩn, nên gặp chuyên gia

#### 2. Normal Response Content Nodes
**Thiếu hoàn toàn**: Database chỉ có disorder/treatment nodes, không có:
- "Stress bình thường trước thuyết trình"
- "Lo âu tình huống vs GAD - khác biệt"
- "Coping strategies cho stress hằng ngày"

#### 3. Workflow Conditional Routing
**Workflow hiện tại**: `slot_filling` → `query_rewriter` → `diagnostic_retrieval` → `disease_conclusion`
**Thiếu**: Node assessment + routing:
- `normal_response` → normal_coping_retrieval
- `adjustment_reaction` → adjustment_retrieval  
- `possible/likely_disorder` → diagnostic_retrieval (current flow)

---

## 🎯 Vấn Đề Hiện Tại

Bot đang cố gắng **ép vào một bệnh nào đó** ngay cả khi người dùng chỉ đang trải qua **áp lực cuộc sống bình thường** hoặc **phản ứng stress cấp tính tạm thời**.

**Ví dụ**:
- User: "Lo lắng vì thuyết trình tuần sau"
- Bot hiện tại: ❌ "Bạn có thể đang gặp Rối loạn lo âu..." (WRONG - đây chỉ là lo âu tình huống bình thường)
- Bot lý tưởng: ✅ "Lo lắng trước thuyết trình là phản ứng bình thường. Đây là cách giúp bạn chuẩn bị tốt hơn..."

## 🧠 Phân Tích Gốc Rễ

### Nguyên Nhân Bot "Ép Chẩn Đoán"

1. **Retrieval Bias**: Database chủ yếu chứa tài liệu về **disorders/treatment** → retrieval luôn kéo về node disorder
   - **Evidence**: Workflow hiện tại: `query_rewriter` → `diagnostic_retrieval` → `disease_conclusion` → `treatment_retrieval`
   - Không có nhánh alternative cho "normal stress response"

2. **Thiếu Classification Logic**: `is_diagnosis_ready()` chỉ check "có đủ điều kiện chẩn đoán chưa", KHÔNG check "đây có phải disorder không"
   - `is_diagnosis_ready()` = True chỉ nghĩa: "đủ thời gian + thông tin để đánh giá"
   - KHÔNG nghĩa: "chắc chắn là disorder"
   - Cần thêm `assess_disorder_likelihood()` để classify normal vs disorder

3. **LLM Instruction Bias**: Prompt sinh câu trả lời chưa có instruction rõ ràng về "khi nào KHÔNG phải disorder"
   - `answer_nodes_prompt_vie.yaml` có: "không làm quá vấn đề" (general)
   - Thiếu: concrete rules như "if duration <2 weeks + clear trigger → normalize as normal stress"

4. **Thiếu Node "Normal Response"**: Knowledge graph thiếu node về "stress bình thường", "lo âu tình huống", "điều chỉnh tạm thời"
   - Current: chỉ có `mental_health_diagnostic_support.jsonl` và `mental_health_treatment_guidance.jsonl`
   - Missing: `normal_responses.jsonl` content

### So Sánh: `is_diagnosis_ready()` vs `assess_disorder_likelihood()` (Proposed)

| Aspect | `is_diagnosis_ready()` (CÓ SẴN) | `assess_disorder_likelihood()` (ĐỀ XUẤT) |
|--------|--------------------------------|------------------------------------------|
| **Mục đích** | Check "đủ điều kiện để assess chưa?" | Classify "đây là gì?" |
| **Output** | `True/False` (binary gate) | `"normal_response"/"adjustment_reaction"/"possible_disorder"/"likely_disorder"` |
| **Logic** | Timing + Data completeness | Symptom pattern + severity + context |
| **Use case** | "CÓ THỂ đánh giá chưa?" | "ĐÂY CÓ PHẢI disorder không?" |
| **Ví dụ** | Duration = "1 tuần" → False (chưa đủ lâu) | Duration = "1 tuần" + clear trigger → "normal_response" |

**Kết luận**: Hai function này **COMPLEMENTARY** (bổ sung cho nhau), KHÔNG duplicate!
- **Flow lý tưởng**: 
  1. Check `is_diagnosis_ready()` → Nếu False: hỏi thêm
  2. Nếu True: Chạy `assess_disorder_likelihood()` → Route tương ứng



### Tại Sao Đây Là Vấn Đề Nghiêm Trọng?

- **Y đức**: Gây lo lắng không cần thiết, tạo "bệnh hóa" (pathologizing) trải nghiệm bình thường
- **Tin cậy**: User mất niềm tin khi bot chẩn đoán quá nhanh
- **An toàn**: Vi phạm nguyên tắc "do no harm"

---

## 💡 Đề Xuất Giải Pháp (5 Tầng)

### 📊 Tầng 1: Thêm Decision Tree "Normal vs Disorder" ⚠️ **NEW IMPLEMENTATION**

**Status**: ❌ Chưa có trong codebase (cần implement mới)

**Integration với Code Hiện Tại**:
- Sử dụng output từ `is_diagnosis_ready()` (đã có) làm prerequisite
- Bổ sung thêm classification logic

**Workflow Integration**:
```
slot_filling (có sẵn)
    ↓
is_diagnosis_ready()? (có sẵn)
    ↓ False → request_more_info
    ↓ True
    ↓
assess_disorder_likelihood() (NEW - đề xuất)
    ↓
    ├─→ normal_response → normal_coping_retrieval (NEW)
    ├─→ adjustment_reaction → adjustment_retrieval (NEW)  
    ├─→ possible_disorder → diagnostic_retrieval (có sẵn, nhưng add caution)
    └─→ likely_disorder → diagnostic_retrieval (có sẵn, current flow)
```

Tạo một module đánh giá sau khi `is_diagnosis_ready() = True`.

```python
# File: backend/src/rag/utils/assessment.py (NEW FILE - CHƯA TỒN TẠI)

from typing import Dict, Any, Tuple

def assess_disorder_likelihood(slots: Dict[str, Any]) -> Tuple[str, str, float]:
    """
    Đánh giá xem triệu chứng có khả năng là disorder hay normal response.
    
    PREREQUISITE: is_diagnosis_ready() = True (đã check đủ thông tin + thời gian)
    
    KHÁC BIỆT với is_diagnosis_ready():
    - is_diagnosis_ready(): "Đủ điều kiện để assess chưa?" → True/False
    - assess_disorder_likelihood(): "Đây là gì?" → normal/adjustment/possible/likely
    
    Returns:
        Tuple of (category, explanation, confidence)
        - category: "normal_response", "adjustment_reaction", "possible_disorder", "likely_disorder"
        - explanation: Lý do đánh giá
        - confidence: 0.0-1.0
    """
    
    # Criteria for NORMAL RESPONSE
    normal_indicators = 0
    disorder_indicators = 0
    
    # 1. Duration Check
    duration = slots.get("duration", "")
    if duration:
        duration_lower = duration.lower()
        # Short duration → likely normal/adjustment
        if any(term in duration_lower for term in ["ngày", "day", "hôm", "tuần", "week"]):
            if "1" in duration or "2" in duration or "vài" in duration or "mấy" in duration:
                normal_indicators += 2
        # Long duration → consider disorder
        if any(term in duration_lower for term in ["tháng", "month", "năm", "year"]):
            disorder_indicators += 2
    
    # 2. Trigger Check (Recent Life Event)
    recent_events = slots.get("recent_life_events", "")
    if recent_events:
        # Clear identifiable trigger → likely normal stress/adjustment
        event_lower = recent_events.lower()
        normal_triggers = [
            "thuyết trình", "presentation", "thi", "exam", "deadline",
            "họp", "meeting", "phỏng vấn", "interview", 
            "tranh cãi", "conflict", "mất ngủ vì", "lo vì"
        ]
        if any(trigger in event_lower for trigger in normal_triggers):
            normal_indicators += 2
    
    # 3. Impairment Check
    daily_functioning = slots.get("daily_functioning", "")
    work_impact = slots.get("work_school_impact", "")
    
    if daily_functioning in ["normal", "mild_impairment"] or work_impact in ["none", "mild"]:
        normal_indicators += 1
    elif daily_functioning in ["moderate", "severe"] or work_impact in ["moderate", "severe", "unable"]:
        disorder_indicators += 2
    
    # 4. Symptom Pattern
    symptom_fluctuation = slots.get("symptom_fluctuation", "")
    if symptom_fluctuation:
        pattern_lower = symptom_fluctuation.lower()
        # Episodic/situational → likely normal
        if any(term in pattern_lower for term in ["tình huống", "situational", "thỉnh thoảng", "sometimes", "khi"]):
            normal_indicators += 1
        # Persistent/continuous → consider disorder
        if any(term in pattern_lower for term in ["liên tục", "continuous", "suốt", "always", "luôn"]):
            disorder_indicators += 1
    
    # 5. Physical Health Check
    medical_history = slots.get("medical_history")
    substance_use = slots.get("substance_use")
    
    # If medical cause not ruled out → cannot conclude disorder
    if medical_history is None or substance_use is None:
        # Insufficient info to conclude disorder
        disorder_indicators -= 1
    
    # 6. Severity/Intensity
    intensity = slots.get("intensity", "")
    if intensity in ["low", "medium"]:
        normal_indicators += 1
    elif intensity in ["high", "very_high"]:
        disorder_indicators += 1
    
    # Decision Logic
    total_score = normal_indicators - disorder_indicators
    
    if total_score >= 3:
        return (
            "normal_response",
            "Các dấu hiệu cho thấy đây là phản ứng stress bình thường với tình huống cụ thể, không đáp ứng tiêu chuẩn rối loạn.",
            0.8
        )
    elif total_score >= 1:
        return (
            "adjustment_reaction",
            "Có thể là phản ứng điều chỉnh (adjustment reaction) với biến cố sống, chưa đủ tiêu chuẩn chẩn đoán rối loạn.",
            0.7
        )
    elif total_score >= -1:
        return (
            "possible_disorder",
            "Một số dấu hiệu gợi ý khả năng rối loạn, cần theo dõi thêm và tư vấn chuyên gia.",
            0.6
        )
    else:
        return (
            "likely_disorder",
            "Các dấu hiệu đáp ứng tiêu chuẩn của rối loạn tâm lý, nên gặp chuyên gia để đánh giá chính xác.",
            0.7
        )


def should_retrieve_disorder_content(slots: Dict[str, Any]) -> bool:
    """
    Quyết định có nên retrieve disorder-specific content không.
    
    Returns:
        True nếu nên retrieve disorder content
        False nếu nên focus vào coping/stress management
    """
    category, _, confidence = assess_disorder_likelihood(slots)
    
    # Chỉ retrieve disorder content khi:
    # 1. Category là possible/likely disorder
    # 2. Đã có diagnosis_ready (từ slots.is_diagnosis_ready())
    
    from .slots import is_diagnosis_ready
    
    if category in ["normal_response", "adjustment_reaction"]:
        return False  # Không retrieve disorder → focus coping/stress management
    elif category == "possible_disorder" and is_diagnosis_ready(slots):
        return True   # Có thể retrieve nhưng cẩn trọng
    elif category == "likely_disorder" and is_diagnosis_ready(slots):
        return True   # Retrieve disorder content
    else:
        return False  # Chưa đủ thông tin → hỏi thêm
```

### 📚 Tầng 2: Thêm "Normal Response" Nodes vào Knowledge Graph ⚠️ **NEW CONTENT**

**Status**: ❌ Chưa có (cần tạo mới)

**Current Content Files**:
- ✅ `mental_health_diagnostic_support.jsonl` - Có disorder descriptions
- ✅ `mental_health_treatment_guidance.jsonl` - Có treatment guidance
- ❌ `normal_responses.jsonl` - **THIẾU** - content về stress/anxiety bình thường

Hiện tại knowledge graph chủ yếu chứa disorder nodes. Cần thêm:

#### Các Node Cần Thêm:

1. **Normal Stress Responses**
   - "Phản ứng stress cấp tính bình thường"
   - "Lo âu tình huống (Situational Anxiety)"
   - "Buồn bã tạm thời (Transient Sadness)"
   - "Mệt mỏi sau áp lực công việc (Work-related Fatigue)"

2. **Coping Strategies (Non-disorder)**
   - "Kỹ thuật thư giãn cho stress hằng ngày"
   - "Quản lý lo âu trước thuyết trình"
   - "Cải thiện giấc ngủ khi stress"
   - "Work-life balance"

3. **Psychoeducation (Normal vs Disorder)**
   - "Khi nào stress trở thành rối loạn?"
   - "Phân biệt lo âu bình thường vs GAD"
   - "Adjustment Disorder là gì?"

#### Cách Thêm:

```python
# File: backend/data/raw/normal_responses.jsonl

{"id": "normal_001", "title": "Phản ứng stress cấp tính bình thường", "content": "Stress cấp tính là phản ứng tự nhiên của cơ thể với tình huống đe dọa hoặc thách thức. Các triệu chứng như lo lắng, tim đập nhanh, mất ngủ tạm thời trong vài ngày đến vài tuần khi đối mặt với deadline, thuyết trình, hoặc biến cố quan trọng là HOÀN TOÀN BÌNH THƯỜNG. Đây KHÔNG phải là rối loạn lo âu. Khác biệt chính: (1) Có trigger rõ ràng, (2) Thời gian ngắn (<1 tháng), (3) Giảm dần khi tình huống kết thúc, (4) Không ảnh hưởng nghiêm trọng đến chức năng hàng ngày."}

{"id": "normal_002", "title": "Lo âu trước thuyết trình - Phản ứng bình thường", "content": "Lo lắng trước khi thuyết trình trước đám đông là phản ứng cực kỳ phổ biến, ảnh hưởng đến 75% người trưởng thành. Đây KHÔNG phải là rối loạn tâm lý. Các biểu hiện như: tim đập nhanh, đổ mồ hôi, căng thẳng trước giờ G, mất ngủ 1-2 đêm là hoàn toàn bình thường. Cách đối phó: (1) Chuẩn bị kỹ lưỡng, (2) Thực hành trước, (3) Kỹ thuật thở sâu, (4) Tái đóng khung tích cực ('hồi hộp' thay vì 'lo sợ'). Nếu sau thuyết trình mà triệu chứng biến mất → đây là lo âu tình huống, không cần điều trị."}

{"id": "normal_003", "title": "Phân biệt Stress bình thường vs Rối loạn lo âu (GAD)", "content": "Nhiều người nhầm lẫn giữa stress hằng ngày và rối loạn lo âu lan tỏa (GAD). Khác biệt chính:\n\nSTRESS BÌNH THƯỜNG:\n- Có nguyên nhân cụ thể (công việc, thi cử, tài chính)\n- Thời gian ngắn (vài ngày đến vài tuần)\n- Giảm khi giải quyết được vấn đề\n- Không ảnh hưởng nhiều đến công việc/sống\n- Có thể quản lý bằng nghỉ ngơi/thư giãn\n\nRỐI LOẠN LO ÂU (GAD):\n- Lo âu lan tỏa, KHÔNG rõ nguyên nhân\n- Kéo dài ≥ 6 THÁNG\n- Liên tục mặc dù không có stress rõ ràng\n- Ảnh hưởng NGHIÊM TRỌNG đến công việc/quan hệ\n- Khó kiểm soát dù đã thử nhiều cách\n\nNếu bạn chỉ lo lắng về deadline tuần sau → đây là STRESS BÌNH THƯỜNG, không phải GAD."}
```

Sau đó chạy ingestion pipeline để đưa vào vector DB và knowledge graph.

### 🤖 Tầng 3: Cập Nhật Prompt Sinh Câu Trả Lời (Answer Generation) ⚠️ **MODIFY EXISTING**

**Status**: ⚠️ File có sẵn nhưng cần bổ sung instruction

**Current Files**:
- `backend/src/rag/prompts/answer_nodes_prompt_vie.yaml` (có sẵn)
  - ✅ Có: "không làm quá vấn đề", "không bịa thêm", "chỉ giải quyết vấn đề họ đưa ra"
  - ❌ Thiếu: Concrete rules about "when to normalize vs when to suggest disorder"
  
- `backend/src/rag/prompts/treatment_answer_prompt.yaml` (có sẵn, cho treatment phase)

**Cần Thêm**: Decision logic section trong answer prompts

#### File cần sửa: `backend/src/rag/prompts/answer_nodes_prompt_vie.yaml`

**Thêm Section Mới vào existing prompt**:

```yaml
# Thêm vào answer_nodes_prompt_vie.yaml sau NGUYÊN TẮC CỐT LÕI section

  ========== DECISION LOGIC: NORMAL vs DISORDER (NEW) ==========
  
  **Assessment Category** (provided in context from assess_disorder_likelihood()):
  - "normal_response" → Focus on validation + coping strategies
  - "adjustment_reaction" → Validate + psychoeducation about adjustment
  - "possible_disorder" → Cautious mention + recommend monitoring
  - "likely_disorder" → Suggest professional evaluation (but don't diagnose)

  **Response Structure by Category**:

  IF category = "normal_response":
  ```
  1. VALIDATE: "Lo lắng trước [event] là phản ứng hoàn toàn bình thường..."
  2. NORMALIZE: "Nhiều người trải qua điều tương tự khi..."
  3. EDUCATE: "Đây không phải là rối loạn lo âu mà là..."
  4. COPING: "Một số cách giúp bạn quản lý cảm giác này..."
  5. REASSURE: "Cảm giác này thường giảm dần sau khi..."
  ```

  IF category = "adjustment_reaction":
  ```
  1. VALIDATE: "Đối mặt với [life event] là thách thức lớn..."
  2. EDUCATE: "Phản ứng của bạn gọi là 'rối loạn điều chỉnh'..."
  3. DIFFERENTIATE: "Điều này khác với rối loạn ở chỗ..."
  4. SUPPORT: "Đây là gợi ý giúp bạn điều chỉnh..."
  5. TIMELINE: "Thường cải thiện trong vài tuần/tháng..."
  ```

  IF category = "possible_disorder" OR "likely_disorder":
  ```
  1. ACKNOWLEDGE: "Những dấu hiệu bạn chia sẻ có thể liên quan đến..."
  2. CAUTION: "Tuy nhiên, chỉ chuyên gia mới có thể chẩn đoán chính xác..."
  3. RECOMMEND: "Mình khuyên bạn nên gặp tâm lý sư/bác sĩ để..."
  4. SUPPORT: "Trong lúc chờ, đây là cách hỗ trợ bản thân..."
  ```

  ========== FORBIDDEN PHRASES (NEVER USE) ==========
  
  - ❌ "Bạn bị rối loạn..."
  - ❌ "Đây là triệu chứng của [disorder name]..."
  - ❌ "Bạn cần điều trị cho [disorder]..."
  - ❌ "Chẩn đoán của bạn là..."

  ========== PREFERRED PHRASES ==========
  
  - ✅ "Dấu hiệu này **có thể** liên quan đến..."
  - ✅ "Điều này **thường gặp** khi..."
  - ✅ "Đây là phản ứng **bình thường** với..."
  - ✅ "Chuyên gia sẽ giúp xác định xem..."
  - ✅ "Nếu tiếp tục ≥ [timeframe], hãy tham khảo ý kiến chuyên gia..."

  USER SLOTS:
  {{SLOTS}}
  
  ASSESSMENT CATEGORY: {{ASSESSMENT_CATEGORY}}
  ASSESSMENT EXPLANATION: {{ASSESSMENT_EXPLANATION}}
  
  RETRIEVED CONTEXT:
  {{CONTEXT}}
```

### 🔀 Tầng 4: Cập Nhật Workflow Logic ⚠️ **MODIFY EXISTING WORKFLOW**

**Status**: ⚠️ Workflow có sẵn nhưng cần thêm nodes và routing

**Current Workflow** (trong `workflow.py`):
```
translate_question → classify_type_query → router → safety_check 
    → slot_filling → route_after_slot_filling 
    → query_rewriter → diagnostic_retrieval → disease_conclusion 
    → route_after_disease_conclusion 
    → treatment_retrieval / graph_retrieval → answer
```

**Thiếu**:
- ❌ Assessment node (sau slot_filling, trước query_rewriter)
- ❌ Conditional routing based on assessment category
- ❌ `normal_coping_retrieval` node
- ❌ `adjustment_retrieval` node

**Proposed Change**: Insert assessment node AFTER `slot_filling`, BEFORE `query_rewriter`

#### File: `backend/src/rag/workflow/workflow.py`

**Thêm Node Đánh Giá và Routing**:

```python
# Modify existing workflow.py

from ..utils.assessment import assess_disorder_likelihood, should_retrieve_disorder_content  # NEW import

def assessment_node(state: KGState) -> KGState:
    """
    NEW NODE: Đánh giá xem có nên đi vào nhánh disorder hay không.
    Chạy AFTER slot_filling, BEFORE query_rewriter
    """
    slots = state.get("slots", {})
    
    # Prerequisite check: is_diagnosis_ready() phải = True mới chạy node này
    from src.rag.utils.slots import is_diagnosis_ready
    if not is_diagnosis_ready(slots):
        # Không đủ thông tin → skip assessment, yêu cầu thêm info
        state["assessment_category"] = "insufficient_info"
        return state
    
    # Đánh giá disorder likelihood
    category, explanation, confidence = assess_disorder_likelihood(slots)
    
    state["assessment_category"] = category
    state["assessment_explanation"] = explanation
    state["assessment_confidence"] = confidence
    
    logger.info(f"[ASSESSMENT] Category: {category}, Confidence: {confidence:.2f}")
    logger.info(f"[ASSESSMENT] Explanation: {explanation}")
    
    return state


def route_after_assessment(state: KGState) -> Literal["normal_coping_retrieval", "adjustment_retrieval", "query_rewriter"]:
    """
    NEW ROUTING: Quyết định nhánh tiếp theo dựa trên assessment.
    
    Routes:
    - normal_response → normal_coping_retrieval (focus coping, NOT disorder)
    - adjustment_reaction → adjustment_retrieval (focus adjustment, NOT disorder)
    - possible_disorder / likely_disorder → query_rewriter → diagnostic_retrieval (current flow)
    """
    category = state.get("assessment_category", "possible_disorder")
    
    if category == "normal_response":
        logger.info("[ROUTING] Normal response detected → normal_coping_retrieval")
        return "normal_coping_retrieval"
    elif category == "adjustment_reaction":
        logger.info("[ROUTING] Adjustment reaction detected → adjustment_retrieval")
        return "adjustment_retrieval"
    else:
        # possible_disorder or likely_disorder → proceed to diagnostic flow
        logger.info(f"[ROUTING] {category} → diagnostic flow (query_rewriter)")
        return "query_rewriter"


# Update workflow graph
def build_kg_graph():
    builder = StateGraph(KGState)
    
    # Existing nodes (keep as is)
    builder.add_node("slot_filling", slot_filling_node)
    builder.add_node("query_rewriter", query_rewriter_node)
    builder.add_node("diagnostic_retrieval", diagnostic_retrieval_node)
    
    # NEW NODES
    builder.add_node("assessment", assessment_node)  # NEW
    builder.add_node("normal_coping_retrieval", normal_coping_retrieval_node)  # NEW (cần implement)
    builder.add_node("adjustment_retrieval", adjustment_retrieval_node)  # NEW (cần implement)
    
    # MODIFY EDGE: slot_filling → assessment (instead of direct to query_rewriter)
    builder.add_conditional_edges(
        "slot_filling",
        route_after_slot_filling,  # Existing routing
        {
            "query_rewriter": "assessment",  # CHANGE: go to assessment first, not query_rewriter
            "request_more_info": "request_more_info",  # Keep existing path
        },
    )
    
    # NEW EDGE: assessment → conditional routing
    builder.add_conditional_edges(
        "assessment",
        route_after_assessment,  # NEW routing function
        {
            "normal_coping_retrieval": "normal_coping_retrieval",
            "adjustment_retrieval": "adjustment_retrieval",
            "query_rewriter": "query_rewriter",  # Proceed to diagnostic flow
        },
    )
    
    # NEW EDGES: normal/adjustment paths → answer_with_graph (skip disease_conclusion)
    builder.add_edge("normal_coping_retrieval", "answer_with_graph")
    builder.add_edge("adjustment_retrieval", "answer_with_graph")
    
    # Existing edges (keep as is)
    builder.add_edge("query_rewriter", "diagnostic_retrieval")
    # ... rest of workflow unchanged
```

**Implementation Priority**:
1. ✅ Có sẵn: `route_after_slot_filling` (check has_sufficient_slots)
2. ❌ Cần implement: `assessment_node()`
3. ❌ Cần implement: `route_after_assessment()`
4. ❌ Cần implement: `normal_coping_retrieval_node()` và `adjustment_retrieval_node()`

### 📝 Tầng 5: Logging và Feedback Loop ⚠️ **NEW IMPLEMENTATION**

**Status**: ❌ Chưa có monitoring cho over-diagnosis

Để đảm bảo bot không ép chẩn đoán, cần theo dõi:

```python
# File: backend/src/rag/utils/metrics.py (NEW FILE hoặc thêm vào existing monitoring)

def log_diagnosis_decision(
    conversation_id: str,
    slots: Dict[str, Any],
    assessment_category: str,
    final_response: str
):
    """
    Log decision để review sau.
    """
    # Check if response contains disorder-specific terms
    disorder_terms = ["rối loạn", "disorder", "bệnh", "illness", "GAD", "OCD", "depression"]
    contains_diagnosis = any(term.lower() in final_response.lower() for term in disorder_terms)
    
    log_entry = {
        "conversation_id": conversation_id,
        "timestamp": datetime.now().isoformat(),
        "duration": slots.get("duration"),
        "recent_life_events": slots.get("recent_life_events"),
        "assessment_category": assessment_category,
        "contains_diagnosis_terms": contains_diagnosis,
        "response_excerpt": final_response[:200]
    }
    
    # Log to file or monitoring system
    if assessment_category == "normal_response" and contains_diagnosis:
        # WARNING: Bot đang ép chẩn đoán cho normal case
        logger.warning(f"Potential over-diagnosis: {log_entry}")
    
    return log_entry
```

---

## 🧪 Test Cases Cần Pass

### Test 1: Normal Performance Anxiety
```
Input:
- User: "Lo lắng vì thuyết trình tuần sau"
- Duration: "1 tuần"
- Recent event: "chuẩn bị thuyết trình"
- Impact: "mild"

Expected Output:
- Assessment: "normal_response"
- Response: "Lo lắng trước thuyết trình là phản ứng hoàn toàn bình thường..."
- NO mention of GAD, anxiety disorder
```

### Test 2: Work Stress (Not Burnout Yet)
```
Input:
- User: "Mệt mỏi vì deadline"
- Duration: "2 tuần"
- Recent event: "nhiều deadline"
- Daily functioning: "normal"

Expected Output:
- Assessment: "normal_response" or "adjustment_reaction"
- Response: "Stress từ áp lực công việc là phổ biến..."
- Suggest work-life balance, rest
- NO mention of depression, burnout disorder
```

### Test 3: Adjustment Reaction (Breakup)
```
Input:
- User: "Buồn sau khi chia tay"
- Duration: "3 tuần"
- Recent event: "chia tay người yêu"
- Impact: "moderate"

Expected Output:
- Assessment: "adjustment_reaction"
- Response: "Buồn bã sau chia tay là phản ứng điều chỉnh bình thường..."
- Explain difference from depression
- NO immediate diagnosis of depression
```

### Test 4: Likely Disorder (Should Refer)
```
Input:
- User: "Lo âu liên tục, không rõ lý do"
- Duration: "6 tháng"
- Recent event: None
- Impact: "severe"
- Daily functioning: "severe impairment"

Expected Output:
- Assessment: "likely_disorder"
- Response: "Dấu hiệu này có thể liên quan đến rối loạn lo âu... Mình khuyên bạn gặp chuyên gia..."
- Can mention GAD as POSSIBILITY, not definitive diagnosis
```

---

## 📋 Implementation Checklist với Status

### Phase 1: Core Logic (Week 1)
- [ ] ❌ **NEW**: Tạo file `backend/src/rag/utils/assessment.py`
- [ ] ❌ **NEW**: Implement `assess_disorder_likelihood()` function
- [ ] ❌ **NEW**: Implement `should_retrieve_disorder_content()` helper
- [ ] ⚠️ **USE EXISTING**: Integrate với `is_diagnosis_ready()` từ `slots.py` (đã có)
- [ ] ❌ **NEW**: Test assessment function với 20+ test cases

### Phase 2: Content (Week 2)
- [ ] ❌ **NEW**: Tạo file `backend/data/raw/normal_responses.jsonl`
- [ ] ❌ **NEW**: Viết 20-30 "normal response" content nodes
- [ ] ❌ **NEW**: Viết 10-15 "adjustment reaction" content nodes
- [ ] ❌ **NEW**: Chạy ingestion pipeline để ingest vào vector DB + knowledge graph
- [ ] ⚠️ **VERIFY**: Check existing graph có thể store normal response nodes không

### Phase 3: Prompt Engineering (Week 2)
- [ ] ⚠️ **MODIFY EXISTING**: Update `answer_nodes_prompt_vie.yaml`
  - [ ] Thêm "DECISION LOGIC: NORMAL vs DISORDER" section
  - [ ] Thêm response structure by category
  - [ ] Thêm forbidden/preferred phrases
- [ ] ⚠️ **VERIFY**: Check `treatment_answer_prompt.yaml` có cần update không
- [ ] ❌ **NEW**: Add assessment_category, assessment_explanation vào prompt context

### Phase 4: Workflow Integration (Week 3)
- [ ] ❌ **NEW**: Implement `assessment_node()` trong `workflow/graph_nodes/`
- [ ] ⚠️ **MODIFY**: Update `workflow.py`:
  - [ ] Add `assessment` node
  - [ ] Modify routing: `slot_filling` → `assessment` → conditional
  - [ ] Add `route_after_assessment()` function
- [ ] ❌ **NEW**: Implement `normal_coping_retrieval_node()`
- [ ] ❌ **NEW**: Implement `adjustment_retrieval_node()`
- [ ] ⚠️ **MODIFY**: Update `state.py` (KGState) to include:
  - [ ] `assessment_category: str`
  - [ ] `assessment_explanation: str`
  - [ ] `assessment_confidence: float`

### Phase 5: Testing & Monitoring (Week 3-4)
- [ ] ❌ **NEW**: Implement logging in `metrics.py` hoặc existing logger
- [ ] ❌ **NEW**: Add over-diagnosis detection (normal_response + disorder_terms = WARNING)
- [ ] ❌ **NEW**: Create test suite với 50+ cases (normal, adjustment, disorder)
- [ ] ❌ **NEW**: A/B test với user feedback
- [ ] ⚠️ **USE EXISTING**: Integrate với current logging system (nếu có)

**Legend**:
- ❌ **NEW**: Cần implement mới hoàn toàn
- ⚠️ **MODIFY EXISTING**: Có sẵn nhưng cần sửa/bổ sung
- ✅ **USE EXISTING**: Dùng lại code hiện tại, không cần thay đổi

---

## 🔍 Files Cần Tạo/Sửa - Summary

### 📄 Tạo Mới (NEW)
1. `backend/src/rag/utils/assessment.py` - assess_disorder_likelihood() logic
2. `backend/data/raw/normal_responses.jsonl` - Normal stress content
3. `backend/src/rag/workflow/graph_nodes/assessment.py` - Assessment node
4. `backend/src/rag/workflow/graph_nodes/normal_coping_retrieval.py` - Normal coping retrieval
5. `backend/src/rag/workflow/graph_nodes/adjustment_retrieval.py` - Adjustment retrieval
6. Test suite cho assessment logic

### ✏️ Sửa/Bổ Sung (MODIFY)
1. `backend/src/rag/workflow/workflow.py` - Add assessment node + routing
2. `backend/src/rag/workflow/state.py` - Add assessment fields to KGState
3. `backend/src/rag/prompts/answer_nodes_prompt_vie.yaml` - Add decision logic section
4. (Optional) `backend/src/rag/utils/metrics.py` - Add over-diagnosis monitoring

### 🔒 Giữ Nguyên (USE AS-IS)
1. ✅ `backend/src/rag/utils/slots.py` - is_diagnosis_ready() đã implement tốt
2. ✅ `backend/src/rag/workflow/graph_nodes/slot_filling.py` - Slot extraction logic OK
3. ✅ `backend/src/rag/workflow/graph_nodes/diagnostic_retrieval.py` - Dùng cho disorder cases
4. ✅ `backend/src/rag/workflow/graph_nodes/disease_conclusion.py` - Dùng cho disorder cases

---

## 🎯 Success Metrics

### Quantitative:
1. **Diagnosis Rate**: Giảm 40-50% số lần bot mention disorder terms trong 2 tuần đầu
2. **Normal Response Rate**: Tăng lên 30-40% conversations kết luận "normal/adjustment"
3. **User Satisfaction**: Survey "Bot có hiểu đúng tình huống của bạn không?" → target 80%+ "Yes"

### Qualitative:
1. Bot biết khi nào nói "Đây là bình thường" thay vì "Có thể là bệnh"
2. Response cảm thấy "reassuring" thay vì "alarming"
3. Không còn case "lo lắng thuyết trình" → "GAD"

---

## ⚠️ Lưu Ý Quan Trọng

1. **Balance**: Cẩn thận không "under-diagnose". Vẫn phải recognize disorders thật sự.
2. **Liability**: Luôn disclaimer "Chỉ chuyên gia mới chẩn đoán được"
3. **Cultural Context**: Trong văn hóa Việt Nam, stress từ học tập/công việc rất phổ biến và thường là normal response
4. **Iteration**: Cần monitor và adjust threshold liên tục dựa trên feedback

---

## 📚 Tài Liệu Tham Khảo

- DSM-5: Adjustment Disorders vs Major Depressive Disorder
- ICD-11: Differentiation of normal stress responses
- APA Guidelines: When to refer vs when to provide psychoeducation

---

**Tác giả**: AI Assistant  
**Ngày**: 2026-01-04  
**Status**: Proposal - Chờ Review & Approval
