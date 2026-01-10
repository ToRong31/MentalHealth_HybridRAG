# 🎯 KỊCH BẢN: Thêm Empathy Preamble vào Request More Info

## 📋 Tóm tắt thay đổi

**Vấn đề hiện tại:**
- `request_more_info_node` dùng câu mở đầu cố định, generic: "Để tôi có thể hỗ trợ bạn tốt hơn, bạn có thể chia sẻ thêm về:"
- Thiếu tính đồng cảm, không phản chiếu lại trải nghiệm người dùng

**Giải pháp:**
- Thêm câu đồng cảm (empathy preamble) được LLM tạo ra dựa trên context
- Fallback thông minh nếu LLM không tạo hoặc thiếu dữ liệu
- Giữ nguyên rule: tối đa 3 câu hỏi/turn

---

## 🏗️ KIẾN TRÚC THAY ĐỔI

### 1. Thêm field mới vào State

**File:** `backend/src/rag/workflow/state.py`

```python
# Thêm vào class KGState
empathy_preamble_vi: Optional[str]  # Câu đồng cảm tiếng Việt (1-2 câu)
```

**Lý do:**
- Cần lưu câu đồng cảm để dùng ở request_more_info_node
- Được tạo bởi LLM trong slot_filling

---

### 2. Cập nhật Slot Filling Prompt

**File:** `backend/src/rag/prompts/slot_filling_prompt.yaml`

#### 2.1. Thêm section mới TRƯỚC "OUTPUT JSON SCHEMA"

```yaml
  ========== EMPATHY PREAMBLE (ĐỒNG CẢM) ==========
  
  **Mục đích:** Tạo 1-2 câu tiếng Việt để phản chiếu & công nhận trải nghiệm của người dùng
  
  **Yêu cầu bắt buộc:**
  - ✅ Viết bằng tiếng Việt
  - ✅ 1-2 câu ngắn gọn (không quá dài)
  - ✅ Phản chiếu lại USER INPUT + ALREADY FILLED SLOTS
  - ✅ Nhắc đến ít nhất 1 chi tiết cụ thể nếu có dữ liệu (cảm xúc / bối cảnh / tác động)
  - ❌ KHÔNG chẩn đoán hoặc phán xét
  - ❌ KHÔNG "dạy đời" hoặc đưa ra lời khuyên
  - ❌ KHÔNG đặt câu hỏi trong empathy_preamble
  - ❌ KHÔNG bịa chi tiết nếu không có thông tin
  
  **Cấu trúc empathy tốt:**
  - Pattern 1: "Mình nghe bạn [đang trải qua X], [điều đó] [ảnh hưởng Y]."
  - Pattern 2: "Có vẻ [tình huống X] đang khiến bạn [cảm xúc/tác động Y]."
  - Pattern 3: "Nghe bạn chia sẻ, [chi tiết cụ thể X] hẳn là [validation Y]."
  
  **Ví dụ empathy_preamble_vi:**
  
  EX1 - Có cảm xúc + trigger:
  USER: "Tôi cảm thấy rất lo lắng vì deadline công việc"
  SLOTS: emotion=["anxious"], trigger=["work deadline"]
  EMPATHY: "Mình nghe bạn đang cảm thấy lo lắng vì áp lực deadline công việc, điều đó hẳn đang khiến bạn khá căng thẳng."
  
  EX2 - Có presenting_problem + impact:
  USER: "Tôi khó ngủ và không tập trung được việc"
  SLOTS: presenting_problem=["insomnia"], work_school_impact=["difficulty concentrating"]
  EMPATHY: "Có vẻ việc khó ngủ đang ảnh hưởng khá nhiều đến khả năng tập trung và công việc của bạn."
  
  EX3 - Có emotion + duration + intensity:
  USER: "Tôi buồn và mệt mỏi suốt 2 tuần nay"
  SLOTS: emotion=["sad"], duration=["2 weeks"], intensity=["severe"]
  EMPATHY: "Mình nghe bạn đã phải chịu đựng cảm giác buồn bã và mệt mỏi trong suốt 2 tuần qua, điều đó thật sự rất nặng nề."
  
  EX4 - Ít dữ liệu (câu đồng cảm chung, không bịa):
  USER: "Tôi cần giúp đỡ"
  SLOTS: {} (empty)
  EMPATHY: "Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng."
  
  EX5 - Có nhiều chi tiết (chọn 1-2 quan trọng nhất):
  USER: "Mất việc 1 tháng trước, giờ lo lắng, khó ngủ, tránh bạn bè"
  SLOTS: recent_life_events=["job loss 1 month ago"], emotion=["anxious"], sleep_quality=["poor"], social_functioning=["avoiding friends"]
  EMPATHY: "Mình nghe bạn đã phải đối mặt với việc mất việc làm gần đây, và điều đó đang ảnh hưởng đến nhiều khía cạnh trong cuộc sống của bạn."
  
  **Validation checklist:**
  [ ] Câu empathy có phản ánh ít nhất 1 chi tiết từ USER INPUT hoặc SLOTS?
  [ ] Có tránh chẩn đoán/phán xét/lời khuyên không?
  [ ] Không có câu hỏi trong empathy_preamble?
  [ ] Nếu không có dữ liệu, đã dùng câu chung (không bịa chi tiết)?
```

#### 2.2. Cập nhật OUTPUT JSON SCHEMA

```yaml
  ========== OUTPUT JSON SCHEMA ==========
  
  Return ONLY valid JSON in this exact format (all fields must be present):
  
  {
    "empathy_preamble_vi": "",
    "slots": {
      "presenting_problem": [],
      "emotion": [],
      # ... (all existing slots)
    },
    "missing_slots": [],
    "relevant_missing_slots": [],
    "follow_up_questions": []
  }

  ⚠️ CRITICAL OUTPUT RULES: 
  - **empathy_preamble_vi**: STRING, always present (1-2 Vietnamese sentences)
  - **ALL other fields must be present in output**
  - **Lists must be arrays []**, tri-states must be "yes"/"no"/"unknown"
  - **Follow-up questions**: Array of strings in **VIETNAMESE** (user's language)
```

---

### 3. Cập nhật Slot Filling Processing

**File:** `backend/src/rag/llm/answer_nodes/slot_filling.py`

#### 3.1. Parse empathy_preamble từ LLM response

**Location:** Trong hàm `process_slot_filling()`, sau khi parse JSON

```python
# Line ~80, sau khi có result từ JSON
slots = result.get("slots", get_default_slots())
missing_slots = result.get("missing_slots", [])
relevant_missing_slots = result.get("relevant_missing_slots", [])
follow_up_questions = result.get("follow_up_questions", [])

# ========== NEW: Parse empathy_preamble ==========
empathy_preamble_vi = result.get("empathy_preamble_vi", "")

# Validate empathy (không được là câu hỏi)
if empathy_preamble_vi and "?" in empathy_preamble_vi:
    logger.warning(f"⚠️ Empathy preamble contains question mark: '{empathy_preamble_vi}'")
    logger.warning("   Empathy should not be a question - using fallback")
    empathy_preamble_vi = ""  # Clear invalid empathy

logger.info(f"\n💙 Empathy preamble: {empathy_preamble_vi if empathy_preamble_vi else '(not generated)'}")
# ========== END NEW ==========
```

#### 3.2. Return empathy_preamble trong result

**Location:** Cuối hàm `process_slot_filling()`, trong return statement

```python
return {
    "slots": slots,
    "missing_slots": missing_slots,
    "relevant_missing_slots": relevant_missing_slots,
    "follow_up_questions": follow_up_questions,
    "empathy_preamble_vi": empathy_preamble_vi  # NEW
}
```

#### 3.3. Update error fallbacks

**Location:** Các exception handlers (line ~120-140)

```python
# Tất cả error returns cần thêm empathy_preamble_vi
return {
    "slots": get_default_slots(),
    "missing_slots": [],
    "relevant_missing_slots": [],
    "follow_up_questions": [],
    "empathy_preamble_vi": ""  # NEW
}
```

---

### 4. Cập nhật Slot Filling Node

**File:** `backend/src/rag/workflow/graph_nodes/slot_filling.py`

#### 4.1. Propagate empathy_preamble to state

**Location:** Trong hàm `slot_filling_node()`, sau khi có result

```python
# Line ~93, sau await process_slot_filling()
result = await process_slot_filling(enhanced_question, existing_slots=existing_slots)
new_slots = result.get("slots", {})

# NEW: Get empathy_preamble
empathy_preamble_vi = result.get("empathy_preamble_vi", "")
```

#### 4.2. Add to result dict

**Location:** Cuối hàm, before return

```python
# Line ~160+, thêm vào result
result["empathy_preamble_vi"] = empathy_preamble_vi

logger.info(f"[DEBUG] Returning result with has_sufficient_slots = {result.get('has_sufficient_slots')}")
logger.info(f"[DEBUG] Empathy preamble: {empathy_preamble_vi[:80] if empathy_preamble_vi else '(none)'}")
```

---

### 5. Cập nhật Request More Info Node (CORE CHANGE)

**File:** `backend/src/rag/workflow/graph_nodes/request_more_info.py`

#### 5.1. Thêm Emotion Mapping Dictionary

**Location:** Đầu file, sau SLOT_QUESTIONS

```python
# Emotion mapping: English → Vietnamese
EMOTION_MAP = {
    "anxious": "lo lắng",
    "anxiety": "lo lắng",
    "worried": "lo lắng",
    "nervous": "bồn chồn",
    
    "sad": "buồn",
    "sadness": "buồn bã",
    "depressed": "trầm buồn",
    "down": "chán nản",
    "unhappy": "không vui",
    "hopeless": "tuyệt vọng",
    
    "stressed": "căng thẳng",
    "overwhelmed": "quá tải",
    "pressure": "áp lực",
    
    "angry": "tức giận",
    "irritable": "cáu gắt",
    "frustrated": "bực bội",
    
    "tired": "mệt mỏi",
    "exhausted": "kiệt sức",
    "fatigue": "mệt mỏi",
    
    "scared": "sợ hãi",
    "fearful": "lo sợ",
    "panic": "hoảng loạn",
    
    "numb": "tê liệt",
    "empty": "trống rỗng",
    "disconnected": "mất kết nối",
}
```

#### 5.2. Thêm hàm build_empathy_from_slots()

**Location:** Trước hàm `request_more_info_node()`

```python
def build_empathy_from_slots(slots: Dict[str, Any]) -> str:
    """
    Build empathy preamble from existing slots when LLM doesn't provide one.
    RULE: Only use data that exists, don't fabricate.
    
    Args:
        slots: Existing slots dict
    
    Returns:
        Vietnamese empathy sentence (1-2 sentences)
    """
    if not slots:
        return "Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng."
    
    # Extract available data
    emotions = slots.get("emotion", [])
    presenting = slots.get("presenting_problem", [])
    trigger = slots.get("trigger", [])
    current_stressors = slots.get("current_stressors", [])
    work_impact = slots.get("work_school_impact", [])
    social_impact = slots.get("social_functioning", [])
    duration = slots.get("duration", [])
    intensity = slots.get("intensity", [])
    
    # Build empathy based on what's available
    parts = []
    
    # 1. Try emotion-based empathy
    if emotions:
        emotion_en = emotions[0] if isinstance(emotions, list) else emotions
        emotion_vi = EMOTION_MAP.get(emotion_en.lower(), "khó khăn")
        
        # Check for context
        if trigger or current_stressors:
            context = (trigger[0] if trigger else current_stressors[0]) if isinstance(trigger or current_stressors, list) else ""
            if context and len(context) < 50:  # Only if short
                return f"Mình nghe bạn đang cảm thấy {emotion_vi}, và có vẻ {context} đang ảnh hưởng đến bạn khá nhiều."
        
        # With impact
        if work_impact or social_impact:
            return f"Mình nghe bạn đang cảm thấy {emotion_vi}, và điều này đang ảnh hưởng đến nhiều khía cạnh trong cuộc sống của bạn."
        
        # With duration or intensity
        if duration and len(duration[0]) < 30:
            return f"Mình nghe bạn đã phải trải qua cảm giác {emotion_vi} trong {duration[0]}, điều đó hẳn rất nặng nề."
        
        if intensity:
            return f"Mình nghe bạn đang cảm thấy {emotion_vi}, và có vẻ điều này đang tác động khá mạnh đến bạn."
        
        # Simple emotion acknowledgment
        return f"Mình nghe bạn đang cảm thấy {emotion_vi}, điều đó hẳn là không dễ chịu."
    
    # 2. Try presenting_problem-based empathy
    if presenting:
        problem = presenting[0] if isinstance(presenting, list) else presenting
        if len(problem) < 50:  # Only if concise
            if work_impact or social_impact:
                return f"Có vẻ vấn đề về {problem} đang ảnh hưởng đến nhiều khía cạnh trong cuộc sống của bạn."
            return f"Mình nghe bạn đang gặp khó khăn với {problem}, điều đó hẳn đang khiến bạn khá lo lắng."
    
    # 3. Try impact-based empathy
    if work_impact or social_impact:
        return "Mình nghe những thay đổi gần đây đang ảnh hưởng đến công việc và các mối quan hệ của bạn, điều đó hẳn rất khó khăn."
    
    # 4. Fallback: generic but safe
    return "Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng."
```

#### 5.3. Cập nhật hàm request_more_info_node()

**Location:** Thay thế toàn bộ logic build answer

```python
async def request_more_info_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Handle insufficient REQUIRED slots by returning follow-up questions.
    Now includes empathy preamble before questions.
    
    ENFORCES:
    - Empathy preamble from LLM or fallback
    - Minimum 1 question if required slots missing
    - Maximum 3 questions per turn
    - Questions must be SPECIFIC (not generic)
    
    Args:
        state: State dict with follow_up_questions, required_missing_slots, empathy_preamble_vi
    
    Returns:
        Updated state with answer containing empathy + follow-up questions
    """
    follow_up_questions = state.get("follow_up_questions", [])
    required_missing = state.get("required_missing_slots", [])
    empathy_preamble = state.get("empathy_preamble_vi", "")
    slots = state.get("slots", {})
    
    logger.info(f"Insufficient REQUIRED slots filled. Requesting more information.")
    logger.info(f"Missing REQUIRED slots: {required_missing[:10]}...")
    
    # ========== EMPATHY PREAMBLE SELECTION (3-tier fallback) ==========
    # Tier 1: Use LLM-generated empathy (preferred)
    if empathy_preamble and empathy_preamble.strip():
        logger.info(f"✅ Using LLM-generated empathy: '{empathy_preamble[:80]}...'")
        final_empathy = empathy_preamble.strip()
    
    # Tier 2: Build from existing slots (fallback)
    elif slots:
        logger.info("⚠️ No LLM empathy, building from existing slots")
        final_empathy = build_empathy_from_slots(slots)
        logger.info(f"   Generated: '{final_empathy[:80]}...'")
    
    # Tier 3: Generic safe empathy (last resort)
    else:
        logger.warning("⚠️ No empathy from LLM and no slots, using generic fallback")
        final_empathy = "Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng."
    
    # Validate empathy is not a question
    if "?" in final_empathy:
        logger.warning(f"⚠️ Empathy contains '?', removing: '{final_empathy}'")
        final_empathy = final_empathy.replace("?", ".").strip()
    
    # ========== QUESTION ENFORCEMENT (existing logic) ==========
    if required_missing and not follow_up_questions:
        logger.warning(f"⚠️ CRITICAL: {len(required_missing)} required slots missing but NO follow-up questions!")
        logger.warning(f"   Auto-generating fallback questions...")
        follow_up_questions = generate_questions_from_slots(required_missing, max_questions=3)
        logger.info(f"   → Generated {len(follow_up_questions)} fallback questions")
    
    if len(follow_up_questions) > 3:
        logger.warning(f"⚠️ Too many questions ({len(follow_up_questions)}), trimming to 3")
        follow_up_questions = follow_up_questions[:3]
    
    # ========== BUILD FINAL ANSWER WITH EMPATHY ==========
    if follow_up_questions:
        if len(follow_up_questions) == 1:
            # Single question format
            answer = (
                f"{final_empathy}\n\n"
                f"Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:\n\n"
                f"{follow_up_questions[0]}"
            )
        else:
            # Multiple questions format (2-3)
            answer = (
                f"{final_empathy}\n\n"
                f"Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:"
            )
            for i, question in enumerate(follow_up_questions, 1):
                answer += f"\n{i}. {question}"
    else:
        # Final fallback (should rarely reach here)
        logger.error("❌ CRITICAL: No questions generated even after fallback!")
        answer = (
            f"{final_empathy}\n\n"
            f"Để mình hiểu rõ hơn, bạn có thể chia sẻ thêm về:\n"
            f"1. Tình trạng này bắt đầu từ khi nào?\n"
            f"2. Đã kéo dài bao lâu rồi?\n"
            f"3. Mức độ nghiêm trọng ra sao?"
        )
    
    logger.info(f"✅ Built answer with empathy + {len(follow_up_questions)} questions")
    logger.info(f"   Empathy: {final_empathy[:80]}...")
    for i, q in enumerate(follow_up_questions, 1):
        logger.info(f"   Q{i}: {q[:60]}...")
    
    # Update state
    state["answer"] = answer
    state["done"] = True
    state["needs_more_info"] = True
    
    return state
```

---

## 🧪 TESTING PLAN

### Test Case 1: LLM tạo empathy thành công
**Setup:**
```python
state = {
    "follow_up_questions": ["Tình trạng này bắt đầu từ khi nào?"],
    "required_missing_slots": ["onset"],
    "empathy_preamble_vi": "Mình nghe bạn đang cảm thấy lo lắng vì công việc, điều đó hẳn đang khiến bạn khá căng thẳng.",
    "slots": {"emotion": ["anxious"], "trigger": ["work stress"]}
}
```

**Expected Output:**
```
Mình nghe bạn đang cảm thấy lo lắng vì công việc, điều đó hẳn đang khiến bạn khá căng thẳng.

Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:

Tình trạng này bắt đầu từ khi nào?
```

### Test Case 2: LLM không tạo empathy, có slots
**Setup:**
```python
state = {
    "follow_up_questions": ["Tình trạng này bắt đầu từ khi nào?", "Đã kéo dài bao lâu?"],
    "required_missing_slots": ["onset", "duration"],
    "empathy_preamble_vi": "",  # Empty
    "slots": {"emotion": ["sad"], "work_school_impact": ["missing work"]}
}
```

**Expected Output:**
```
Mình nghe bạn đang cảm thấy buồn, và điều này đang ảnh hưởng đến nhiều khía cạnh trong cuộc sống của bạn.

Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:
1. Tình trạng này bắt đầu từ khi nào?
2. Đã kéo dài bao lâu?
```

### Test Case 3: Không có empathy, không có slots
**Setup:**
```python
state = {
    "follow_up_questions": ["Bạn đang cảm thấy cảm xúc gì?"],
    "required_missing_slots": ["emotion"],
    "empathy_preamble_vi": "",
    "slots": {}
}
```

**Expected Output:**
```
Mình nghe những gì bạn chia sẻ và hiểu rằng điều này có thể đang khiến bạn khá nặng lòng.

Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:

Bạn đang cảm thấy cảm xúc gì?
```

### Test Case 4: LLM tạo empathy có câu hỏi (invalid)
**Setup:**
```python
state = {
    "follow_up_questions": ["Tình trạng này bắt đầu từ khi nào?"],
    "required_missing_slots": ["onset"],
    "empathy_preamble_vi": "Bạn có đang lo lắng không?",  # Has question mark
    "slots": {"emotion": ["anxious"]}
}
```

**Expected:**
- Detect question mark in empathy
- Use Tier 2 fallback (build from slots)

**Expected Output:**
```
Mình nghe bạn đang cảm thấy lo lắng, điều đó hẳn là không dễ chịu.

Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:

Tình trạng này bắt đầu từ khi nào?
```

### Test Case 5: 3 questions max
**Setup:**
```python
state = {
    "follow_up_questions": [
        "Câu 1?", "Câu 2?", "Câu 3?"
    ],
    "required_missing_slots": ["onset", "duration", "intensity"],
    "empathy_preamble_vi": "Mình nghe bạn đang gặp khó khăn.",
    "slots": {}
}
```

**Expected Output:**
```
Mình nghe bạn đang gặp khó khăn.

Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:
1. Câu 1?
2. Câu 2?
3. Câu 3?
```

---

## 📝 IMPLEMENTATION CHECKLIST

### Phase 1: Preparation (5 min)
- [ ] Backup hiện tại: `git commit -m "backup before empathy implementation"`
- [ ] Đọc lại toàn bộ kịch bản
- [ ] Chuẩn bị test cases

### Phase 2: State & Schema (10 min)
- [ ] Add `empathy_preamble_vi: Optional[str]` to `state.py`
- [ ] Update `slot_filling_prompt.yaml`:
  - [ ] Add EMPATHY PREAMBLE section
  - [ ] Add examples (5 examples)
  - [ ] Update JSON schema output
- [ ] Commit: `git commit -m "feat: add empathy_preamble to state and prompt"`

### Phase 3: Slot Filling Processing (15 min)
- [ ] Update `slot_filling.py` (llm/answer_nodes):
  - [ ] Parse `empathy_preamble_vi` from LLM response
  - [ ] Validate (không có câu hỏi)
  - [ ] Add to return dict
  - [ ] Update all error handlers
- [ ] Update `slot_filling.py` (workflow/graph_nodes):
  - [ ] Propagate empathy to state
  - [ ] Add logging
- [ ] Test: Chạy slot_filling với mock input, check log có empathy
- [ ] Commit: `git commit -m "feat: parse and validate empathy_preamble in slot_filling"`

### Phase 4: Request More Info (20 min)
- [ ] Update `request_more_info.py`:
  - [ ] Add `EMOTION_MAP` dictionary
  - [ ] Add `build_empathy_from_slots()` function
  - [ ] Update `request_more_info_node()` logic
  - [ ] Test all 3 tiers of empathy selection
- [ ] Commit: `git commit -m "feat: implement empathy preamble in request_more_info"`

### Phase 5: Integration Testing (15 min)
- [ ] Test Case 1: LLM empathy success
- [ ] Test Case 2: Fallback from slots
- [ ] Test Case 3: Generic fallback
- [ ] Test Case 4: Invalid empathy (có ?)
- [ ] Test Case 5: Multiple questions format
- [ ] Check logs cho mỗi test case

### Phase 6: End-to-End Testing (10 min)
- [ ] Start backend: `docker compose restart backend`
- [ ] Test với real conversation:
  - [ ] User: "Tôi cảm thấy lo lắng"
  - [ ] Check response có empathy
  - [ ] Check format câu hỏi
- [ ] Test edge cases:
  - [ ] First turn (no slots)
  - [ ] After several turns (many slots)
  - [ ] LLM fails to generate empathy

### Phase 7: Finalization (5 min)
- [ ] Review all changes
- [ ] Update logs/comments if needed
- [ ] Final commit: `git commit -m "feat: complete empathy preamble implementation"`
- [ ] Create tag: `git tag v1.0-empathy-preamble`

---

## 🔄 ROLLBACK PLAN

Nếu có vấn đề nghiêm trọng:

```bash
# Rollback to previous commit
git revert HEAD

# Or reset to before implementation
git reset --hard <commit-hash-before-empathy>

# Restart backend
docker compose restart backend
```

**Files to revert:**
1. `backend/src/rag/workflow/state.py`
2. `backend/src/rag/prompts/slot_filling_prompt.yaml`
3. `backend/src/rag/llm/answer_nodes/slot_filling.py`
4. `backend/src/rag/workflow/graph_nodes/slot_filling.py`
5. `backend/src/rag/workflow/graph_nodes/request_more_info.py`

---

## 📊 EXPECTED IMPACT

### Trước (hiện tại):
```
Để tôi có thể hỗ trợ bạn tốt hơn, bạn có thể chia sẻ thêm về:
1. Tình trạng này bắt đầu từ khi nào?
2. Đã kéo dài bao lâu?
```

### Sau (với empathy):
```
Mình nghe bạn đang cảm thấy lo lắng vì công việc, điều đó hẳn đang khiến bạn khá căng thẳng.

Để mình hiểu rõ hơn và cùng bạn tìm hướng phù hợp, bạn cho mình biết thêm:
1. Tình trạng này bắt đầu từ khi nào?
2. Đã kéo dài bao lâu?
```

### Benefits:
✅ Tăng tính đồng cảm và kết nối với user  
✅ Validate trải nghiệm của user trước khi hỏi thêm  
✅ Tự nhiên hơn, giống conversation thật  
✅ LLM học được pattern tốt hơn từ examples  
✅ 3-tier fallback đảm bảo luôn có empathy (không bao giờ fail)  

### Risks:
⚠️ LLM có thể tạo empathy không phù hợp → Giải quyết bằng validation + fallback  
⚠️ Response dài hơn → OK, empathy chỉ 1-2 câu ngắn  
⚠️ Cần test kỹ với nhiều scenarios → Có 5 test cases cover  

---

## 🎓 LESSONS LEARNED

### Good Practices Applied:
1. **3-tier fallback system**: LLM → Slots → Generic
2. **Validation**: Check for questions in empathy
3. **Logging**: Track which tier is used
4. **Safe fallback**: Never fabricate details
5. **Clear examples in prompt**: 5 examples với variety

### Architecture Principles:
1. **Separation of concerns**: LLM tạo, Python validates
2. **Defensive programming**: Always have fallback
3. **User-first**: Empathy improves UX significantly
4. **Gradual degradation**: System works even if LLM fails

---

## 📚 REFERENCES

- Original request: User feedback về generic opening
- Related files:
  - `SLOT_SYSTEM_IMPROVEMENTS.md`
  - `FIX_REPETITIVE_SLOT_QUESTIONS.md`
- Therapeutic principles: Rogers' empathic understanding
- Conversational AI best practices: Acknowledgment before inquiry

---

## ✅ COMPLETION CRITERIA

Feature is complete when:
1. [ ] All 5 test cases pass
2. [ ] Logs show empathy selection working (3 tiers)
3. [ ] End-to-end conversation flows naturally
4. [ ] No questions in empathy_preamble
5. [ ] Fallback never fabricates details
6. [ ] All commits pushed with clear messages

---

**Total estimated time:** ~80 minutes  
**Priority:** High (UX improvement)  
**Risk level:** Low (has fallbacks)  
**Dependencies:** None (standalone feature)

---

## 🚀 READY TO IMPLEMENT?

Khi sẵn sàng triển khai:

1. Copy kịch bản này
2. Đi theo từng bước trong IMPLEMENTATION CHECKLIST
3. Test sau mỗi phase
4. Commit thường xuyên
5. Nếu có vấn đề → Check ROLLBACK PLAN

**Good luck! 💙**
