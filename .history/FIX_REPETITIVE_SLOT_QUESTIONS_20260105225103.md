# 🔧 FIX: Chatbot Asking Repetitive Slot Questions

## 🔴 VẤN ĐỀ (PROBLEM)

Chatbot liên tục hỏi lại về các slot đã có thông tin:

**Ví dụ từ cuộc hội thoại:**
- User đã trả lời `duration: "3-4 tuần"` → Bot vẫn hỏi lại "Cảm giác này kéo dài bao lâu?"
- User đã trả lời `substance_use: "cà phê 2-3 ly/ngày, rượu cuối tuần"` → Bot vẫn hỏi lại "Bạn có dùng cà phê, rượu...?"
- User đã trả lời `medical_history: "không có bệnh tim/thần kinh"` → Bot vẫn hỏi lại "Bạn có tiền sử bệnh lý...?"
- User đã nói `"không có biến cố lớn, chỉ công việc dồn"` → `recent_life_events` vẫn null → Bot hỏi lại

**State slots cho thấy thông tin đã được lưu:**
```
duration: "khoảng một tháng nay, đặc biệt rõ rệt trong hai tuần gần đây" ✓
substance_use: "cà phê (2-3 cốc/ngày), rượu (1-2 lon/ly cuối tuần)..." ✓
medical_history: "no heart check; no consultation for dizziness" ✓
recent_life_events: null ❌ (nhưng user đã nói "không có biến cố lớn")
```

---

## 🔍 NGUYÊN NHÂN (ROOT CAUSE)

### 1. **Prompt KHÔNG nhận được existing_slots**
Trong `slot_filling.py`, prompt chỉ có `QUESTION`:
```python
prompt = format_prompt(prompt_template, QUESTION=question)
```

**Vấn đề:** LLM không biết slot nào đã được fill từ các turn trước → cứ hỏi lại!

### 2. **Extraction logic không phân biệt "không có" vs null**
Khi user nói **"không có biến cố lớn"**, hệ thống extract thành `null` thay vì `"không có biến cố lớn"` → hệ thống nghĩ chưa hỏi → hỏi lại!

---

## ✅ GIẢI PHÁP (SOLUTION)

### **1. Truyền existing_slots vào prompt**

**File:** `backend/src/rag/llm/answer_nodes/slot_filling.py`

**Thay đổi:**
- ✅ Thêm parameter `existing_slots` vào `process_slot_filling()`
- ✅ Build context về slots đã fill để gửi cho LLM
- ✅ Append context vào prompt với warning: **"DO NOT ASK AGAIN"**

```python
async def process_slot_filling(question: str, existing_slots: Dict[str, Any] = None) -> Dict[str, Any]:
    # Build existing slots context to avoid re-asking
    existing_slots_str = ""
    if existing_slots:
        filled_slots = {k: v for k, v in existing_slots.items() 
                      if v not in [None, [], "none", "unknown"]}
        if filled_slots:
            existing_slots_str = "\n\n========== ALREADY FILLED SLOTS (DO NOT ASK AGAIN) ==========\n"
            for key, value in filled_slots.items():
                existing_slots_str += f"- {key}: {value}\n"
            existing_slots_str += "\n⚠️ CRITICAL: Do NOT include these slots in relevant_missing_slots...\n"
    
    # Format prompt with question and existing slots
    prompt = format_prompt(prompt_template, QUESTION=question) + existing_slots_str
```

### **2. Cập nhật slot_filling_node để truyền existing_slots**

**File:** `backend/src/rag/workflow/graph_nodes/slot_filling.py`

```python
# Call logic function with enhanced context to extract NEW slots from current turn
# Pass existing_slots so LLM knows what NOT to ask again
result = await process_slot_filling(enhanced_question, existing_slots=existing_slots)
```

### **3. Thêm instruction vào prompt**

**File:** `backend/src/rag/prompts/slot_filling_prompt.yaml`

**Thêm section mới sau USER QUESTION:**

```yaml
========== CRITICAL: AVOID RE-ASKING FILLED SLOTS ==========

⚠️ **IMPORTANT**: If a slot already has a value from previous turns (shown below as "ALREADY FILLED SLOTS"), you MUST:
1. PRESERVE that value in your "slots" output (do not set to null)
2. DO NOT include it in "relevant_missing_slots"
3. DO NOT ask follow-up questions about it

This prevents asking the user the same question multiple times!

Example: If "duration" already filled with "3-4 tuần", do NOT ask "Cảm giác này kéo dài bao lâu?" again.
```

### **4. Cải thiện extraction cho "negative responses"**

**Thêm EXAMPLE 2b vào prompt:**

```yaml
EXAMPLE 2b - User Says "No Major Events" (Extract as string, not null):
USER: "Không có biến cố gì quá lớn, chủ yếu là công việc dồn và em ngủ ít hơn bình thường."

OUTPUT:
{
  "slots": {
    ...
    "recent_life_events": "không có biến cố lớn, công việc dồn và ngủ ít",  // ⭐ EXTRACT even when "no major events"
    "current_stressors": ["công việc dồn", "thiếu ngủ"],
    ...
  }
}

EXPLANATION:
- ⭐ CRITICAL: When user says "no major events", extract it as a STRING value
- This ANSWERS the question - user confirmed no major life events
- Setting to null would make system ask again!
```

**Cập nhật slot definition:**
```yaml
- recent_life_events: str - Major life events (job loss, breakup, death, etc.) OR "không có biến cố lớn" if none reported
```

---

## 📊 KẾT QUẢ MONG ĐỢI (EXPECTED RESULTS)

### **Trước khi fix:**
```
Turn 1: Bot hỏi "Cảm giác này kéo dài bao lâu?"
Turn 2: User: "3-4 tuần"
Turn 3: Bot hỏi lại "Cảm giác này kéo dài bao lâu?" ❌
Turn 4: User: "Tôi đã nói rồi, 3-4 tuần" (frustrated)
```

### **Sau khi fix:**
```
Turn 1: Bot hỏi "Cảm giác này kéo dài bao lâu?"
Turn 2: User: "3-4 tuần"
       → duration filled
Turn 3: Bot nhận ra duration đã có → KHÔNG hỏi lại ✅
       → Hỏi về các slot khác chưa fill
```

### **Test case với "negative response":**
```
Turn 1: Bot hỏi "Có biến cố lớn nào gần đây không?"
Turn 2: User: "Không có biến cố gì, chỉ công việc dồn thôi"
       → recent_life_events: "không có biến cố lớn, công việc dồn"
Turn 3: Bot nhận ra đã được trả lời → KHÔNG hỏi lại ✅
```

---

## 🧪 TESTING

### **Test 1: Không hỏi lại slot đã fill**
```python
# Setup
state = {
    "slots": {
        "duration": "3-4 tuần",
        "substance_use": "cà phê 2-3 ly/ngày"
    }
}

# Action
result = await slot_filling_node(state)

# Expected
assert "duration" not in result["relevant_missing_slots"]
assert "substance_use" not in result["relevant_missing_slots"]
assert "Cảm giác này kéo dài bao lâu?" not in result["follow_up_questions"]
```

### **Test 2: Extract "không có" as value, not null**
```python
# User input
question = "Không có biến cố gì quá lớn, chủ yếu công việc dồn"

# Action
result = await process_slot_filling(question)

# Expected
assert result["slots"]["recent_life_events"] is not None
assert "không có biến cố lớn" in result["slots"]["recent_life_events"]
assert "recent_life_events" not in result["missing_slots"]
```

### **Test 3: Merge preserves existing values**
```python
existing = {"duration": "3 tuần", "emotion": ["lo lắng"]}
new = {"intensity": "high", "emotion": ["buồn"]}

merged = merge_slots(existing, new)

assert merged["duration"] == "3 tuần"  # Preserved
assert "lo lắng" in merged["emotion"]  # Preserved
assert "buồn" in merged["emotion"]     # Added
assert merged["intensity"] == "high"   # Added
```

---

## 📝 FILES CHANGED

1. ✅ `backend/src/rag/llm/answer_nodes/slot_filling.py`
   - Added `existing_slots` parameter
   - Build existing slots context string
   - Append to prompt

2. ✅ `backend/src/rag/workflow/graph_nodes/slot_filling.py`
   - Pass `existing_slots` to `process_slot_filling()`

3. ✅ `backend/src/rag/prompts/slot_filling_prompt.yaml`
   - Added "AVOID RE-ASKING FILLED SLOTS" section
   - Added EXAMPLE 2b for negative responses
   - Updated `recent_life_events` definition

---

## 🚀 DEPLOYMENT

1. **Restart backend container:**
   ```bash
   docker compose restart backend
   ```

2. **Test với cuộc hội thoại mẫu:**
   - User: "Dạo này mình hay lo lắng"
   - Bot: "Cảm giác này kéo dài bao lâu?"
   - User: "Khoảng 3 tuần"
   - Bot: (should NOT ask about duration again)

3. **Monitor logs:**
   ```bash
   docker compose logs -f backend | grep "SLOT FILLING"
   ```

---

## 📚 RELATED ISSUES

- Slot persistence across turns
- Conversation memory
- Follow-up question filtering

---

## ✅ CHECKLIST

- [x] Identify root cause (prompt không nhận existing_slots)
- [x] Implement solution (truyền existing_slots vào prompt)
- [x] Update prompt with instructions
- [x] Add example for negative responses
- [x] Test locally
- [ ] Deploy to staging
- [ ] User acceptance testing
- [ ] Deploy to production
- [ ] Monitor for regression

---

**Date:** 2026-01-05  
**Author:** GitHub Copilot  
**Status:** ✅ FIXED - Ready for testing
