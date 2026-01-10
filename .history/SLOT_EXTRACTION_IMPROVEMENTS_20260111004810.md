# Slot Extraction Improvements - Fix Repetitive Questions

## Vấn đề (Problem)

Hệ thống slot filling đang gặp vấn đề **trích xuất kém** (poor extraction), dẫn đến việc hỏi lặp lại các câu hỏi mà người dùng đã trả lời:

### Các slot bị ảnh hưởng:
- **Slot 10 (self_care_functioning)**: Người dùng đã nói "lười nhai, sụt cân" và "đấu tranh mới đi tắm được" nhưng hệ thống vẫn hỏi lại về ăn uống/vệ sinh
- **Slot 12 (medical_history_any)**: Người dùng đã khẳng định "không có bệnh nền" nhưng vẫn bị hỏi lại
- **Slot 14 & 20 (substance_use_any / caffeine_nicotine_use)**: Người dùng đã nói "không dùng chất kích thích gì" nhưng vẫn bị hỏi lại
- **Slot 15 (frequency)**: Người dùng đã nói "hàng ngày, gần như cả ngày" nhưng vẫn bị hỏi lại

## Nguyên nhân (Root Cause)

### 1. Prompt không nhấn mạnh semantic extraction
- LLM chỉ được hướng dẫn extract từ USER INPUT hiện tại
- Không có instruction rõ ràng về việc RE-EXTRACT từ conversation history

### 2. Context không đủ chi tiết
- `existing_slots_str` chỉ show các slot đã filled
- Không show **nội dung conversation history** để LLM có thể re-extract

### 3. Thiếu post-processing validation
- Không có logic kiểm tra xem thông tin đã xuất hiện trong conversation hay chưa
- Không có fallback để catch information LLM bỏ sót

## Giải pháp (Solution)

### ✅ Cải tiến 1: Enhance Prompt với Semantic Extraction Instructions

**File**: `backend/src/rag/prompts/slot_filling_prompt.yaml`

**Thay đổi**:
```yaml
🔍 **SEMANTIC EXTRACTION FROM ENTIRE CONVERSATION**: 
- You MUST scan the ENTIRE USER INPUT (including previous conversation turns if present)
- Extract information EVEN IF it appeared in previous turns, not just current question
- Re-extract previously mentioned information that wasn't captured in ALREADY FILLED SLOTS
- Use semantic understanding to infer slot values from context
```

**Thêm Examples**:
```yaml
🔍 EX-NEW1 - RE-EXTRACT from previous conversation (self_care_functioning):
USER INPUT:
Previous: Q: "How are you doing?" A: "I'm lazy to chew food, losing weight, and have to struggle to take a shower."
Current: "What about your eating habits?"
ALREADY FILLED: {}
EXTRACT:
  self_care_functioning = ["difficulty with eating - lazy to chew", "weight loss", "difficulty with hygiene - struggle to shower"]
  appetite_changes = ["decreased appetite", "weight loss"]
WHY: Even though bot is asking about eating, MUST re-extract ALL self-care info from previous answer
```

### ✅ Cải tiến 2: Enhanced Context Building

**File**: `backend/src/rag/llm/answer_nodes/slot_filling.py`

**Thay đổi**:
```python
# Add reminder about semantic extraction
existing_slots_str += "\n\n🔍 REMINDER: Scan the ENTIRE conversation above (including previous Q&A pairs) to extract ALL mentioned information.\n"
existing_slots_str += "Even if information was mentioned in previous turns, if it's NOT in ALREADY FILLED SLOTS → extract it NOW.\n"
```

**Mục đích**: Nhắc LLM phải quét toàn bộ conversation, không chỉ câu hỏi hiện tại.

### ✅ Cải tiến 3: Post-Processing Slot Extraction

**File**: `backend/src/rag/workflow/graph_nodes/slot_filling.py`

**Thêm hàm**: `_post_process_slot_extraction()`

**Chức năng**:
- Sử dụng **regex patterns** và **keyword matching** để catch thông tin rõ ràng mà LLM bỏ sót
- Xử lý các patterns phổ biến:
  - "no medical conditions" → `medical_history_any = "no"`
  - "don't use stimulants" → `substance_use_any = "no"`
  - "every day" → `frequency = ["daily"]`
  - "struggle to shower", "lazy to eat" → `self_care_functioning`

**Pattern examples**:
```python
# PATTERN 1: Medical history
no_medical_patterns = [
    r"no\s+(underlying\s+)?(medical\s+)?(conditions?|diseases?|illness)",
    r"không\s+có\s+bệnh\s+nền",
]

# PATTERN 2: Substance use
no_substance_patterns = [
    r"(don't|do not)\s+use\s+(any\s+)?(substances?|drugs?|stimulants?)",
    r"không\s+dùng\s+chất\s+kích\s+thích",
]

# PATTERN 5: Self-care
hygiene_patterns = [
    (r"(struggle|hard)\s+to\s+(shower|bathe)", "difficulty with hygiene - struggle to shower"),
    (r"lười\s+(nhai|ăn)", "difficulty with eating - lazy to chew"),
    (r"sụt\s+cân", "weight loss")
]
```

### ✅ Cải tiến 4: Filter Redundant Questions

**File**: `backend/src/rag/workflow/graph_nodes/request_more_info.py`

**Thêm hàm**: `filter_redundant_questions()`

**Chức năng**:
- Loại bỏ các câu hỏi về slot đã được fill
- Sử dụng keyword matching để detect xem câu hỏi có liên quan đến slot nào

**Keyword mapping**:
```python
slot_keywords = {
    "self_care_functioning": ["ăn uống", "vệ sinh", "tắm", "chăm sóc"],
    "medical_history_any": ["bệnh nền", "tiền sử", "bệnh lý"],
    "substance_use_any": ["chất kích thích", "ma túy", "rượu"],
    "caffeine_nicotine_use": ["cà phê", "cafe", "thuốc lá"],
    "frequency": ["tần suất", "bao lâu", "mỗi ngày"],
}
```

**Logic**:
```python
for question in questions:
    for slot_name, keywords in slot_keywords.items():
        slot_value = slots.get(slot_name)
        if not is_empty_slot(slot_value):  # Slot already filled
            if any(kw in question.lower() for kw in keywords):
                # Skip this question (redundant)
                continue
```

## Workflow mới (New Flow)

```
1. User input arrives
   ↓
2. Build enhanced context with conversation history
   ↓
3. LLM extraction với semantic instructions
   ↓
4. Post-processing: Catch obvious patterns LLM missed
   ↓
5. Merge với existing slots
   ↓
6. Filter redundant questions về slots đã filled
   ↓
7. Return cleaned follow-up questions
```

## Testing

Chạy test suite để verify:
```bash
cd /app
python test_slot_extraction_improvements.py
```

**Test cases**:
1. ✅ Self-care functioning extraction from previous turn
2. ✅ Medical history "no" detection
3. ✅ Frequency extraction from "every day" mention
4. ✅ Post-processing pattern matching

## Expected Results

### Before Fix:
```
Turn 1: User: "Tôi lười nhai, sụt cân, đấu tranh mới tắm được"
Turn 2: Bot: "Bạn cảm thấy thế nào về việc ăn uống?"
Turn 3: Bot: "Việc ăn uống và vệ sinh cá nhân của bạn thế nào?" ❌ (asking again!)
```

### After Fix:
```
Turn 1: User: "Tôi lười nhai, sụt cân, đấu tranh mới tắm được"
Turn 2: Bot: "Bạn cảm thấy thế nào về việc ăn uống?"
[System extracts: self_care_functioning = ["difficulty eating - lazy to chew", "weight loss", "struggle to shower"]]
Turn 3: Bot: "Tình trạng này kéo dài bao lâu rồi?" ✅ (asks different question)
```

## Files Modified

1. ✅ `backend/src/rag/prompts/slot_filling_prompt.yaml`
   - Added semantic extraction instructions
   - Added re-extraction examples

2. ✅ `backend/src/rag/llm/answer_nodes/slot_filling.py`
   - Enhanced context building with extraction reminders

3. ✅ `backend/src/rag/workflow/graph_nodes/slot_filling.py`
   - Added `_post_process_slot_extraction()` function
   - Integrated post-processing into workflow

4. ✅ `backend/src/rag/workflow/graph_nodes/request_more_info.py`
   - Added `filter_redundant_questions()` function
   - Integrated filtering before returning questions

5. ✅ `backend/test_slot_extraction_improvements.py` (NEW)
   - Test suite to verify improvements

## Impact

### Positive:
- ✅ Giảm câu hỏi lặp lại → Better user experience
- ✅ Trích xuất chính xác hơn → Fewer turns needed
- ✅ Tận dụng semantic understanding của LLM
- ✅ Có fallback với pattern matching cho các trường hợp rõ ràng

### Trade-offs:
- ⚠️ Thêm computational cost (post-processing regex)
- ⚠️ Cần maintain keyword mappings khi thêm slot mới

## Maintenance

Khi thêm slot mới:
1. Update `slot_keywords` trong `filter_redundant_questions()`
2. Add regex patterns vào `_post_process_slot_extraction()` nếu cần
3. Update prompt examples nếu slot phức tạp

## Monitoring

Check logs để monitor:
```python
logger.info(f"[POST-PROCESS] Detected {slot_name}='{value}' from pattern: {pattern}")
logger.info(f"[FILTER] Removed redundant question about {slot_name}")
```

---

**Date**: 2026-01-11  
**Version**: 1.0  
**Status**: ✅ Implemented & Tested
