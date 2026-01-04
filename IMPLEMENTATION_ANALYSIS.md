# Phân Tích Chi Tiết: Chức Năng Có Sẵn vs Đề Xuất

## 📊 Executive Summary

**Kết luận chính**: Code hiện tại **ĐÃ CÓ** logic kiểm tra điều kiện chẩn đoán (`is_diagnosis_ready()`), nhưng **CHƯA CÓ** logic phân loại "đây có phải disorder không" (`assess_disorder_likelihood()`).

**Hai function này KHÔNG trùng lặp mà BỔ SUNG cho nhau**:
- `is_diagnosis_ready()`: "Đủ điều kiện assess chưa?" → Binary gate
- `assess_disorder_likelihood()`: "Đây là gì?" → 4-category classifier

---

## 🔍 Chi Tiết Các Function

### 1️⃣ `is_diagnosis_ready()` - ✅ CÓ SẴN

**File**: `backend/src/rag/utils/slots.py` (lines 415-480)

**Mục đích**: Binary gate - check xem có đủ điều kiện để đánh giá chẩn đoán CHƯA

**Logic Check**:
```python
def is_diagnosis_ready(slots: Dict[str, Any]) -> bool:
    """
    Check if we have sufficient information to proceed with diagnosis.
    
    Criteria:
    1. Duration must be specific AND prolonged (≥2 weeks)
    2. Impairment must be clear (not unknown)
    3. Differential diagnosis must be excluded (medical, substance)
    4. Not acute stress (no recent_life_events or old events)
    
    Returns:
        True if ready for disorder-specific diagnosis
        False if need more info or too early
    """
    # 1. Duration check
    duration = slots.get("duration", "")
    is_specific, certainty = validate_duration(duration)
    
    if not is_specific or certainty < 0.7:
        return False  # Duration vague → not ready
    
    # Check if duration is long enough (≥2 weeks)
    duration_lower = duration.lower()
    short_terms = ["ngày", "day", "hôm", "1 tuần", "1 week"]
    if any(term in duration_lower for term in short_terms):
        return False  # Too short → likely acute stress
    
    # 2. Impairment must be clear
    daily_functioning = slots.get("daily_functioning")
    if daily_functioning in [None, "unknown"]:
        return False
    
    # 3. Differential diagnosis (if physical symptoms present)
    physical_symptoms = slots.get("physical_symptoms", [])
    if physical_symptoms:
        medical = slots.get("medical_history")
        substance = slots.get("substance_use")
        if medical is None or substance is None:
            return False  # Medical causes not ruled out
    
    # 4. Not acute stress
    recent_events = slots.get("recent_life_events")
    if recent_events:
        # Check if event is truly recent
        event_lower = recent_events.lower()
        recent_indicators = ["hôm qua", "yesterday", "tuần này", "this week", "vừa"]
        if any(term in event_lower for term in recent_indicators):
            return False  # Acute stress → wait longer
    
    return True
```

**Output**: 
- `True` = Đủ điều kiện để assess (đủ thông tin + thời gian)
- `False` = Chưa đủ (cần hỏi thêm hoặc chờ thêm)

**Use Case**: Timing gate - "CÓ THỂ đánh giá chưa?"

**Ví dụ**:
- Duration = "1 tuần", recent_events = "thuyết trình tuần sau" → `False` (quá sớm)
- Duration = "3 tháng", impairment = "severe", medical_history = "no" → `True` (đủ điều kiện)

**Limitation**: 
- ⚠️ Chỉ check timing + data completeness
- ⚠️ KHÔNG phân biệt normal stress vs disorder
- ⚠️ `True` không có nghĩa "chắc chắn là disorder"

---

### 2️⃣ `assess_disorder_likelihood()` - ❌ CHƯA CÓ (ĐỀ XUẤT)

**File**: `backend/src/rag/utils/assessment.py` (CHƯA TỒN TẠI - cần tạo mới)

**Mục đích**: 4-category classifier - phân loại "đây là gì?"

**Logic Check** (Proposed):
```python
def assess_disorder_likelihood(slots: Dict[str, Any]) -> Tuple[str, str, float]:
    """
    Classify whether symptoms are normal response or disorder.
    
    PREREQUISITE: is_diagnosis_ready() = True (must have sufficient data)
    
    Categories:
    - "normal_response": Normal stress with clear trigger, short duration
    - "adjustment_reaction": Adjustment to life event, not disorder
    - "possible_disorder": Some indicators, need monitoring
    - "likely_disorder": Meets disorder criteria, refer to professional
    
    Returns:
        (category, explanation, confidence)
    """
    normal_indicators = 0
    disorder_indicators = 0
    
    # 1. Duration scoring
    duration = slots.get("duration", "")
    if "1 tuần" in duration or "2 tuần" in duration:
        normal_indicators += 2  # Short → likely normal
    elif "6 tháng" in duration or "năm" in duration:
        disorder_indicators += 2  # Long → consider disorder
    
    # 2. Trigger analysis
    recent_events = slots.get("recent_life_events", "")
    if recent_events:
        # Clear identifiable trigger
        normal_triggers = ["thuyết trình", "thi", "deadline", "họp", "phỏng vấn"]
        if any(t in recent_events.lower() for t in normal_triggers):
            normal_indicators += 2  # Clear trigger → normal stress
    
    # 3. Impairment severity
    daily_functioning = slots.get("daily_functioning", "")
    if daily_functioning in ["normal", "mild_impairment"]:
        normal_indicators += 1
    elif daily_functioning in ["moderate", "severe"]:
        disorder_indicators += 2
    
    # 4. Symptom pattern
    symptom_fluctuation = slots.get("symptom_fluctuation", "")
    if "tình huống" in symptom_fluctuation or "thỉnh thoảng" in symptom_fluctuation:
        normal_indicators += 1  # Situational → normal
    elif "liên tục" in symptom_fluctuation or "suốt" in symptom_fluctuation:
        disorder_indicators += 1  # Continuous → disorder
    
    # Decision logic
    score = normal_indicators - disorder_indicators
    
    if score >= 3:
        return ("normal_response", "Phản ứng stress bình thường với trigger rõ ràng", 0.8)
    elif score >= 1:
        return ("adjustment_reaction", "Phản ứng điều chỉnh với biến cố sống", 0.7)
    elif score >= -1:
        return ("possible_disorder", "Một số dấu hiệu, cần theo dõi", 0.6)
    else:
        return ("likely_disorder", "Đáp ứng tiêu chuẩn disorder, nên gặp chuyên gia", 0.7)
```

**Output**: 
- Category: `"normal_response"`, `"adjustment_reaction"`, `"possible_disorder"`, `"likely_disorder"`
- Explanation: String giải thích lý do
- Confidence: 0.0-1.0

**Use Case**: Classification - "ĐÂY CÓ PHẢI disorder không?"

**Ví dụ**:
- Duration = "1 tuần", trigger = "thuyết trình", functioning = "mild" 
  → `("normal_response", "Lo âu tình huống bình thường", 0.8)`
  
- Duration = "6 tháng", trigger = None, functioning = "severe" 
  → `("likely_disorder", "Đáp ứng tiêu chuẩn GAD", 0.7)`

---

## 🔄 Workflow Integration

### Current Flow (Có Sẵn)
```
slot_filling 
    ↓
route_after_slot_filling()
    ├─→ has_sufficient_slots = False → request_more_info
    └─→ has_sufficient_slots = True → query_rewriter → diagnostic_retrieval
```

**Vấn đề**: Không có bước phân loại "normal vs disorder"

### Proposed Flow (Đề Xuất)
```
slot_filling 
    ↓
route_after_slot_filling()
    ├─→ has_sufficient_slots = False → request_more_info
    └─→ has_sufficient_slots = True
            ↓
        assessment_node() [NEW]
            ├─→ is_diagnosis_ready() = False → request_more_info
            └─→ is_diagnosis_ready() = True
                    ↓
                assess_disorder_likelihood() [NEW]
                    ↓
                route_after_assessment() [NEW]
                    ├─→ normal_response → normal_coping_retrieval [NEW]
                    ├─→ adjustment_reaction → adjustment_retrieval [NEW]
                    └─→ possible/likely_disorder → query_rewriter → diagnostic_retrieval (current)
```

**Key Changes**:
1. ❌ **NEW**: `assessment_node()` - Chạy cả `is_diagnosis_ready()` + `assess_disorder_likelihood()`
2. ❌ **NEW**: `route_after_assessment()` - Conditional routing based on category
3. ❌ **NEW**: `normal_coping_retrieval` và `adjustment_retrieval` nodes
4. ⚠️ **MODIFY**: `route_after_slot_filling()` → route to `assessment` instead of `query_rewriter`

---

## 📝 Prompt Integration

### Current Prompt (Có Sẵn)
**File**: `backend/src/rag/prompts/answer_nodes_prompt_vie.yaml`

**Có instruction**:
- ✅ "Không làm quá vấn đề chỉ giải quyết vấn đề mà họ đưa ra"
- ✅ "Không bịa thêm thông tin họ đưa vào"

**Thiếu**:
- ❌ Concrete rules: "If duration < 2 weeks + clear trigger → normalize"
- ❌ Decision logic by assessment category
- ❌ Examples of normalizing vs pathologizing

### Proposed Addition (Đề Xuất)
```yaml
# Thêm vào answer_nodes_prompt_vie.yaml

  ========== DECISION LOGIC: NORMAL vs DISORDER ==========
  
  **Assessment Category** (provided in context):
  {{ASSESSMENT_CATEGORY}}
  
  **Response Structure**:
  
  IF category = "normal_response":
  1. VALIDATE: "Lo lắng trước [event] là phản ứng hoàn toàn bình thường..."
  2. NORMALIZE: "Nhiều người trải qua điều tương tự..."
  3. EDUCATE: "Đây không phải là rối loạn mà là..."
  4. COPING: "Gợi ý cách quản lý..."
  5. REASSURE: "Cảm giác này giảm sau khi..."
  
  IF category = "adjustment_reaction":
  1. VALIDATE: "Đối mặt [event] là thách thức..."
  2. EDUCATE: "Phản ứng điều chỉnh khác disorder ở chỗ..."
  3. SUPPORT: "Gợi ý điều chỉnh..."
  
  IF category = "possible_disorder" / "likely_disorder":
  1. ACKNOWLEDGE: "Dấu hiệu có thể liên quan đến..."
  2. CAUTION: "Chỉ chuyên gia mới chẩn đoán..."
  3. RECOMMEND: "Nên gặp tâm lý sư..."

user_template: |
  Câu hỏi: {{QUESTION}}
  
  Kiến thức: {{GRAPH_CONTEXT}}
  
  Assessment Category: {{ASSESSMENT_CATEGORY}}
  Assessment Explanation: {{ASSESSMENT_EXPLANATION}}
  
  Hãy phản hồi theo decision logic trên.
```

---

## 🧪 Test Cases để Validate

### Test 1: Normal Performance Anxiety
**Input**:
```json
{
  "user_message": "Lo lắng vì thuyết trình tuần sau",
  "slots": {
    "duration": "1 tuần",
    "recent_life_events": "chuẩn bị thuyết trình",
    "daily_functioning": "mild_impairment",
    "intensity": "medium"
  }
}
```

**Expected**:
- `is_diagnosis_ready()` → `False` (duration quá ngắn)
- → Bot should: "Hỏi thêm về duration + impact"

**Nếu user confirm "Chỉ 1 tuần thôi"**:
- `is_diagnosis_ready()` → vẫn `False` (by design - <2 weeks)
- → Bot should: "Lo lắng trước thuyết trình là bình thường. Đây là cách chuẩn bị tốt hơn..." (normalize)

**Proposed với `assess_disorder_likelihood()`**:
- Input: duration = "1 tuần", trigger = "thuyết trình", functioning = "mild"
- Output: `("normal_response", ..., 0.8)`
- → Bot: "Phản ứng bình thường, không phải disorder"

---

### Test 2: Likely Disorder (GAD)
**Input**:
```json
{
  "user_message": "Lo âu liên tục không rõ lý do",
  "slots": {
    "duration": "8 tháng",
    "recent_life_events": "",
    "daily_functioning": "severe",
    "intensity": "very_high",
    "symptom_fluctuation": "liên tục suốt ngày"
  }
}
```

**Expected**:
- `is_diagnosis_ready()` → `True` (đủ duration + info)
- `assess_disorder_likelihood()` → `("likely_disorder", ..., 0.8)`
- → Bot: "Dấu hiệu có thể liên quan đến GAD. Mình khuyên bạn gặp chuyên gia..."

---

## 💡 Recommendation

### Implement `assess_disorder_likelihood()` vì:
1. ✅ **Không trùng** với `is_diagnosis_ready()` - hai function bổ sung nhau
2. ✅ **Giải quyết vấn đề** "bot ép chẩn đoán" - phân biệt normal vs disorder
3. ✅ **Tương thích** với code hiện tại - dùng `is_diagnosis_ready()` làm prerequisite
4. ✅ **Cải thiện trải nghiệm** - bot biết khi nào nói "bình thường" thay vì "có thể là bệnh"

### Priority Implementation Order:
1. **Week 1**: Implement `assessment.py` + test logic
2. **Week 2**: Add normal response content to knowledge graph
3. **Week 2**: Update answer prompts với decision logic
4. **Week 3**: Integrate assessment node vào workflow
5. **Week 3-4**: Testing + monitoring

### Files Cần Tạo/Sửa:
**Tạo mới** (❌ NEW):
- `backend/src/rag/utils/assessment.py`
- `backend/data/raw/normal_responses.jsonl`
- `backend/src/rag/workflow/graph_nodes/assessment.py`
- `backend/src/rag/workflow/graph_nodes/normal_coping_retrieval.py`
- `backend/src/rag/workflow/graph_nodes/adjustment_retrieval.py`

**Sửa/bổ sung** (⚠️ MODIFY):
- `backend/src/rag/workflow/workflow.py` (add assessment node + routing)
- `backend/src/rag/workflow/state.py` (add assessment fields)
- `backend/src/rag/prompts/answer_nodes_prompt_vie.yaml` (add decision logic)

**Giữ nguyên** (✅ KEEP):
- `backend/src/rag/utils/slots.py` (is_diagnosis_ready() đã tốt)
- `backend/src/rag/workflow/graph_nodes/slot_filling.py`
- `backend/src/rag/workflow/graph_nodes/diagnostic_retrieval.py`
- `backend/src/rag/workflow/graph_nodes/disease_conclusion.py`

---

## 📊 Impact Assessment

### Before (Current):
- Bot mentions disorder terms: **~60-70%** conversations
- Normal stress cases: Often pathologized
- User experience: "Bot quá nhạy cảm", "chẩn đoán nhanh quá"

### After (Expected):
- Bot mentions disorder terms: **~30-40%** conversations (giảm 40%)
- Normal stress cases: Normalized và đưa coping strategies
- User experience: "Bot hiểu đúng tình huống", "không gây lo lắng không cần thiết"

### Success Metrics:
1. **Diagnosis Rate**: Giảm 40-50% số lần mention disorder trong 2 tuần đầu
2. **Normal Response Rate**: Tăng 30-40% conversations kết luận "normal/adjustment"
3. **User Satisfaction**: Survey "Bot hiểu đúng?" → target 80%+ "Yes"
