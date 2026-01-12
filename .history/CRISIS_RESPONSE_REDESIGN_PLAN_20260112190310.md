# KỊCH BẢN THIẾT KẾ LẠI CRISIS RESPONSE SYSTEM

## 📋 VẤN ĐỀ HIỆN TẠI

### Hiện trạng:
```
User: "Tôi muốn tự tử"
Bot: [Crisis response với hotlines]

User: "Tôi đang rất đau khổ"
Bot: [Lặp lại crisis response với hotlines]

User: "Tôi cần ai đó nói chuyện"
Bot: [Lặp lại crisis response với hotlines]
```

### Root Causes:
1. ❌ **Dead-end workflow**: `crisis_response → END` (không có path tiếp theo)
2. ❌ **No state tracking**: Không biết đã show crisis response bao nhiêu lần
3. ❌ **Context-blind**: Không xem xét user reaction sau crisis message
4. ❌ **One-size-fits-all**: Tất cả high-risk cases đều nhận cùng 1 response
5. ❌ **No de-escalation**: Không có mechanism để giảm risk level nếu user calm down
6. ❌ **Lost opportunity**: Không leverage knowledge graph cho crisis support

---

## 🎯 GIẢI PHÁP ĐỀ XUẤT: ADAPTIVE CRISIS RESPONSE SYSTEM

### Core Principles:
1. **Safety First**: Hotlines luôn được hiển thị ở crisis situations
2. **Progressive Support**: Multi-stage response dựa trên user engagement
3. **Context-Aware**: Track crisis state và user reactions
4. **Hybrid Approach**: Kết hợp immediate safety + contextual support từ KG
5. **De-escalation Path**: Cho phép transition về normal flow nếu risk giảm

---

## 🏗️ KIẾN TRÚC MỚI

### 1. Crisis State Management

**Thêm vào `state.py`:**

```python
class KGState(TypedDict):
    # ... existing fields ...
    
    # Crisis Management (NEW)
    crisis_level: Optional[str]  # "critical" | "high" | "moderate" | None
    crisis_stage: Optional[int]  # 1: immediate, 2: follow-up, 3: supportive
    crisis_indicators: Optional[List[str]]  # List of detected risk indicators
    crisis_response_count: Optional[int]  # Số lần đã show crisis response
    user_acknowledged_crisis: Optional[bool]  # User đã thấy/respond crisis message
    crisis_de_escalation_attempted: Optional[bool]  # Đã cố gắng de-escalate
    crisis_context_retrieved: Optional[bool]  # Đã retrieve contextual support
```

**Rationale:**
- `crisis_level`: Phân biệt mức độ nghiêm trọng (từ safety_check indicators)
- `crisis_stage`: Track progression qua các giai đoạn response
- `crisis_response_count`: Prevent repetition (max 2-3 lần)
- `user_acknowledged_crisis`: Check if user engaged với crisis message
- `crisis_context_retrieved`: Flag để retrieve support content 1 lần

---

### 2. Multi-Stage Crisis Response Flow

#### Stage 1: IMMEDIATE SAFETY (First Response)
**Trigger:** Lần đầu detect high-risk
**Goal:** Safety intervention + hotlines

```
crisis_response_stage_1:
  ⚠️ [Empathetic opening based on indicators]
  
  🆘 HOTLINE KHẨN CẤP (24/7):
  • 115 - Cấp cứu y tế
  • 111 - Tổng đài bảo vệ trẻ em
  • 1800 599 913 - Tư vấn tâm lý
  
  💚 [Immediate safety steps]
  
  ❓ Bạn có thể cho tôi biết bạn đang ở đâu và có ai ở cùng không?
```

**Output:**
- Set `crisis_stage = 1`
- Set `crisis_response_count = 1`
- Set `done = False` (KHÔNG kết thúc conversation!)
- Route to `crisis_follow_up_classifier` node

---

#### Stage 2: ENGAGEMENT CHECK (After Stage 1)
**Node:** `crisis_follow_up_classifier`
**Goal:** Classify user response sau crisis message

```python
async def crisis_follow_up_classifier(state):
    """
    Classify user response sau crisis message:
    - "immediate_danger": User confirm đang trong nguy hiểm → Escalate
    - "seeking_help": User muốn nói chuyện/cần hỗ trợ → Supportive path
    - "declining_help": User từ chối/defensive → Gentle persistence
    - "de_escalated": User calm hơn/risk giảm → Gradual transition
    """
    
    question = state["question"]
    history = format_recent_history(state["conversation_buffer"])
    crisis_indicators = state.get("crisis_indicators", [])
    
    # LLM classify with crisis context
    classification = await llm_classify_crisis_response(
        question=question,
        history=history,
        previous_indicators=crisis_indicators
    )
    
    return classification  # "immediate_danger" | "seeking_help" | "declining_help" | "de_escalated"
```

**Routing Logic:**

```python
def route_after_crisis_follow_up(state):
    classification = state["crisis_follow_up_classification"]
    
    if classification == "immediate_danger":
        # User trong nguy hiểm cấp thiết → Escalate + repeat hotlines
        return "crisis_escalation"
    
    elif classification == "seeking_help":
        # User muốn support → Retrieve contextual help
        return "crisis_contextual_support"
    
    elif classification == "declining_help":
        # User defensive → Gentle persistence (1 more try)
        if state["crisis_response_count"] < 2:
            return "crisis_gentle_persistence"
        else:
            return "crisis_contextual_support"  # Proceed anyway
    
    elif classification == "de_escalated":
        # Risk giảm → Transition về normal flow với monitoring
        return "crisis_to_normal_transition"
```

---

#### Stage 3a: ESCALATION PATH (Immediate Danger)
**Node:** `crisis_escalation_node`
**Trigger:** User confirm trong nguy hiểm

```python
async def crisis_escalation_node(state):
    """
    Stronger intervention khi user confirm immediate danger
    """
    
    message = f"""
    {state["empathy_preamble_vi"]}
    
    🚨 **TÌNH HUỐNG KHẨN CẤP**
    
    Bạn đang trong tình huống nguy hiểm và cần được hỗ trợ NGAY LẬP TỨC từ chuyên gia.
    
    📞 **HÃY GỌI NGAY:**
    • **115** - Cấp cứu y tế (miễn phí, 24/7)
    • **113** - Cảnh sát (nếu cần bảo vệ)
    
    Nếu bạn không thể gọi, hãy:
    1. Nhắn tin cho người thân: "Tôi cần giúp đỡ khẩn cấp"
    2. Đi đến bệnh viện gần nhất
    3. Gọi xe cứu thương
    
    Tôi là chatbot và không thể thay thế sự hỗ trợ khẩn cấp từ con người.
    
    ⚠️ Bạn có đang an toàn ngay lúc này không?
    """
    
    state["answer"] = message
    state["crisis_stage"] = 2
    state["crisis_response_count"] += 1
    state["done"] = False
    
    return state
```

**Note:** Nếu user tiếp tục trong danger sau 2-3 turns → Có thể kết thúc conversation với final message khuyến khích gọi hotline.

---

#### Stage 3b: CONTEXTUAL SUPPORT PATH (Seeking Help)
**Node:** `crisis_contextual_support_node`
**Trigger:** User muốn nói chuyện/cần hỗ trợ

**Workflow:**
```
crisis_contextual_support_node
  ↓
  1. Retrieve coping strategies cho crisis (từ KG)
  2. Retrieve grounding techniques
  3. Retrieve immediate safety planning info
  4. Generate supportive response kết hợp:
     - Validation + empathy
     - Actionable coping strategies
     - Gentle reminder về hotlines (không aggressive)
```

**Implementation:**

```python
async def crisis_contextual_support_node(state):
    """
    Provide contextual support từ knowledge graph
    Kết hợp safety message + practical coping strategies
    """
    
    # Extract crisis indicators để target retrieval
    indicators = state.get("crisis_indicators", [])
    question = state["question"]
    
    # Build crisis-specific query
    crisis_queries = []
    if "suicide" in indicators or "self-harm" in indicators:
        crisis_queries = [
            "coping strategies for suicidal thoughts",
            "grounding techniques for crisis",
            "safety planning for self-harm urges",
            "reasons to stay alive",
            "distraction techniques immediate"
        ]
    elif "harm_others" in indicators:
        crisis_queries = [
            "managing anger and aggression",
            "impulse control techniques",
            "crisis de-escalation strategies"
        ]
    
    # Parallel retrieval (graph + dense)
    results = await parallel_crisis_retrieval(
        queries=crisis_queries,
        graph_retrieval=True,
        dense_retrieval=True
    )
    
    # Generate hybrid response
    prompt = f"""
    USER IN CRISIS - provide supportive response combining:
    
    CRISIS INDICATORS: {', '.join(indicators)}
    USER QUESTION: {question}
    CONVERSATION HISTORY: {format_history(state["conversation_buffer"])}
    
    COPING STRATEGIES FROM KNOWLEDGE BASE:
    {results["coping_strategies"]}
    
    GROUNDING TECHNIQUES:
    {results["grounding_techniques"]}
    
    INSTRUCTIONS:
    1. Start with validation + empathy (2-3 câu)
    2. Provide 2-3 ACTIONABLE coping strategies (cụ thể, dễ làm ngay)
    3. Include 1 grounding technique (breathing, 5 senses, etc.)
    4. End with gentle reminder: "Nếu cảm giác này quá nặng, đừng ngại gọi 115 hoặc 1800 599 913"
    5. Ask open-ended question để encourage tiếp tục nói chuyện
    
    DO NOT:
    - Repeat full crisis hotline list (đã show ở stage 1)
    - Be overly clinical or detached
    - Give false hope or minimize feelings
    - Suggest long-term solutions (focus on RIGHT NOW)
    
    TONE: Warm, present, practical, non-judgmental
    """
    
    response = await llm.generate(prompt)
    
    state["answer"] = response
    state["crisis_stage"] = 3
    state["crisis_context_retrieved"] = True
    state["done"] = False  # Allow continuation
    
    return state
```

**Example Output:**
```
Tôi nghe thấy bạn đang trải qua đau khổ rất lớn, và tôi hiểu rằng có những lúc 
cảm giác này khiến mọi thứ như không còn lối thoát. Cảm ơn bạn đã chia sẻ với tôi.

💡 **NGAY BÂY GIỜ, bạn có thể thử:**

1. **Kỹ thuật 5-4-3-2-1** (Grounding):
   - Nhìn 5 thứ xung quanh bạn
   - Chạm vào 4 bề mặt khác nhau
   - Nghe 3 âm thanh
   - Ngửi 2 mùi
   - Nếm 1 vị
   
   → Giúp bạn quay về hiện tại, giảm overwhelming feelings

2. **Breathing 4-7-8**:
   - Hít vào 4 giây
   - Giữ 7 giây
   - Thở ra 8 giây
   - Lặp 4 lần
   
   → Làm chậm nhịp tim, giảm panic

3. **Temperature shock**:
   - Rửa mặt bằng nước lạnh
   - Hoặc giữ ice cube trong tay
   
   → Cơ thể tập trung vào cảm giác này thay vì emotions

🤝 Nếu các kỹ thuật này không giúp được, hoặc cảm giác quá nặng, 
đừng ngại gọi **115** hoặc **1800 599 913** để được hỗ trợ từ chuyên gia.

Bạn có muốn thử một trong những kỹ thuật này không? Hoặc bạn muốn nói 
thêm về những gì đang khiến bạn cảm thấy như vậy?
```

---

#### Stage 3c: GENTLE PERSISTENCE (Declining Help)
**Node:** `crisis_gentle_persistence_node`
**Trigger:** User defensive/từ chối help

```python
async def crisis_gentle_persistence_node(state):
    """
    Gentle persistence khi user resistant
    """
    
    message = f"""
    {state["empathy_preamble_vi"]}
    
    Tôi hiểu bạn có thể chưa sẵn sàng nói về điều này, và đó là quyền của bạn. 
    
    Tôi chỉ muốn bạn biết:
    • Những cảm xúc bạn đang có là có thật và quan trọng
    • Bạn không cần phải đối mặt với chúng một mình
    • Có những người được đào tạo để giúp đỡ, không phán xét: **1800 599 913**
    
    Nếu bạn thay đổi ý định, tôi vẫn ở đây để lắng nghe.
    
    Bạn có muốn nói về điều gì khác không? Hoặc tôi có thể giúp bạn tìm 
    thông tin về cách đối phó với cảm xúc khó khăn?
    """
    
    state["answer"] = message
    state["crisis_stage"] = 2
    state["crisis_response_count"] += 1
    state["crisis_de_escalation_attempted"] = True
    state["done"] = False
    
    return state
```

---

#### Stage 3d: TRANSITION TO NORMAL (De-escalated)
**Node:** `crisis_to_normal_transition_node`
**Trigger:** Risk level giảm, user calm hơn

```python
async def crisis_to_normal_transition_node(state):
    """
    Transition từ crisis mode về normal flow với monitoring
    """
    
    # Check if user truly de-escalated (not just deflecting)
    is_genuine_deescalation = await verify_deescalation(
        question=state["question"],
        history=state["conversation_buffer"],
        previous_indicators=state["crisis_indicators"]
    )
    
    if not is_genuine_deescalation:
        # User deflecting → Stay in crisis support
        return await crisis_contextual_support_node(state)
    
    # Genuine de-escalation → Proceed with monitored normal flow
    message = f"""
    {state["empathy_preamble_vi"]}
    
    Tôi rất vui vì bạn đang cảm thấy ổn định hơn. 
    
    Để đảm bảo an toàn, tôi muốn nhắc bạn:
    • Nếu bất cứ lúc nào cảm giác trở lại, hãy gọi **115** hoặc **1800 599 913**
    • Số này luôn sẵn sàng 24/7, không cần ngại ngùng
    
    Bây giờ, bạn muốn nói về điều gì? Tôi có thể giúp bạn với:
    • Cách đối phó với căng thẳng
    • Kỹ thuật thư giãn
    • Thông tin về các rối loạn tâm lý
    • Hoặc bất cứ điều gì bạn cần
    """
    
    state["answer"] = message
    state["crisis_level"] = "moderate"  # Downgrade from "high"
    state["crisis_stage"] = None
    state["done"] = False
    
    # Next turn sẽ qua normal flow nhưng với heightened monitoring
    state["requires_safety_monitoring"] = True
    
    return state
```

---

### 3. Crisis-Aware Retrieval

**New Node:** `crisis_retrieval_node`

```python
async def crisis_retrieval_node(state):
    """
    Specialized retrieval cho crisis situations
    Focus: immediate coping, safety planning, grounding techniques
    """
    
    crisis_indicators = state.get("crisis_indicators", [])
    question = state["question"]
    
    # Build crisis-specific queries
    queries = build_crisis_queries(crisis_indicators)
    
    # Multi-source retrieval
    results = {
        "graph": await graph_crisis_retrieval(queries),
        "dense": await dense_crisis_retrieval(queries),
        "emergency_protocols": get_emergency_protocols(crisis_indicators)
    }
    
    # Merge and rank by urgency
    ranked_content = rank_by_crisis_relevance(results)
    
    state["crisis_chunks"] = ranked_content
    return state
```

**Crisis-Specific Collections trong Knowledge Graph:**
- `crisis_coping_strategies` - Immediate coping techniques
- `grounding_techniques` - 5-4-3-2-1, breathing, etc.
- `safety_planning` - Safety plans for different crisis types
- `reasons_to_live` - Hope-oriented content (use carefully)
- `distraction_techniques` - Immediate distractions

---

### 4. Workflow Graph Updates

**Hiện tại:**
```
safety_check → (high_risk?) → crisis_response → END
```

**Mới:**
```
safety_check → (high_risk?) → crisis_immediate_response (stage 1)
                                    ↓
                              crisis_follow_up_classifier
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
            immediate_danger  seeking_help   declining_help
                    ↓               ↓               ↓
            crisis_escalation  crisis_contextual   gentle_persistence
                    ↓          _support             ↓
                    ↓               ↓               ↓
                    └───────────────┼───────────────┘
                                    ↓
                              (next user input)
                                    ↓
                              safety_check (re-assess)
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓                               ↓
            still high_risk?                   de_escalated?
                    ↓                               ↓
            Continue crisis flow           Transition to normal
                                          (với monitoring)
```

**Code Changes trong `workflow.py`:**

```python
# Add new nodes
builder.add_node("crisis_immediate_response", crisis_immediate_response_node)
builder.add_node("crisis_follow_up_classifier", crisis_follow_up_classifier_node)
builder.add_node("crisis_escalation", crisis_escalation_node)
builder.add_node("crisis_contextual_support", crisis_contextual_support_node)
builder.add_node("crisis_gentle_persistence", crisis_gentle_persistence_node)
builder.add_node("crisis_to_normal_transition", crisis_to_normal_transition_node)

# Update routing
builder.add_conditional_edges(
    "safety_check",
    route_after_safety_check,
    {
        "crisis_immediate_response": "crisis_immediate_response",  # Changed from "crisis_response"
        "slot_filling": "slot_filling"
    }
)

# Add crisis flow routing
builder.add_edge("crisis_immediate_response", "crisis_follow_up_classifier")

builder.add_conditional_edges(
    "crisis_follow_up_classifier",
    route_after_crisis_follow_up,
    {
        "crisis_escalation": "crisis_escalation",
        "crisis_contextual_support": "crisis_contextual_support",
        "crisis_gentle_persistence": "crisis_gentle_persistence",
        "crisis_to_normal_transition": "crisis_to_normal_transition"
    }
)

# Crisis nodes DON'T go to END - they set done=False
# Next user input will re-enter workflow at "safety_check"
```

---

### 5. Safety Monitoring trong Normal Flow

**Concept:** Sau khi transition từ crisis về normal, tiếp tục monitor

```python
def route_after_safety_check(state):
    """
    Enhanced với crisis monitoring
    """
    is_high_risk = state.get("is_high_risk", False)
    requires_monitoring = state.get("requires_safety_monitoring", False)
    
    if is_high_risk:
        # Check if already in crisis flow
        if state.get("crisis_stage"):
            # Re-escalation - đã ở crisis mode rồi nhưng vẫn high-risk
            return "crisis_escalation"
        else:
            # First time detect
            return "crisis_immediate_response"
    
    elif requires_monitoring:
        # User từng ở crisis, giờ stable nhưng cần watch closely
        # Log for monitoring
        logger.warning(f"[MONITORING] User {state.get('user_id')} in post-crisis monitoring")
        
        # Proceed normal flow nhưng với heightened sensitivity
        state["crisis_sensitivity_increased"] = True
    
    return "slot_filling"
```

---

## 📊 IMPACT ANALYSIS

### Before:
```
Turn 1: User "Tôi muốn tự tử" → Crisis hotlines → END
Turn 2: User "Tôi cần ai đó" → Crisis hotlines → END (repetitive)
Turn 3: User "Tôi buồn" → Crisis hotlines → END (stuck)
```

### After:
```
Turn 1: User "Tôi muốn tự tử" 
        → Crisis hotlines + safety check question
        → done=False

Turn 2: User "Tôi đang ở nhà một mình"
        → Contextual support: grounding techniques + coping strategies
        → "Bạn muốn thử kỹ thuật breathing không?"
        → done=False

Turn 3: User "Tôi thử rồi, hơi ổn hơn"
        → Transition to normal + monitoring
        → "Bạn muốn nói thêm về điều gì đang làm bạn buồn không?"
        → Normal diagnostic flow (slot filling, retrieval, etc.)

Turn 4: User "Tôi bị stress từ công việc"
        → Normal flow với monitoring
        → Retrieve stress coping strategies từ KG
        → Contextual answer
```

---

## 🎯 BENEFITS

1. **✅ Không lặp lại**: Multi-stage prevents repetition
2. **✅ Context-aware**: Adapt response based on user engagement
3. **✅ Balanced approach**: Safety + support, không quá aggressive
4. **✅ Leverage KG**: Sử dụng knowledge graph cho crisis content
5. **✅ De-escalation path**: Có thể quay về normal flow
6. **✅ Continuous conversation**: Không dead-end, encourage tiếp tục
7. **✅ Monitoring**: Track post-crisis users
8. **✅ Flexible**: Handle different crisis types (SI, NSSI, harm others)

---

## ⚠️ SAFETY CONSIDERATIONS

### Critical Requirements:
1. **Hotlines luôn xuất hiện** ở stage 1 (immediate response)
2. **Never minimize**: Không bao giờ downplay crisis
3. **Professional boundary**: Clear là chatbot, không thay thế chuyên gia
4. **Escalation protocol**: Khi user confirm immediate danger, ưu tiên hotlines
5. **Logging**: Log tất cả crisis interactions cho review
6. **Timeout**: Nếu user không respond sau crisis message, consider ending session gracefully

### Red Flags to Watch:
- User có plan cụ thể + means + intent → ESCALATE immediately
- Mention về harming others → ESCALATE + consider notifying authorities protocol
- Under 18 và mention abuse → ESCALATE + child protection resources

---

## 📝 IMPLEMENTATION PHASES

### Phase 1: State & Tracking (1-2 days)
- [ ] Update `state.py` với crisis fields
- [ ] Implement crisis state initialization
- [ ] Add crisis logging utilities

### Phase 2: Multi-Stage Nodes (2-3 days)
- [ ] Implement `crisis_immediate_response_node`
- [ ] Implement `crisis_follow_up_classifier_node`
- [ ] Implement `crisis_escalation_node`
- [ ] Implement `crisis_contextual_support_node`
- [ ] Implement `crisis_gentle_persistence_node`
- [ ] Implement `crisis_to_normal_transition_node`

### Phase 3: Crisis Retrieval (2 days)
- [ ] Create crisis-specific queries
- [ ] Implement `crisis_retrieval_node`
- [ ] Test retrieval quality with crisis scenarios

### Phase 4: Workflow Integration (1 day)
- [ ] Update workflow graph
- [ ] Update routing logic
- [ ] Update edge connections

### Phase 5: Testing (2-3 days)
- [ ] Test crisis escalation path
- [ ] Test contextual support path
- [ ] Test de-escalation path
- [ ] Test repetition prevention
- [ ] Test monitoring after crisis
- [ ] Edge cases (deflecting, aggression, etc.)

### Phase 6: Monitoring & Tuning (Ongoing)
- [ ] Log analysis
- [ ] False positive/negative rates
- [ ] User engagement metrics
- [ ] Response quality review

**Total: ~2 weeks**

---

## 🧪 TEST SCENARIOS

### Scenario 1: Escalation Path
```
T1: User: "Tôi muốn tự tử" 
    → immediate_response (hotlines)
    
T2: User: "Tôi đã chuẩn bị thuốc ngủ rồi"
    → classifier: immediate_danger
    → escalation (stronger intervention)
    
T3: User: "Tôi không thể gọi ai được"
    → escalation (alternative emergency options)
```

### Scenario 2: Support Path
```
T1: User: "Tôi không muốn sống nữa"
    → immediate_response (hotlines)
    
T2: User: "Tôi chỉ cần ai đó hiểu tôi"
    → classifier: seeking_help
    → contextual_support (grounding + coping)
    
T3: User: "Tôi thử breathing, nó hơi giúp được"
    → classifier: de_escalated
    → transition_to_normal + monitoring
    
T4: User: "Tôi bị stress từ công việc"
    → normal_flow (slot filling, retrieval)
```

### Scenario 3: Resistant User
```
T1: User: "Tôi muốn chết"
    → immediate_response
    
T2: User: "Không cần bạn can thiệp"
    → classifier: declining_help
    → gentle_persistence
    
T3: User: "Thôi được rồi, tôi ổn"
    → verify genuine de-escalation
    → If genuine: transition
    → If not: contextual_support
```

---

## 💡 ADDITIONAL ENHANCEMENTS

### Optional Features:
1. **Crisis history tracking**: Store crisis episodes per user
2. **Escalation to human**: Button để connect với human counselor (nếu có)
3. **Follow-up check**: Auto check-in sau 24h nếu crisis episode
4. **Resource recommendations**: Nearby crisis centers, therapists
5. **Safety plan builder**: Interactive tool để build personal safety plan

---

## 📚 REFERENCES

- Crisis Intervention Best Practices (APA)
- Suicide Prevention Guidelines (WHO)
- Chatbot Safety Standards (IEEE)
- Mental Health First Aid Protocols

---

**END OF REDESIGN PLAN**
