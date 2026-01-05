# Kế Hoạch Cải Thiện Hệ Thống Chẩn Đoán Rối Loạn Tâm Thần

## Ngày tạo: 2026-01-06 | Cập nhật: 2026-01-06 v2

---

## 🔴 VẤN ĐỀ CỐT LÕI

### **Root Cause: Premature Binary Classification**

**Vấn đề kiến trúc:**
```
Current Flow (WRONG):
slot_filling → assessment → BINARY DECISION
                               ├─ "normal" → normal_coping (STOP - no diagnosis!)
                               └─ "disorder" → diagnostic → differential diagnosis
```

**Hệ quả:**
- ❌ OCD bị miss vì có stress trigger → classify "normal stress"
- ❌ GAD bị miss vì có life event → classify "adjustment reaction"
- ❌ Depression bị miss vì symptoms overlap với grief/fatigue
- ❌ Panic Disorder bị miss vì physical symptoms → classify "anxiety"
- ❌ **CRITICAL FLAW**: Assessment node acts as gatekeeper, blocks diagnostic investigation

### **Case Studies**

**Case 1: OCD missed**
- Triệu chứng: Kiểm tra lặp lại, ý nghĩ xâm nhập, cưỡng chế
- LLM kết luận: "Stress công việc bình thường"
- Lý do sai: Có trigger (chuyển việc) → route về normal_stress → BỎ QUA diagnostic

**Case 2: GAD missed**
- Triệu chứng: Lo âu lan tỏa nhiều lĩnh vực, 4 tháng, khó kiểm soát
- LLM kết luận: "Pressure từ học tập"
- Lý do sai: Duration chưa đủ dài → score thấp → route về adjustment

**Case 3: Depression missed**
- Triệu chứng: Mất hứng thú, mệt mỏi, khó ngủ, tự ti
- LLM kết luận: "Buồn bã do chia tay bình thường"
- Lý do sai: Có life event → classify adjustment reaction → không check criteria MDD

**Case 4: Normal stress FALSE POSITIVE diagnosed as disorder**
- Triệu chứng: Stress công việc 2 tuần, lo lắng nhẹ
- LLM kết luận: "GAD có khả năng cao"
- Lý do sai: Overlap keywords → route vào diagnostic → không có mechanism check "normal response"

---

## 📊 PHÂN TÍCH KIẾN TRÚC HIỆN TẠI

### **1. Critical Architecture Flaw**

**File:** `backend/src/rag/workflow/workflow.py` (lines 134-160)

```python
def route_after_assessment(state: KGState) -> str:
    category = state.get("assessment_category")
    
    if category == "normal_stress":
        return "normal_coping_retrieval"  # ❌ STOPS diagnostic investigation
    
    if category == "adjustment_reaction":
        return "adjustment_retrieval"  # ❌ STOPS diagnostic investigation
    
    # Only possible_disorder/likely_disorder go to diagnostic
    return "query_rewriter"  # → diagnostic_retrieval
```

**Vấn đề:**
- ❌ **Premature binary decision**: normal vs disorder before differential diagnosis
- ❌ **No verification mechanism**: Assessment score alone determines route
- ❌ **Assumes mutual exclusivity**: Can't be "stressed" AND have disorder

### **2. Assessment Module Problems**

**File:** `backend/src/rag/utils/assessment.py` (lines 268-400)

```python
def assess_disorder_likelihood(...):
    # Decision rules:
    if max_item_score <= 3 AND D <= 1 AND total_score <= 4:
        return "normal_stress"  # ❌ Blocks diagnostic for low scores
    
    if matched_items overlap with life_events:
        return "adjustment_reaction"  # ❌ Blocks diagnostic if stressor present
    
    # Only high scores reach diagnostic
    if max_item_score >= 5 OR D >= 3 OR total_score >= 8:
        return "likely_disorder"
```

**Vấn đề:**
1. **Score thresholds arbitrary**: OCD/GAD/Depression có patterns khác nhau
2. **Life event bias**: Có stressor → assume adjustment, không check co-morbidity
3. **No disorder-specific criteria**: Chỉ dựa vào generic scores

### **3. Missing Differential Diagnosis Framework**

**Không có module:**
- ❌ Disorder-specific criteria checking (DSM-5/ICD-11)
- ❌ Differential diagnosis logic (OCD vs GAD vs OCPD)
- ❌ Exclusion criteria checking (medical conditions, substances)
- ❌ Severity spectrum (subclinical → clinical threshold)

**Thiếu slots cho differential diagnosis:**
```yaml
# OCD-specific
- compulsion_time_per_day, has_rituals, obsession_type, insight_level

# GAD-specific  
- worry_topics_count, uncontrollability, restlessness, concentration_difficulty

# Depression-specific
- anhedonia_severity, worthlessness, suicidal_ideation, psychomotor_changes

# Panic Disorder-specific
- panic_attack_frequency, fear_of_attacks, physical_symptoms_peak_time

# Common exclusion criteria
- medical_conditions_ruled_out, substance_use_timeline, medication_effects
```

---

## 🎯 GIẢI PHÁP ĐỀ XUẤT: UNIVERSAL DIAGNOSTIC FLOW

### **Core Principle: "Innocent Until Proven Guilty" → "Investigate Then Rule Out"**

**Thay đổi tư duy:**
```
OLD: "Prove it's a disorder to enter diagnostic flow"
NEW: "Investigate all cases, then prove it's NOT a disorder"
```

**New Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                     SLOT FILLING PHASE                          │
│  Collect: symptoms, duration, impact, triggers, history         │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                  SEVERITY ASSESSMENT                            │
│  Purpose: Triage urgency, NOT binary diagnosis                  │
│  Output: mild/moderate/severe/crisis                            │
│  Action: Set priority, NOT block diagnostic                     │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
        ╔═══════════════════════════════════╗
        ║   UNIVERSAL DIAGNOSTIC FLOW       ║
        ║   (ALL CASES GO THROUGH THIS)     ║
        ╚═══════════════╤═══════════════════╝
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│               DISORDER SCREENING (Parallel)                     │
│  ┌─────────┬─────────┬──────────┬──────────┬─────────────┐     │
│  │   OCD   │   GAD   │   MDD    │  Panic   │  PTSD etc.  │     │
│  │ Screen  │ Screen  │  Screen  │  Screen  │   Screen    │     │
│  └────┬────┴────┬────┴─────┬────┴─────┬────┴──────┬──────┘     │
│       │         │          │          │           │            │
│       ↓         ↓          ↓          ↓           ↓            │
│   Score 0-10  Score 0-10  Score 0-10  Score 0-10  Score 0-10  │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│            DIFFERENTIAL DIAGNOSIS ENGINE                        │
│  1. Rank disorders by screening scores                          │
│  2. Check diagnostic thresholds (e.g., OCD ≥ 7/10)             │
│  3. Apply exclusion criteria (medical, substance, other)        │
│  4. Identify top candidate(s)                                   │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
            ┌────────┴────────┐
            │  Any ≥ threshold? │
            └────┬──────────┬──┘
                 │ YES      │ NO
                 ↓          ↓
    ┌────────────────┐   ┌──────────────────┐
    │ TARGETED Q's   │   │ RULE-OUT CHECK   │
    │ Ask disorder-  │   │ Verify truly     │
    │ specific Qs to │   │ normal vs sub-   │
    │ confirm/refute │   │ clinical         │
    └───────┬────────┘   └────────┬─────────┘
            ↓                     ↓
    ┌────────────────┐    ┌──────────────────┐
    │ FINAL DECISION │    │ NORMAL RESPONSE  │
    │ - Disorder(s)  │    │ - Coping advice  │
    │ - Severity     │    │ - Monitoring     │
    │ - Treatment    │    │ - When to worry  │
    └────────────────┘    └──────────────────┘
```

### **Key Design Principles**

**1. NO PREMATURE EXCLUSION**
- ❌ Remove binary "normal vs disorder" gate
- ✅ ALL cases undergo systematic screening
- ✅ Let screening scores determine route, not assessment scores

**2. PARALLEL SCREENING**
- ❌ Don't assume single disorder
- ✅ Screen for multiple disorders simultaneously
- ✅ Detect co-morbidities (e.g., GAD + MDD, OCD + Depression)

**3. THRESHOLD-BASED ROUTING**
- ❌ Don't use arbitrary total scores
- ✅ Each disorder has specific threshold (based on DSM-5/ICD-11)
- ✅ Different thresholds for "possible" vs "likely" vs "highly probable"

**4. VERIFICATION MECHANISM**
- ❌ Don't diagnose based on keywords alone
- ✅ Ask targeted questions for high-scoring disorders
- ✅ Apply exclusion criteria systematically

**5. GRACEFUL DEGRADATION**
- ❌ Don't force diagnosis when uncertain
- ✅ Output "subclinical" or "monitoring recommended"
- ✅ Explain reasoning transparently

---

## 🔧 IMPLEMENTATION DETAILS

### **Phương án đề xuất: Option 2 (Red Flags + Targeted Questions)**

**Lý do:**
- Balance giữa accuracy và complexity
- Ít thay đổi architecture nhất
- Có thể iterate dễ dàng

### **1. Thêm Red Flags Detection**

**File mới:** `backend/src/rag/utils/red_flags_detector.py`

```python
"""
Red Flags Detector - Identify potential disorders from symptoms
"""

RED_FLAGS_PATTERNS = {
    "ocd": {
        "keywords": [
            "kiểm tra", "checking", "lặp lại", "repeat",
            "phải làm", "must do", "bắt buộc", "compelled",
            "xâm nhập", "intrusive", "ám ảnh", "obsessive",
            "nghi thức", "ritual", "trình tự", "sequence"
        ],
        "patterns": [
            r"kiểm\s*tra\s*(đi|lại)+",
            r"phải\s+(làm|kiểm\s*tra)",
            r"lo\s+(sợ|lắng)\s+.*\s+(quên|sơ\s*suất|gây)",
            r"\d+\s*(lần|times)\s+(checking|kiểm\s*tra)"
        ],
        "score_threshold": 3  # Need at least 3 hits to flag
    },
    
    "panic_disorder": {
        "keywords": [
            "tim đập", "heart racing", "khó thở", "breathless",
            "chóng mặt", "dizzy", "mất kiểm soát", "losing control",
            "chết", "die", "sắp", "about to"
        ],
        "patterns": [
            r"(tim|heart)\s+(đập|racing|pounding)",
            r"(khó|difficulty)\s+(thở|breath)",
            r"(sợ|fear)\s+(chết|die|sắp\s+chết)"
        ],
        "score_threshold": 3
    },
    
    "gad": {
        "keywords": [
            "lo lắng", "worry", "căng thẳng", "tension",
            "kiểm soát", "control", "liên tục", "constantly",
            "nhiều thứ", "many things", "mọi thứ", "everything"
        ],
        "patterns": [
            r"lo\s+(lắng|âu)\s+(về|cho)\s+(nhiều|mọi)",
            r"không\s+(thể|thể)\s+kiểm\s*soát",
            r"căng\s+thẳng\s+(liên\s*tục|suốt)"
        ],
        "score_threshold": 3
    }
}

def detect_red_flags(slots: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Detect potential disorder red flags from slots.
    
    Returns:
        {
            "ocd": {"detected": True, "score": 5, "matched": [...]},
            "panic_disorder": {"detected": False, "score": 1, ...},
            ...
        }
    """
    import re
    
    results = {}
    
    # Combine all text fields for analysis
    text_fields = [
        slots.get("emotion", []),
        slots.get("primary_symptoms", []),
        slots.get("physical_symptoms", []),
        slots.get("trigger", ""),
        slots.get("impact", ""),
        slots.get("daily_functioning", ""),
        slots.get("work_school_impact", "")
    ]
    
    combined_text = " ".join(
        [str(item) for field in text_fields 
         for item in (field if isinstance(field, list) else [field])]
    ).lower()
    
    for disorder, config in RED_FLAGS_PATTERNS.items():
        score = 0
        matched_keywords = []
        matched_patterns = []
        
        # Check keywords
        for keyword in config["keywords"]:
            if keyword in combined_text:
                score += 1
                matched_keywords.append(keyword)
        
        # Check regex patterns
        for pattern in config["patterns"]:
            if re.search(pattern, combined_text):
                score += 2  # Patterns count more than keywords
                matched_patterns.append(pattern)
        
        detected = score >= config["score_threshold"]
        
        results[disorder] = {
            "detected": detected,
            "score": score,
            "threshold": config["score_threshold"],
            "matched_keywords": matched_keywords,
            "matched_patterns": matched_patterns
        }
    
    return results
```

### **2. Thêm OCD-Specific Slots**

**File:** `backend/src/rag/utils/slots.py`

```python
# Thêm vào DIFFERENTIAL_DIAGNOSIS_SLOTS
OCD_SPECIFIC_SLOTS = [
    "compulsion_time_per_day",     # Thời gian dành cho nghi thức mỗi ngày
    "repetition_count",             # Số lần lặp lại
    "has_rituals",                  # Có nghi thức cụ thể không
    "sense_of_compulsion",          # Cảm giác bị thôi thúc
    "anxiety_if_resist",            # Lo âu tăng nếu cố không làm
    "avoidance_behavior",           # Có tránh né tình huống không
    "mental_checking",              # Có kiểm tra trong đầu không
    "obsession_type",               # Loại ám ảnh: contamination/harm/symmetry/...
    "insight_level"                 # Có nhận ra là thái quá không
]
```

### **3. Thêm OCD Assessment Questions**

**File mới:** `backend/src/rag/prompts/ocd_assessment_prompt.yaml`

```yaml
ocd_assessment_prompt: |
  Based on the symptoms described, I need to ask specific questions to determine if this might be OCD (Obsessive-Compulsive Disorder).
  
  CURRENT SYMPTOMS:
  {{CURRENT_SYMPTOMS}}
  
  CRITICAL OCD ASSESSMENT QUESTIONS (ask in Vietnamese):
  
  1. TIME CONSUMED (compulsion_time_per_day):
     "Mỗi ngày bạn dành khoảng bao nhiêu thời gian cho việc kiểm tra/làm nghi thức này?"
     
  2. ANXIETY IF RESIST (anxiety_if_resist):
     "Nếu bạn cố gắng KHÔNG kiểm tra, mức lo lắng/khó chịu của bạn tăng ra sao? Và nó có giảm đi sau một thời gian không?"
     
  3. RITUALS/PATTERNS (has_rituals, repetition_count):
     "Có số lần kiểm tra cụ thể không? Phải kiểm tra đúng cách/đúng trình tự/đúng 'cảm giác' nào đó mới có thể thôi?"
     
  4. AVOIDANCE (avoidance_behavior):
     "Có tình huống nào bạn cố tránh vì biết nếu gặp sẽ phải kiểm tra/lo lắng không?"
     
  5. MENTAL CHECKING (mental_checking):
     "Ngoài kiểm tra bằng hành động, bạn có 'kiểm tra trong đầu' không? (nhớ lại xem mình đã làm gì, đã làm đúng chưa)"
     
  6. FUNCTIONAL IMPAIRMENT (confirm from previous):
     "Việc này ảnh hưởng cụ thể thế nào đến: công việc, quan hệ, giấc ngủ, chất lượng cuộc sống?"
     
  7. INSIGHT (insight_level):
     "Khi không ở trong tình huống, bạn có nhận ra rằng việc kiểm tra nhiều lần là 'thái quá' hoặc 'không hợp lý' không?"
  
  EXTRACTION INSTRUCTIONS:
  - Extract answers into OCD-specific slots
  - DO NOT diagnose yet - only collect information
  - If answer suggests OCD criteria met → set flag for diagnostic flow
```

### **4. Update Workflow với Red Flags Check**

**File:** `backend/src/rag/workflow/workflow.py`

```python
# Thêm node mới
from src.rag.utils.red_flags_detector import detect_red_flags

async def red_flags_check_node(state: KGState) -> KGState:
    """
    Check for disorder red flags and decide if need targeted questions.
    """
    slots = state.get("slots", {})
    
    # Detect red flags
    red_flags = detect_red_flags(slots)
    
    state["red_flags"] = red_flags
    
    # Log detected flags
    detected_disorders = [d for d, info in red_flags.items() if info["detected"]]
    if detected_disorders:
        logger.warning(f"🚩 Red flags detected: {detected_disorders}")
    
    return state

# Update routing logic
def route_after_red_flags(state: KGState) -> str:
    """
    Route based on red flags + assessment.
    """
    red_flags = state.get("red_flags", {})
    assessment_category = state.get("assessment_category", "possible_disorder")
    
    # Check if any red flags detected
    has_red_flags = any(info["detected"] for info in red_flags.values())
    
    if has_red_flags:
        # Has red flags → ask targeted questions
        logger.info("[ROUTING] Red flags detected → targeted_questions_node")
        return "targeted_questions"
    
    # No red flags → follow normal assessment routing
    if assessment_category in ["normal_stress", "adjustment_reaction"]:
        return "normal_coping"
    else:
        return "diagnostic_flow"
```

### **5. Cập nhật Assessment để không "chốt" quá sớm**

**File:** `backend/src/rag/utils/assessment.py`

```python
def assess_with_uncertainty(slots: Dict[str, Any], matched_items: List[Dict[str, Any]], 
                           red_flags: Dict[str, Dict[str, Any]]) -> Tuple[str, str, float, bool]:
    """
    Enhanced assessment that considers red flags.
    
    Returns:
        (category, explanation, confidence, needs_more_info)
        
    Categories:
        - normal_stress
        - adjustment_reaction
        - uncertain_ocd (NEW!)
        - uncertain_gad (NEW!)
        - possible_disorder
        - likely_disorder
    """
    
    # Run normal assessment
    base_category, base_explanation, base_confidence = assess_disorder_likelihood(slots, matched_items)
    
    # Check red flags
    has_ocd_flags = red_flags.get("ocd", {}).get("detected", False)
    has_gad_flags = red_flags.get("gad", {}).get("detected", False)
    
    # Override if red flags present but assessment says normal
    if base_category in ["normal_stress", "adjustment_reaction"]:
        if has_ocd_flags:
            return ("uncertain_ocd", 
                   "Triệu chứng có một số đặc điểm của OCD. Cần hỏi thêm để xác định rõ hơn.",
                   0.5,
                   True)  # needs_more_info = True
        
        if has_gad_flags:
            return ("uncertain_gad",
                   "Triệu chứng có đặc điểm của rối loạn lo âu tổng quát. Cần hỏi thêm.",
                   0.5,
                   True)
    
    # No conflict → return base assessment
    return (base_category, base_explanation, base_confidence, False)
```

---

## 📝 IMPLEMENTATION STEPS

### **Phase 1: Red Flags Detection (Week 1)**

1. ✅ Tạo `red_flags_detector.py` với OCD/GAD/Panic patterns
2. ✅ Add `red_flags_check_node` vào workflow
3. ✅ Update routing để check red flags
4. ✅ Test với OCD case

### **Phase 2: OCD-Specific Questions (Week 2)**

1. ✅ Add OCD_SPECIFIC_SLOTS vào slots.py
2. ✅ Tạo `ocd_assessment_prompt.yaml`
3. ✅ Tạo `targeted_questions_node` trong workflow
4. ✅ Update slot_filling để handle OCD slots

### **Phase 3: Enhanced Assessment (Week 3)**

1. ✅ Update `assessment.py` với `assess_with_uncertainty()`
2. ✅ Add "uncertain_ocd", "uncertain_gad" categories
3. ✅ Update routing logic để handle uncertain states
4. ✅ Test end-to-end flow

### **Phase 4: Testing & Validation (Week 4)**

1. ✅ Test với 10 OCD cases
2. ✅ Test với 10 GAD cases
3. ✅ Test với 10 normal stress cases
4. ✅ Measure accuracy, false positives, false negatives
5. ✅ Tune thresholds và patterns

---

## 🎯 SUCCESS METRICS

**Accuracy targets:**
- OCD detection rate: ≥ 85% (from current ~0%)
- False positive rate: ≤ 15%
- Normal stress correctly identified: ≥ 80%

**User experience:**
- Average questions to diagnosis: ≤ 15 turns
- User satisfaction with accuracy: ≥ 4/5

---

## ⚠️ RISKS & MITIGATION

**Risk 1: Too many false positives**
- **Mitigation**: Tune score thresholds, add more specific patterns

**Risk 2: Users frustrated with more questions**
- **Mitigation**: Explain why asking (transparency)

**Risk 3: Complexity increases debugging difficulty**
- **Mitigation**: Extensive logging, unit tests for each component

---

## 🔄 ALTERNATIVE: Simpler Approach

**If Option 2 too complex, fallback to:**

### **Simple Red Flag Prompt Enhancement**

Update `slot_filling_prompt.yaml` với section:

```yaml
⚠️ **RED FLAG DETECTION**:

If user describes:
- Repetitive behaviors (kiểm tra lặp lại, rituals)
- Intrusive thoughts (ý nghĩ xâm nhập, ám ảnh)
- Compulsion (phải làm, bị thôi thúc)
- Distress if resist (khó chịu nếu không làm)

→ ALWAYS ask these follow-up questions:
1. "Mỗi ngày bạn dành bao nhiêu thời gian cho việc này?"
2. "Nếu cố không làm thì mức lo lắng tăng thế nào?"
3. "Có số lần hoặc trình tự cụ thể phải làm đúng không?"

→ DO NOT conclude "normal stress" until these are answered
```

**Pros:** Minimal code changes
**Cons:** Less systematic, might still miss cases

---

## 📚 REFERENCES

- DSM-5 OCD Criteria
- ICD-11 6B20 Obsessive-Compulsive Disorder
- Yale-Brown Obsessive Compulsive Scale (Y-BOCS)
- Clinical interviewing techniques for OCD

---

## ✅ NEXT STEPS

1. **Review this plan** with team
2. **Choose option** (recommend Option 2)
3. **Start Phase 1** implementation
4. **Set up test cases** for validation

---

**Created by:** GitHub Copilot  
**Date:** 2026-01-06  
**Status:** DRAFT - Awaiting approval
