# Slot Filling Implementation Test Plan

## Implementation Checklist

### 1. Update State Structure
- [x] File: `backend/src/rag/workflow/state.py`
- [x] Add to `KGState`: slots, missing_slots, relevant_missing_slots, follow_up_questions

### 2. Create Slot Filling Prompt
- [x] File: `backend/src/rag/prompts/slot_filling_prompt.yaml`
- [x] Prompt đã tinh chỉnh với 5 gold examples

### 3. Create Helper Functions
- [x] File: `backend/src/rag/workflow/graph_nodes.py`
- [x] Function: `get_default_slots()`
- [x] Function: `build_slot_context()`

### 4. Implement Slot Filling Node
- [x] File: `backend/src/rag/workflow/graph_nodes.py`
- [x] Function: `slot_filling_node()`
- [x] Load prompt, call LLM, parse JSON, handle errors

### 5. Update Workflow
- [x] File: `backend/src/rag/workflow/workflow.py`
- [x] Import `slot_filling_node`
- [x] Add node và update routing

### 6. Update Answer Node
- [x] File: `backend/src/rag/llm/answer_nodes.py`
- [x] Use slots và follow-up questions

---

## Test Cases

### Test 1: Work Anxiety (Example 1)
**Input:**
```
"Dạo này mình cảm thấy rất lo lắng khi đi làm, cứ tới gần giờ vào công ty là trong người bồn chồn khó chịu."
```

**Expected Slots:**
- emotion: ["lo lắng", "bồn chồn"]
- trigger: "đi làm / đến công ty"
- duration: "dạo này"
- work_school_impact: "ảnh hưởng trước giờ đi làm"
- current_stressors: ["công việc"]

**Expected Relevant Missing:**
- intensity
- impact
- coping_mechanisms

**Expected Follow-ups:**
- Questions về intensity, impact, coping mechanisms
- Không hỏi về sleep (không liên quan)

**Check:**
- [ ] Slots extracted correctly
- [ ] Relevant missing slots identified
- [ ] Follow-up questions are relevant
- [ ] No irrelevant questions (sleep, social support)

---

### Test 2: Insomnia + Fatigue (Example 2)
**Input:**
```
"Tuần này mình mất ngủ nhiều lắm, ngủ không sâu và sáng dậy rất mệt."
```

**Expected Slots:**
- sleep_quality: "không sâu"
- sleep_duration: "ít / không đủ"
- duration: "tuần này"
- energy_level: "thấp"
- physical_symptoms: ["mệt mỏi"]

**Expected Relevant Missing:**
- trigger
- current_stressors
- daily_functioning

**Expected Follow-ups:**
- Questions về trigger, stressors, daily functioning
- Không hỏi về social support (không liên quan)

**Check:**
- [ ] Slots extracted correctly
- [ ] Relevant missing slots identified
- [ ] Follow-up questions are relevant
- [ ] No irrelevant questions (social support)

---

### Test 3: Social Isolation (Example 3)
**Input:**
```
"Dạo gần đây mình không muốn gặp ai cả, cứ muốn ở một mình thôi."
```

**Expected Slots:**
- social_isolation: true
- social_withdrawal: true
- duration: "dạo gần đây"

**Expected Relevant Missing:**
- trigger
- impact
- support_system

**Expected Follow-ups:**
- Questions về trigger, impact, support system
- Không hỏi về sleep (không liên quan)

**Check:**
- [ ] Slots extracted correctly
- [ ] Relevant missing slots identified
- [ ] Follow-up questions are relevant
- [ ] No irrelevant questions (sleep)

---

### Test 4: Passive Suicidal Ideation (Example 4)
**Input:**
```
"Mình mệt mỏi quá, nhiều lúc chỉ muốn biến mất cho rồi."
```

**Expected Slots:**
- emotion: ["mệt mỏi"]
- risk_level: "medium"
- suicidal_ideation: true

**Expected Relevant Missing:**
- current_stressors
- support_system
- impact

**Expected Follow-ups:**
- Questions về stressors, support system, impact
- Empathetic tone

**Check:**
- [ ] Slots extracted correctly
- [ ] Risk level detected correctly
- [ ] Suicidal ideation detected
- [ ] Follow-up questions are empathetic

---

### Test 5: Just Want to Talk (Example 5)
**Input:**
```
"Mình chỉ muốn nói chuyện và chia sẻ cho nhẹ lòng."
```

**Expected Slots:**
- need: "listening"

**Expected Relevant Missing:**
- emotion

**Expected Follow-ups:**
- 1 question về emotion
- Không hỏi nhiều (user chỉ muốn tâm sự)

**Check:**
- [ ] Slots extracted correctly
- [ ] Need identified as "listening"
- [ ] Minimal follow-ups (1 question)
- [ ] Natural, empathetic tone

---

### Test 6: English Input
**Input:**
```
"I've been feeling really anxious about work lately, can't sleep well."
```

**Check:**
- [ ] Slots extracted correctly
- [ ] Follow-up questions in English
- [ ] Relevant missing slots identified

---

### Test 7: Very Short Input
**Input:**
```
"Mệt mỏi"
```

**Check:**
- [ ] Basic slots extracted (emotion: ["mệt mỏi"])
- [ ] Relevant missing slots identified (sleep, energy, duration)
- [ ] Follow-up questions are relevant
- [ ] Not asking too many questions (max 2-3)

---

### Test 8: Edge Case - Empty Input
**Input:**
```
""
```

**Check:**
- [ ] Default slots returned
- [ ] No errors
- [ ] Graceful handling

---

### Test 9: Edge Case - Invalid JSON Response
**Simulate:** LLM returns invalid JSON

**Check:**
- [ ] Fallback to default slots
- [ ] No crash
- [ ] Error logged

---

### Test 10: Full Workflow Integration
**Input:** Any test case above

**Check:**
- [ ] translate_question → safety_check → slot_filling → graph_retrieval → answer → translate_answer
- [ ] Slots flow through all nodes
- [ ] Follow-up questions appear in final answer
- [ ] Answer is personalized based on slots

---

## Manual Testing Checklist

### Basic Functionality
- [ ] Slot filling node runs without errors
- [ ] Slots extracted correctly
- [ ] Missing slots identified
- [ ] Relevant missing slots filtered correctly
- [ ] Follow-up questions generated

### Integration
- [ ] Workflow compiles without errors
- [ ] All nodes execute in correct order
- [ ] State flows correctly through nodes
- [ ] Answer includes slot context
- [ ] Answer includes follow-up questions

### Quality
- [ ] Follow-up questions are natural
- [ ] Follow-up questions are relevant
- [ ] No irrelevant questions asked
- [ ] Questions are empathetic
- [ ] Questions are in correct language (VI/EN)

### Error Handling
- [ ] Handles LLM errors gracefully
- [ ] Handles JSON parsing errors
- [ ] Handles missing prompt file
- [ ] Handles empty input
- [ ] Logs errors appropriately

---

## Success Criteria

- [ ] All test cases pass
- [ ] Slot extraction works correctly
- [ ] Relevant missing slots identified correctly
- [ ] Follow-up questions are natural and relevant
- [ ] No irrelevant questions asked
- [ ] Full workflow works end-to-end
- [ ] Error handling works correctly
- [ ] Performance acceptable (latency not too high)

---

## Notes

- Test với real LLM calls (không mock)
- Monitor latency (thêm 1 LLM call)
- Check logs for errors
- Verify JSON parsing works correctly
- Test với various input lengths

