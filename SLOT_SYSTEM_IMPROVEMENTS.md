# Cải Tiến Hệ Thống Slot Filling - Tránh Chẩn Đoán Sớm

## Tổng Quan

Đã cải tiến hệ thống slot filling để tránh việc chatbot "đóng chẩn đoán" quá nhanh. Hệ thống mới tập trung vào **đánh giá và hỗ trợ** thay vì chẩn đoán y khoa sớm.

## Các Thay Đổi Chính

### 1. Cập Nhật `slots.py`

#### A. Thêm DIAGNOSTIC_SLOTS và Cập Nhật REQUIRED_SLOTS

```python
DIAGNOSTIC_SLOTS = {
    "symptoms": ["emotion", "primary_mood", "physical_symptoms", "intensity"],
    "context": ["duration", "trigger", "impact", "daily_functioning"],
    "differential": [
        "substance_use",        # Rượu/cafein/chất kích thích
        "medical_history",      # Bệnh nền tim mạch, tuyến giáp
        "recent_life_events",   # Biến cố lớn: mất việc, chia tay
        "symptom_fluctuation"   # Liên tục hay ngắt quãng
    ]
}

REQUIRED_SLOTS = [
    "emotion",
    "duration",
    "impact", 
    "intensity",
    "recent_life_events"  # ⭐ MỚI - bắt buộc để phân biệt stress vs disorder
]
```

**Lý do**: Thêm `recent_life_events` vào REQUIRED để buộc hệ thống kiểm tra biến cố sống trước khi kết luận bệnh lý.

#### B. Sửa `get_default_slots()` - Risk Level Unknown

```python
"risk_level": "unknown",  # Changed from "none" → tránh "ảo giác an toàn"

# Thêm các slot differential mới:
"substance_use": None,
"medical_history": None,
"recent_life_events": None,
"symptom_fluctuation": None,
"history_of_trauma": None,

# Derived fields để kiểm soát chẩn đoán:
"diagnostic_confidence": "low",
"potential_differentials": [],
"duration_certainty": "vague",
```

**Lý do**: `risk_level="none"` mặc định khiến hệ thống bỏ qua câu hỏi an toàn. `"unknown"` buộc phải đánh giá.

#### C. Fix `merge_slots()` - Dedup List và Max Severity

**Vấn đề cũ**:
- List dedup không đúng (không update set sau khi append)
- Scalar luôn overwrite → mất "đỉnh nặng nhất" (severity peak)

**Giải pháp**:
```python
# List dedup đúng cách
existing_set = set(existing_value)
for item in new_value:
    if item and item not in existing_set:
        merged[key].append(item)
        existing_set.add(item)  # ⭐ FIX: Update set

# Scalar severity fields: merge by "max severity wins"
SEVERITY_ORDER = {
    "risk_level": ["unknown", "none", "low", "medium", "high"],
    "intensity": ["low", "medium", "high", "very_high"],
    "stress_level": ["low", "moderate", "high", "overwhelming"]
}
# Keep higher severity instead of latest
```

#### D. Thêm `validate_duration()` - Kiểm Tra Duration Cụ Thể

```python
def validate_duration(duration_text: Optional[str]) -> Tuple[bool, str]:
    """
    Kiểm tra xem duration có cụ thể không.
    
    Returns:
        (is_specific, certainty_level)
        - "vague": "lately", "dạo này" → NOT sufficient
        - "approximate": "vài tuần", "khoảng 1 tháng" → acceptable
        - "specific": "2 tháng", "từ tháng 10" → best
    """
```

**Lý do**: Duration "dạo này" quá mơ hồ để chẩn đoán. Hàm này chặn các giá trị không đủ tiêu chuẩn.

#### E. Sửa `has_sufficient_slots()` - Fix Bug Logic và Differential Check

**Bug cũ**: Docstring nói "allow max 1 missing" nhưng code `<= 0` (không thiếu gì)

**Giải pháp**:
```python
# Fixed logic: Allow max 1 required slot missing
is_sufficient = len(required_missing) <= 1 and len(differential_missing) <= 1

# Special duration validation
if slot_name == "duration":
    is_specific, certainty = validate_duration(value)
    if not is_specific:
        required_missing.append("specific_duration")

# Differential check: If physical symptoms → MUST check medical
if physical_symptoms and len(physical_symptoms) > 0:
    if not slots.get("medical_history") and not slots.get("substance_use"):
        differential_missing.append("medical_exclusion")
```

**Lý do**: Nếu user kể "tim đập nhanh", PHẢI hỏi bệnh tim/tuyến giáp/cafein trước khi nghĩ đến lo âu.

#### F. Sửa `get_slot_keywords()` - Stage-Aware Keywords

**Vấn đề cũ**: Có emotion là thêm "anxiety", "depression" → retrieval kéo tài liệu chẩn đoán quá sớm

**Giải pháp**:
```python
# Check if diagnosis-ready first
diagnosis_ready = is_diagnosis_ready(slots)

if emotions:
    keywords.extend([e.lower() for e in emotions])
    # Always add coping keywords
    keywords.extend(["mood", "feeling", "coping", "stress management"])
    
    if diagnosis_ready:
        keywords.extend(["anxiety", "depression", "disorder"])
    else:
        # Focus on stress/adjustment/coping
        keywords.extend(["stress", "adjustment", "support", "wellbeing"])
```

**Lý do**: Chỉ thêm keyword disorder khi đủ tiêu chuẩn (duration dài + impairment rõ + đã loại trừ differential).

#### G. Thêm `is_diagnosis_ready()` - Gate Chẩn Đoán

```python
def is_diagnosis_ready(slots: Dict[str, Any]) -> bool:
    """
    Chỉ trả về True khi:
    1. Duration cụ thể và dài (≥2 weeks cho hầu hết disorders)
    2. Có impairment rõ ràng (daily_functioning hoặc work_school_impact)
    3. Đã loại trừ nguyên nhân vật lý/substance
    4. Có pattern ổn định (không phải acute stress)
    """
```

**Mục đích**: Gate này quyết định khi nào hệ thống được phép đi vào "nhánh chẩn đoán disorder-specific".

**Ví dụ sử dụng**:
- `get_slot_keywords()`: Chỉ thêm "disorder" keyword khi `is_diagnosis_ready() = True`
- Trong workflow: Chỉ trigger retrieval chẩn đoán khi gate này pass

#### H. Cập Nhật `build_slot_context()` - Hiển Thị Differential Info

```python
# Add differential info to context
if slots.get("recent_life_events"):
    context_parts.append(f"Recent life events: {slots['recent_life_events']}")
if slots.get("substance_use"):
    context_parts.append(f"Substance use: {slots['substance_use']}")
if slots.get("medical_history"):
    context_parts.append(f"Medical history: {slots['medical_history']}")

# Add diagnostic caution flag
diagnostic_confidence = slots.get("diagnostic_confidence", "low")
context_parts.append(f"⚠️ Diagnostic confidence: {diagnostic_confidence}")
```

**Lý do**: Context này được truyền vào LLM khi sinh câu trả lời. Hiển thị confidence thấp sẽ nhắc LLM tránh kết luận chắc chắn.

---

### 2. Cập Nhật `slot_filling_prompt.yaml`

#### A. Thêm Safety Rule Ở Đầu Prompt

```yaml
⚠️ CRITICAL SAFETY RULE: Your role is ASSESSMENT and SUPPORT, NOT DIAGNOSIS. 
Avoid premature diagnostic conclusions.
```

#### B. Cập Nhật REQUIRED_SLOTS và Thêm DIFFERENTIAL SLOTS

```yaml
REQUIRED SLOTS (HIGHEST PRIORITY):
1. emotion
2. duration (MUST be specific, not vague like "lately")
3. impact
4. intensity
5. recent_life_events (CRITICAL: differentiate stress vs disorder)

DIFFERENTIAL DIAGNOSIS SLOTS (CRITICAL FOR SAFETY):
9. substance_use
10. medical_history
11. symptom_fluctuation

⚠️ DIFFERENTIAL RULE: If physical symptoms → MUST ask about medical_history 
and substance_use to rule out physical causes first.
```

#### C. Thêm Các Slots Mới Vào Schema

```yaml
# Differential diagnosis slots
- substance_use: str - Alcohol/caffeine/drugs
- medical_history: str - Physical conditions (thyroid, heart, etc.)
- recent_life_events: str - Major life events (job loss, breakup, etc.)
- symptom_fluctuation: str - Pattern: continuous/episodic/triggered
- history_of_trauma: str

# Derived fields
- diagnostic_confidence: str - "low", "medium", "high"
- duration_certainty: str - "vague", "approximate", "specific"
- potential_differentials: List[str]
```

#### D. Cập Nhật Output Format

```yaml
"risk_level": "unknown",  # Changed from "none"
"substance_use": null,
"medical_history": null,
"recent_life_events": null,
# ... (thêm tất cả slots mới)
```

#### E. Cải Thiện Examples với Differential Thinking

**Example 1 - Work Anxiety (Fixed)**:
```yaml
USER: "Dạo này mình cảm thấy rất lo lắng khi đi làm..."

BEFORE: duration="dạo này" được chấp nhận → retrieval → chẩn đoán sớm

AFTER:
- duration="dạo này" → duration_certainty="vague"
- relevant_missing_slots: ["specific_duration", "recent_life_events"]
- follow_up: "Cảm giác này kéo dài bao lâu? Vài ngày, tuần hay tháng?"
- follow_up: "Có chuyện gì đặc biệt xảy ra ở công ty gần đây không?"
- potential_differentials: ["work stress", "adjustment disorder", "GAD"]
```

**Example 2 - Physical Symptoms (Fixed)**:
```yaml
USER: "Tim đập nhanh, mất ngủ..."

BEFORE: Thiếu check medical_history → kết luận GAD

AFTER:
- physical_symptoms: ["tim đập nhanh"] detected
- relevant_missing_slots: ["medical_history", "substance_use"] (PRIORITY)
- follow_up: "Bạn có dùng cà phê/nước tăng lực nhiều không?"
- follow_up: "Bạn có tiền sử bệnh tuyến giáp hoặc tim mạch không?"
- potential_differentials: ["caffeine excess", "hyperthyroidism", "anxiety"]
```

---

## Cơ Chế Hoạt Động

### Workflow Mới

```
1. User input → Slot Extraction
   ↓
2. validate_duration() → Check duration quality
   - "dạo này" → vague → ask for specific
   - "2 tháng" → specific → proceed
   ↓
3. has_sufficient_slots() → Check completeness
   - Required slots filled? (allow max 1 missing)
   - Physical symptoms? → Check differential
   ↓
4. is_diagnosis_ready()? → Determine readiness
   - YES → Use disorder-specific keywords & retrieval
   - NO → Use coping/stress management keywords
   ↓
5. build_slot_context() → Pass to LLM
   - Include differential info
   - Show diagnostic_confidence level
   ↓
6. LLM generates response
   - Sees confidence=low → Avoids definitive diagnosis
   - Sees recent_life_events → Considers stress/adjustment
```

### Logic Gates

**Gate A: Sufficient for Support Response**
```python
has_sufficient_slots() → True
# Can provide supportive response/ask follow-up
# BUT not ready for diagnosis yet
```

**Gate B: Ready for Diagnosis**
```python
is_diagnosis_ready() → True
# Duration ≥ 2 weeks + specific
# Impairment clear (moderate/severe)
# Differential checked (medical/substance)
# No acute crisis markers
```

---

## Kết Quả Mong Đợi

### Trước (OLD Behavior)

**Lượt 1**:
- User: "Dạo này lo lắng khi đi làm"
- Bot: ❌ "Bạn có thể đang gặp Rối loạn lo âu lan tỏa (GAD)..."

**Lượt 1** (Physical):
- User: "Tim đập nhanh, mất ngủ"
- Bot: ❌ "Đây là triệu chứng của rối loạn lo âu..."

### Sau (NEW Behavior)

**Lượt 1-2**:
- User: "Dạo này lo lắng khi đi làm"
- Bot: ✅ "Mình hiểu bạn đang cảm thấy lo lắng. Cảm giác này kéo dài bao lâu rồi - vài ngày, tuần hay tháng?"
- User: "Khoảng 3 tuần"
- Bot: ✅ "Có chuyện gì đặc biệt xảy ra ở công ty trong thời gian này không?"

**Lượt 1-2** (Physical):
- User: "Tim đập nhanh, mất ngủ"
- Bot: ✅ "Bạn có đang dùng nhiều cà phê hoặc nước tăng lực không? Hoặc có tiền sử bệnh tuyến giáp, tim mạch không?"
- User: "Uống cà phê nhiều lắm"
- Bot: ✅ "Cafein có thể gây tim đập nhanh và mất ngủ. Có thể thử giảm..."

**Lượt 3+** (Nếu đủ tiêu chuẩn):
- Sau khi confirm: duration ≥ 2 weeks, no acute event, impairment clear, medical ruled out
- Bot: ✅ "Dựa trên những gì bạn chia sẻ, các dấu hiệu này **có thể** liên quan đến lo âu kéo dài. Tuy nhiên, để chắc chắn, bạn nên gặp chuyên gia tâm lý..."

---

## Checklist Kiểm Tra

- [x] `risk_level` default = "unknown" (không còn "none")
- [x] `get_slot_keywords()` chỉ thêm disorder keyword khi `is_diagnosis_ready() = True`
- [x] `has_sufficient_slots()` fix bug `<= 0` → `<= 1`
- [x] `has_sufficient_slots()` check differential khi có physical symptoms
- [x] `merge_slots()` fix dedup list (update set after append)
- [x] `merge_slots()` merge severity theo "max wins"
- [x] Thêm `validate_duration()` để reject "dạo này", "lately"
- [x] Thêm `is_diagnosis_ready()` gate
- [x] `build_slot_context()` hiển thị differential info + confidence
- [x] Prompt thêm DIFFERENTIAL RULE
- [x] Prompt examples updated với differential thinking
- [x] `REQUIRED_SLOTS` bao gồm `recent_life_events`

---

## Testing Checklist

### Test Case 1: Vague Duration
```
Input: "Dạo này mình buồn"
Expected:
- duration_certainty = "vague"
- relevant_missing_slots = ["specific_duration", "recent_life_events"]
- Follow-up asks: "Kéo dài bao lâu? Vài ngày, tuần, tháng?"
```

### Test Case 2: Physical Symptoms
```
Input: "Tim đập nhanh, mệt"
Expected:
- physical_symptoms = ["tim đập nhanh", "mệt"]
- relevant_missing_slots = ["medical_history", "substance_use"]
- Follow-up: "Có dùng cafein/thuốc không? Có bệnh tim/tuyến giáp không?"
```

### Test Case 3: Recent Life Event
```
Input: "Chia tay người yêu tuần trước, giờ buồn lắm"
Expected:
- recent_life_events = "chia tay tuần trước"
- is_diagnosis_ready() = False (too acute)
- Keywords: ["stress", "adjustment", "coping"] NOT ["depression", "disorder"]
```

### Test Case 4: Chronic + Impairment
```
Input: "Lo âu 3 tháng nay, không làm việc được, không ngủ được"
Expected:
- duration = "3 tháng" (specific)
- daily_functioning = "moderate/severe"
- After checking differential → is_diagnosis_ready() = True
- Keywords can include ["anxiety", "disorder"]
```

---

## Lưu Ý Quan Trọng

1. **Không Chẩn Đoán Y Khoa**: Hệ thống vẫn KHÔNG được phép đưa ra chẩn đoán xác định. Chỉ có thể nói "dấu hiệu **có thể** liên quan đến..."

2. **Ưu Tiên An Toàn**: Nếu có suicidal ideation, bỏ qua mọi rule khác và ưu tiên hỏi về support_system + recent_events.

3. **Workflow Integration**: Code workflow/agent cần check `is_diagnosis_ready()` trước khi trigger retrieval chẩn đoán disorder-specific.

4. **Prompt Answer Generation**: Cần cập nhật prompt sinh câu trả lời để hiểu `diagnostic_confidence` và `duration_certainty` trong context.

---

## File Đã Thay Đổi

1. `backend/src/rag/utils/slots.py` - Toàn bộ logic
2. `backend/src/rag/prompts/slot_filling_prompt.yaml` - Prompt và examples

## Tác Giả & Ngày

- Cập nhật: 2026-01-03
- Mục tiêu: Tránh chẩn đoán sớm, tăng an toàn y đức
