# KỊCH BẢN CẢI THIỆN SLOT FILLING THEO DSM-5

**Ngày tạo:** 2026-01-08  
**Mục tiêu:** Redesign slot filling system theo chuẩn DSM-5 intake flow  
**Nguyên tắc:** Làm việc với tiếng Anh (đã có translate node), bắt buộc hỏi đủ theo luồng

---

## 📋 TÓM TẮT YÊU CẦU

### Vấn đề hiện tại:
1. ❌ Slot filling làm việc với tiếng Việt trong khi đã có translate node → tốn công
2. ❌ "No"/"none" bị lưu null → hỏi lại mãi
3. ❌ Impact lẫn lộn giữa distress (chủ quan) và impairment (khách quan)
4. ❌ Exclusion thiếu medication_changes, caffeine, mania/psychosis screening
5. ❌ Required slots không theo luồng intake chuẩn DSM-5
6. ❌ Merge severity (intensity/stress_level) bị bug vì xử lý list sai

### Giải pháp:
1. ✅ Chuyển tất cả prompt sang tiếng Anh
2. ✅ Lưu "no"/"none" dạng string trong list, KHÔNG để null/empty
3. ✅ Tách rõ distress vs impairment
4. ✅ Thêm exclusion slots: medication_changes, caffeine_nicotine_use
5. ✅ Thêm cross-cutting screens: mania_like_symptoms, psychotic_like_symptoms
6. ✅ Tổ chức lại slots theo 9 nhóm DSM-5
7. ✅ Required slots theo stage flow (phải đủ theo thứ tự)
8. ✅ Fix merge logic để không mất "no" và severity xử lý đúng

---

## 📂 CÁC FILE CẦN CHỈNH SỬA

### 1. **backend/src/rag/prompts/slot_filling_prompt.yaml**
- Đổi prompt sang tiếng Anh
- Cập nhật slot definitions theo DSM-5
- Thêm rules cho "no/none" → string in list
- Thêm examples với English input

### 2. **backend/src/rag/utils/slots.py**
- Thêm slots mới vào `get_default_slots()`
- Reorganize `DIAGNOSTIC_SLOTS` thành 9 groups
- Thay `REQUIRED_SLOTS` thành `REQUIRED_SLOTS_BY_STAGE` + `STAGE_FLOW`
- Fix `merge_slots()` để không skip "no"/"none"
- Fix severity merge với list
- Fix `validate_duration()` để "2 weeks" = specific
- Thêm helpers: `is_empty_slot()`, `next_missing_slot()`, `is_intake_complete()`
- Cập nhật `build_slot_context()` với slots mới

### 3. **backend/src/rag/workflow/graph_nodes/slot_filling.py**
- Cập nhật logic để check intake_complete theo stage
- Thêm log stage progression
- Filter follow-up theo stage hiện tại

### 4. **backend/src/rag/utils/slot_utils.py** (nếu có)
- Cập nhật các helper functions theo slots mới

---

## 🔧 CHI TIẾT THAY ĐỔI TỪNG FILE

---

## FILE 1: slot_filling_prompt.yaml

### 1.1. Đổi Prompt Header sang tiếng Anh

```yaml
slot_filling_prompt: |
  You are a mental health intake specialist conducting a structured clinical interview. Extract information into structured slots (in English) and generate contextually relevant follow-up questions.

  USER INPUT (translated to English):
  {{QUESTION}}

  ALREADY FILLED SLOTS:
  {{EXISTING_SLOTS}}

  ========== CRITICAL RULES ==========
  
  ⚠️ **WORK IN ENGLISH**: All extraction must be in English (user input already translated)
  
  ⚠️ **AVOID RE-ASKING**: If slot shown in "ALREADY FILLED SLOTS" → PRESERVE value, do NOT ask again
  
  ⚠️ **ALL SLOTS ARE LISTS** (except tri-state fields): Extract all values as lists
  - Example: User mentions "stress at work" → trigger = ["work stress"]
  - Next turn: User mentions "family issues" → trigger = ["work stress", "family issues"] (merged)
  
  ⚠️ **"NO/NONE" = STRING IN LIST**: When user says "no/none", extract as STRING in list, NOT empty list
  - Example: "No major life events" → recent_life_events = ["no major life events"]
  - Example: "No medical conditions" → medical_history = ["no medical conditions"]
  - Example: "Don't use substances" → substance_use = ["no substance use"]
  
  ⚠️ **TRI-STATE FIELDS**: Some fields use "yes"/"no"/"unknown" (not lists)
  - substance_use_any: "yes"/"no"/"unknown"
  - medical_history_any: "yes"/"no"/"unknown"
  - mania_like_symptoms: "yes"/"no"/"unknown"
  - psychotic_like_symptoms: "yes"/"no"/"unknown"
  
  ⚠️ **COMPOUND SENTENCES**: When user says "no X, BUT Y", extract FULL context as separate items:
  - Example: "No major events, but work deadlines piling up" 
    → recent_life_events = ["no major life events", "increased work deadlines"]

  **DSM-5 INTERVIEW PRIORITIES**:
  1. Presenting problem & timeline (onset, duration, frequency)
  2. Severity assessment (distress + impairment in multiple domains)
  3. Exclusion criteria (substance, medical, medication changes, caffeine)
  4. Cross-cutting screens (mania, psychosis)
  5. Context & support
  6. Ask 1-2 questions max per turn, following stage flow
```

### 1.2. Cập nhật Slot Definitions (DSM-5 Structure)

```yaml
  ========== SLOT DEFINITIONS (DSM-5 INTAKE STRUCTURE) ==========
  
  **SLOT GROUPS** (follow this order in interview):
  
  # A. PRESENTING / CORE (what brings you here)
  - presenting_problem: [] (main concern in 1-2 sentences)
  - emotion: [] (specific emotions: "anxious", "sad", "irritable")
  - primary_mood: [] (baseline mood state: "depressed", "elevated", "neutral")
  
  # B. TIMELINE / COURSE (when, how long, pattern)
  - onset: [] (when did it start: "2 weeks ago", "since last month", "gradually over 6 months")
  - duration: [] (how long has it lasted: "2 weeks", "3 months", "on and off for 1 year")
  - frequency: [] (how often: "daily", "3-4 times per week", "intermittent")
  - symptom_fluctuation: [] ("constant", "episodic", "fluctuating", "worse at specific times")
  - time_of_day_pattern: [] (OPTIONAL: "worse in morning", "worse at night")
  
  # C. SEVERITY (how intense)
  - intensity: [] (symptom intensity: "mild", "moderate", "severe", "overwhelming")
  - distress_level: [] (subjective distress: "mild distress", "moderate distress", "severe distress", or 0-10 scale)
  - stress_level: [] (perceived stress: "low", "moderate", "high", "overwhelming")
  
  # D. IMPAIRMENT / FUNCTIONING (how does it affect life - CRITICAL for DSM-5)
  - daily_functioning: [] (overall daily tasks: "minimal impairment", "moderate difficulty", "severe impairment")
  - work_school_impact: [] (work/study impact: "missing deadlines", "reduced productivity", "unable to work")
  - social_functioning: [] (relationships/social: "avoiding friends", "conflicts increased", "isolated")
  - self_care_functioning: [] (hygiene/eating/self-care: "neglecting hygiene", "skipping meals", "no issues")
  
  # E. SOMATIC / BIO (physical symptoms)
  - physical_symptoms: [] ("rapid heartbeat", "headaches", "fatigue", "trembling")
  - sleep_quality: [] ("poor", "frequent waking", "difficulty falling asleep", "good")
  - sleep_duration: [] ("4-5 hours", "less than normal", "excessive sleep")
  - energy_level: [] ("very low", "exhausted", "normal", "unusually high")
  - appetite_changes: [] ("decreased appetite", "overeating", "no change")
  
  # F. CONTEXT / PSYCHOSOCIAL (triggers, stressors, life events)
  - trigger: [] ("work stress", "relationship conflict", "exam pressure")
  - current_stressors: [] ("work deadlines", "financial concerns", "family issues")
  - recent_life_events: [] ("job loss", "relationship breakup", "no major events", "moved to new city")
  
  # G. SUPPORT / COPING (resources)
  - support_system: [] ("has family support", "close friends available", "isolated")
  - coping_mechanisms: [] ("exercise", "meditation", "talking to friends", "avoidance")
  - coping_effectiveness: [] ("somewhat helpful", "not working well", "very effective")
  - need: [] ("someone to listen", "advice on coping", "professional help")
  
  # H. EXCLUSION CRITERIA (CRITICAL - rule out medical/substance causes)
  - substance_use_any: "unknown" (TRI-STATE: "yes"/"no"/"unknown")
  - substance_use: [] (if _any="yes": ["alcohol daily", "increased coffee intake", "recreational drugs"])
  - medical_history_any: "unknown" (TRI-STATE: "yes"/"no"/"unknown")
  - medical_history: [] (if _any="yes": ["thyroid condition", "diabetes", "heart disease"])
  - medication_changes: [] ("started new antidepressant 1 week ago", "no recent changes")
  - caffeine_nicotine_use: [] ("3-4 coffees daily", "smoking 1 pack/day", "no caffeine/nicotine")
  - current_treatment: [] ("therapy weekly", "medication for depression")
  - medication: [] ("sertraline 50mg", "no medication")
  
  # I. CROSS-CUTTING SCREENS (rule out other disorders - CRITICAL)
  - mania_like_symptoms: "unknown" (TRI-STATE: any decreased sleep with increased energy, impulsivity, racing thoughts)
  - psychotic_like_symptoms: "unknown" (TRI-STATE: any hallucinations, delusions, paranoia)
  
  # J. HISTORY (context for chronicity/patterns)
  - history_of_trauma: [] ("childhood trauma", "no trauma history", "past assault")
  - symptom_fluctuation: [] (already in TIMELINE but keep for compatibility)
  
  # K. DERIVED FIELDS (computed, not extracted directly)
  - diagnostic_confidence: "low" (scalar: low/medium/high - based on completeness)
  - potential_differentials: [] (list of possible diagnoses to consider)
  - duration_certainty: "vague" (scalar: vague/approximate/specific)
  - intake_complete: false (boolean: all required slots filled)

  ⚠️ CRITICAL EXTRACTION RULES:
  - **ALL slots are LISTS []** except: TRI-STATE fields (_any, mania_like_symptoms, psychotic_like_symptoms) and DERIVED fields
  - **Single values go in list**: duration = ["2 weeks"] NOT duration = "2 weeks"
  - **"no/none" → STRING IN LIST**: medical_history = ["no medical conditions"] NOT []
  - **Empty [] vs ["no"]**: [] means not asked yet, ["no ..."] means user said "no"
  - **TRI-STATE**: substance_use_any = "yes"/"no"/"unknown" (if "yes" → ask substance_use details)
  - **Compound sentences → separate items**: "no X, but Y" → ["no X", "Y"]
```

### 1.3. Cập nhật Examples (English Input)

```yaml
  ========== EXAMPLES (ENGLISH INPUT) ==========

  EX1 - Presenting Problem + Vague Duration:
  USER: "I've been feeling very anxious at work lately"
  EXTRACT: 
    presenting_problem = ["feeling anxious at work"]
    emotion = ["anxious"]
    trigger = ["work"]
    duration = ["lately"]
    duration_certainty = "vague"
  ASK: "When did this anxiety start? Days, weeks, or months ago?", "Has anything specific happened at work recently?"
  
  EX2 - "No" should be captured as string:
  USER: "No major life events, but work deadlines are piling up and I'm sleeping poorly"
  EXTRACT: 
    recent_life_events = ["no major life events", "increased work deadlines"]
    sleep_quality = ["poor"]
    current_stressors = ["work deadlines"]
  ASK: "How long have the sleep issues been going on?", "How many hours of sleep are you getting per night?"
  
  EX3 - Physical Symptoms → Check Exclusion:
  USER: "This week I can't sleep, heart racing all the time"
  EXTRACT: 
    onset = ["this week"]
    duration = ["this week"]
    physical_symptoms = ["heart racing", "insomnia"]
    sleep_quality = ["very poor"]
  ASK: "Have you been using more caffeine than usual?", "Do you have any history of thyroid or heart conditions?", "Any new medications recently?"
  WHY: Physical symptoms (heart racing) → MUST check caffeine, medical history, medication changes
  
  EX4 - Check for Mania-like Symptoms:
  USER: "I feel great, only sleeping 3-4 hours but have tons of energy, starting multiple projects"
  EXTRACT:
    primary_mood = ["elevated", "great"]
    sleep_duration = ["3-4 hours"]
    energy_level = ["very high", "tons of energy"]
    mania_like_symptoms = "yes"
  ASK: "How long has this been going on?", "Is this level of energy unusual for you?", "Have you noticed yourself being more impulsive or spending more money than usual?"
  WHY: Decreased sleep + increased energy → possible mania, MUST screen
  
  EX5 - Tri-state: Ask detail only if "yes":
  USER: "I don't use any drugs or alcohol"
  EXTRACT:
    substance_use_any = "no"
    substance_use = ["no substance use"]
  NOTE: substance_use_any = "no" → don't need to ask substance_use details
  
  EX6 - Impairment Assessment (CRITICAL for DSM-5):
  USER: "I'm struggling to get out of bed, missing work, stopped seeing friends"
  EXTRACT:
    daily_functioning = ["difficulty getting out of bed"]
    work_school_impact = ["missing work"]
    social_functioning = ["stopped seeing friends", "socially withdrawn"]
  ASK: "How long has this been going on?", "Are you still able to take care of basic hygiene and meals?", "What about hobbies or activities you used to enjoy?"
  WHY: Multiple domains of impairment → need timeline + self-care check + anhedonia check
```

### 1.4. Cập nhật JSON Output Schema

```yaml
  ========== OUTPUT JSON SCHEMA ==========
  
  Return ONLY valid JSON in this exact format (all slots must be present):
  
  {
    "slots": {
      // A. PRESENTING
      "presenting_problem": [],
      "emotion": [],
      "primary_mood": [],
      
      // B. TIMELINE
      "onset": [],
      "duration": [],
      "frequency": [],
      "symptom_fluctuation": [],
      "time_of_day_pattern": [],
      
      // C. SEVERITY
      "intensity": [],
      "distress_level": [],
      "stress_level": [],
      
      // D. IMPAIRMENT
      "daily_functioning": [],
      "work_school_impact": [],
      "social_functioning": [],
      "self_care_functioning": [],
      
      // E. SOMATIC
      "physical_symptoms": [],
      "sleep_quality": [],
      "sleep_duration": [],
      "energy_level": [],
      "appetite_changes": [],
      
      // F. CONTEXT
      "trigger": [],
      "current_stressors": [],
      "recent_life_events": [],
      
      // G. SUPPORT/COPING
      "support_system": [],
      "coping_mechanisms": [],
      "coping_effectiveness": [],
      "need": [],
      
      // H. EXCLUSION
      "substance_use_any": "unknown",
      "substance_use": [],
      "medical_history_any": "unknown",
      "medical_history": [],
      "medication_changes": [],
      "caffeine_nicotine_use": [],
      "current_treatment": [],
      "medication": [],
      
      // I. SCREENS
      "mania_like_symptoms": "unknown",
      "psychotic_like_symptoms": "unknown",
      
      // J. HISTORY
      "history_of_trauma": [],
      
      // K. DERIVED
      "diagnostic_confidence": "low",
      "potential_differentials": [],
      "duration_certainty": "vague",
      "intake_complete": false
    },
    "missing_slots": [],
    "relevant_missing_slots": [],
    "follow_up_questions": []
  }

  ⚠️ CRITICAL OUTPUT RULES: 
  - **ALL fields must be present in output**
  - **Lists must be arrays []**, tri-states must be "yes"/"no"/"unknown"
  - **"no/none" → STRING IN LIST**: medical_history=["no medical conditions"] NOT []
  - **Empty [] vs ["no"]**: [] = not asked, ["no..."] = user said no
  - **Follow-up questions**: Array of strings in English
```

---

## FILE 2: backend/src/rag/utils/slots.py

### 2.1. Thêm Constants cho Stage Flow

```python
# ============================================================================
# DSM-5 STAGE FLOW CONSTANTS
# ============================================================================

# Stage order for structured intake (DSM-5 based)
STAGE_FLOW = [
    "presenting",     # What brings you here
    "timeline",       # When, how long, pattern
    "severity",       # How severe (distress + intensity)
    "functioning",    # Impairment (DSM-5 Criterion B)
    "context",        # Triggers, stressors, life events
    "exclusion",      # Rule out medical/substance (DSM-5 Criterion D)
    "support_coping", # Resources available
    "screens"         # Cross-cutting symptoms (mania, psychosis)
]

# Diagnostic slots organized by stage
DIAGNOSTIC_SLOTS = {
    "presenting": [
        "presenting_problem",
        "emotion",
        "primary_mood"
    ],
    "timeline": [
        "onset",
        "duration",
        "frequency",
        "symptom_fluctuation",
        "time_of_day_pattern"
    ],
    "severity": [
        "intensity",
        "distress_level",
        "stress_level"
    ],
    "functioning": [
        "daily_functioning",
        "work_school_impact",
        "social_functioning",
        "self_care_functioning"
    ],
    "somatic": [
        "physical_symptoms",
        "sleep_quality",
        "sleep_duration",
        "energy_level",
        "appetite_changes"
    ],
    "context": [
        "trigger",
        "current_stressors",
        "recent_life_events"
    ],
    "support_coping": [
        "support_system",
        "coping_mechanisms",
        "coping_effectiveness",
        "need"
    ],
    "exclusion": [
        "substance_use_any",
        "substance_use",
        "medical_history_any",
        "medical_history",
        "medication_changes",
        "caffeine_nicotine_use",
        "current_treatment",
        "medication"
    ],
    "screens": [
        "mania_like_symptoms",
        "psychotic_like_symptoms"
    ],
    "history": [
        "history_of_trauma"
    ]
}

# Required slots per stage (MUST be filled before moving to next stage)
REQUIRED_SLOTS_BY_STAGE = {
    "presenting": [
        "presenting_problem",
        "emotion",
        "primary_mood"
    ],
    "timeline": [
        "onset",
        "duration",
        "frequency",
        "symptom_fluctuation"
    ],
    "severity": [
        "intensity",
        "distress_level",
        "stress_level"
    ],
    "functioning": [
        "daily_functioning",
        "work_school_impact",
        "social_functioning",
        "self_care_functioning"
    ],
    "context": [
        "trigger",
        "current_stressors",
        "recent_life_events"
    ],
    "exclusion": [
        "substance_use_any",
        "medical_history_any",
        "medication_changes",
        "caffeine_nicotine_use"
    ],
    "support_coping": [
        "support_system",
        "coping_mechanisms"
    ],
    "screens": [
        "mania_like_symptoms",
        "psychotic_like_symptoms"
    ]
}

# Flatten for legacy compatibility
REQUIRED_SLOTS = [s for stage in STAGE_FLOW for s in REQUIRED_SLOTS_BY_STAGE.get(stage, [])]

# Tri-state fields (not lists)
TRI_STATE_FIELDS = {
    "substance_use_any",
    "medical_history_any",
    "mania_like_symptoms",
    "psychotic_like_symptoms"
}

# Valid tri-state values
TRI_STATES = {"yes", "no", "unknown"}
```

### 2.2. Cập nhật get_default_slots()

```python
def get_default_slots() -> Dict[str, Any]:
    """
    Return default empty slots structure (DSM-5 based).
    All slots initialized as [] (lists) or "unknown" (tri-states).
    """
    return {
        # A. PRESENTING / CORE
        "presenting_problem": [],
        "emotion": [],
        "primary_mood": [],
        
        # B. TIMELINE / COURSE
        "onset": [],
        "duration": [],
        "frequency": [],
        "symptom_fluctuation": [],
        "time_of_day_pattern": [],
        
        # C. SEVERITY
        "intensity": [],
        "distress_level": [],
        "stress_level": [],
        
        # D. IMPAIRMENT / FUNCTIONING
        "daily_functioning": [],
        "work_school_impact": [],
        "social_functioning": [],
        "self_care_functioning": [],
        
        # E. SOMATIC / BIO
        "physical_symptoms": [],
        "sleep_quality": [],
        "sleep_duration": [],
        "energy_level": [],
        "appetite_changes": [],
        
        # F. CONTEXT / PSYCHOSOCIAL
        "trigger": [],
        "current_stressors": [],
        "recent_life_events": [],
        
        # G. SUPPORT / COPING
        "support_system": [],
        "coping_mechanisms": [],
        "coping_effectiveness": [],
        "need": [],
        
        # H. EXCLUSION CRITERIA (TRI-STATE + details)
        "substance_use_any": "unknown",      # TRI-STATE
        "substance_use": [],
        "medical_history_any": "unknown",    # TRI-STATE
        "medical_history": [],
        "medication_changes": [],
        "caffeine_nicotine_use": [],
        "current_treatment": [],
        "medication": [],
        
        # I. CROSS-CUTTING SCREENS (TRI-STATE)
        "mania_like_symptoms": "unknown",    # TRI-STATE
        "psychotic_like_symptoms": "unknown", # TRI-STATE
        
        # J. HISTORY
        "history_of_trauma": [],
        
        # K. DERIVED FIELDS
        "diagnostic_confidence": "low",
        "potential_differentials": [],
        "duration_certainty": "vague",
        "intake_complete": False
    }
```

### 2.3. Fix merge_slots() - Không Skip "no"/"none"

```python
def merge_slots(existing_slots: Optional[Dict[str, Any]], new_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge new slots into existing slots (append/update instead of replace).
    
    FIXED RULES:
    - List fields: Append unique values (preserve "no ..." strings)
    - Tri-state fields: Update only if more informative
    - Scalar fields: Update only if new value is not None/empty
    - NEVER skip "no" or "none" strings (they are valid data)
    
    Args:
        existing_slots: Current slots from state
        new_slots: Newly extracted slots
    
    Returns:
        Merged slots dictionary
    """
    SEVERITY_ORDER = {
        "intensity": ["mild", "moderate", "severe", "very_severe", "overwhelming"],
        "distress_level": ["none", "mild", "moderate", "severe"],
        "stress_level": ["low", "moderate", "high", "overwhelming"]
    }
    
    if not existing_slots:
        merged = get_default_slots()
    else:
        merged = existing_slots.copy()
    
    for key, new_value in new_slots.items():
        # Skip only if truly empty (NOT if "no"/"none" string)
        if new_value is None:
            continue
        if isinstance(new_value, str) and new_value.strip() == "":
            continue
        if isinstance(new_value, list) and len(new_value) == 0:
            continue
        
        existing_value = merged.get(key)
        
        # Handle tri-state fields (substance_use_any, etc.)
        if key in TRI_STATE_FIELDS:
            new_lower = new_value.lower() if isinstance(new_value, str) else "unknown"
            if new_lower not in TRI_STATES:
                new_lower = "unknown"
            
            existing_lower = existing_value.lower() if isinstance(existing_value, str) else "unknown"
            
            # Tri-state priority: "yes" > "no" > "unknown"
            priority = {"yes": 3, "no": 2, "unknown": 1}
            if priority.get(new_lower, 0) > priority.get(existing_lower, 0):
                merged[key] = new_lower
            continue
        
        # Handle list fields (most slots)
        if isinstance(new_value, list):
            existing_list = existing_value if isinstance(existing_value, list) else []
            
            # Merge lists: append unique values
            combined = existing_list.copy()
            for item in new_value:
                if item and item not in combined:
                    combined.append(item)
            
            merged[key] = combined
            
            # For severity fields, also compute "_current" scalar (max severity)
            if key in SEVERITY_ORDER:
                best_severity = None
                best_idx = -1
                for val in combined:
                    val_lower = str(val).lower().strip()
                    if val_lower in SEVERITY_ORDER[key]:
                        idx = SEVERITY_ORDER[key].index(val_lower)
                        if idx > best_idx:
                            best_idx = idx
                            best_severity = val_lower
                merged[key + "_current"] = best_severity or "unknown"
            
            continue
        
        # Handle scalar fields (diagnostic_confidence, duration_certainty, etc.)
        if isinstance(new_value, (str, int, float, bool)):
            # For severity scalars, apply max logic
            if key in SEVERITY_ORDER:
                existing_str = str(existing_value).lower() if existing_value else ""
                new_str = str(new_value).lower()
                
                order = SEVERITY_ORDER[key]
                existing_idx = order.index(existing_str) if existing_str in order else -1
                new_idx = order.index(new_str) if new_str in order else -1
                
                if new_idx > existing_idx:
                    merged[key] = new_value
            else:
                # Regular scalar: update if not empty
                if new_value or (isinstance(new_value, bool)):
                    merged[key] = new_value
            continue
    
    return merged
```

### 2.4. Fix validate_duration() - "2 weeks" = specific

```python
def validate_duration(duration_text: Optional[Any]) -> Tuple[bool, str]:
    """
    Check if duration is specific enough for DSM-5 criteria.
    
    FIXED LOGIC:
    1. Check for number + time unit FIRST → specific
    2. Then check vague terms
    3. Then check approximate terms
    
    Args:
        duration_text: Duration string or list
    
    Returns:
        Tuple of (is_specific, certainty_level)
        - is_specific: True if duration meets minimum specificity
        - certainty_level: 'specific', 'approximate', 'vague'
    """
    if not duration_text:
        return False, "vague"
    
    # Handle list: check most specific duration
    if isinstance(duration_text, list):
        best_certainty = "vague"
        best_specific = False
        for d in duration_text:
            is_spec, cert = validate_duration(d)
            if cert == "specific":
                return True, "specific"
            if cert == "approximate" and best_certainty == "vague":
                best_certainty = "approximate"
                best_specific = True
        return best_specific, best_certainty
    
    duration_lower = str(duration_text).lower()
    
    # Priority 1: Specific (number + time unit) → BEST
    has_number = any(char.isdigit() for char in duration_text)
    time_units = ["day", "days", "week", "weeks", "month", "months", "year", "years",
                  "ngày", "tuần", "tháng", "năm"]
    if has_number and any(unit in duration_lower for unit in time_units):
        return True, "specific"
    
    # Priority 2: Vague terms → INSUFFICIENT
    vague_terms = ["lately", "recently", "just now", "gần đây", "dạo này", "mới đây"]
    if any(term in duration_lower for term in vague_terms):
        return False, "vague"
    
    # Priority 3: Approximate terms → ACCEPTABLE
    approximate_terms = ["several", "few", "about", "around", "approximately", 
                        "vài", "khoảng", "approximately"]
    if any(term in duration_lower for term in approximate_terms):
        return True, "approximate"
    
    # Default: if has substance (length > 5), treat as approximate
    if len(duration_text) > 5:
        return True, "approximate"
    
    return False, "vague"
```

### 2.5. Thêm Helper Functions

```python
def is_empty_slot(value: Any) -> bool:
    """
    Check if a slot value is considered empty/missing.
    
    Rules:
    - None → empty
    - Empty string → empty
    - "unknown" (tri-state) → empty
    - Empty list [] → empty
    - List with only empty strings → empty
    - "no ..." string → NOT empty (valid data)
    
    Args:
        value: Slot value to check
    
    Returns:
        True if slot is empty/missing
    """
    if value is None:
        return True
    
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "":
            return True
        # Tri-state: "unknown" is empty, but "yes"/"no" are valid
        if v in TRI_STATES:
            return v == "unknown"
        # Regular string: "none" without context is empty, but "no ..." is valid
        # Simple heuristic: if string contains space, it's descriptive (valid)
        if v == "none":
            return True
        return False
    
    if isinstance(value, list):
        if len(value) == 0:
            return True
        # List with only empty/whitespace strings
        return all(not str(x).strip() for x in value)
    
    if isinstance(value, bool):
        return False  # Booleans are always valid
    
    return False


def next_missing_slot(slots: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Find the next missing required slot following stage flow.
    
    Args:
        slots: Current slot dictionary
    
    Returns:
        Tuple of (stage_name, slot_name) or (None, None) if all complete
    """
    for stage in STAGE_FLOW:
        required_in_stage = REQUIRED_SLOTS_BY_STAGE.get(stage, [])
        
        for slot_name in required_in_stage:
            # Special handling for duration: must be specific
            if slot_name == "duration":
                is_specific, certainty = validate_duration(slots.get("duration"))
                slots["duration_certainty"] = certainty
                if not is_specific:
                    return stage, "duration"
                continue
            
            # Special handling for detail slots: only required if _any = "yes"
            if slot_name == "substance_use":
                if slots.get("substance_use_any", "unknown").lower() == "yes":
                    if is_empty_slot(slots.get("substance_use")):
                        return stage, "substance_use"
                continue
            
            if slot_name == "medical_history":
                if slots.get("medical_history_any", "unknown").lower() == "yes":
                    if is_empty_slot(slots.get("medical_history")):
                        return stage, "medical_history"
                continue
            
            # Regular slot check
            if is_empty_slot(slots.get(slot_name)):
                return stage, slot_name
    
    return None, None


def is_intake_complete(slots: Dict[str, Any]) -> bool:
    """
    Check if all required slots are filled (intake complete).
    
    Args:
        slots: Slot dictionary
    
    Returns:
        True if all required slots filled
    """
    stage, missing = next_missing_slot(slots)
    complete = (missing is None)
    slots["intake_complete"] = complete
    return complete


def get_current_stage(slots: Dict[str, Any]) -> str:
    """
    Determine current stage in intake flow based on filled slots.
    
    Args:
        slots: Slot dictionary
    
    Returns:
        Current stage name (or "complete" if all done)
    """
    stage, _ = next_missing_slot(slots)
    return stage if stage else "complete"
```

### 2.6. Cập nhật has_sufficient_slots() (backward compatible)

```python
def has_sufficient_slots(slots: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Check if required slots are filled sufficiently.
    Now uses stage-based logic.
    
    Args:
        slots: Slot dictionary
    
    Returns:
        Tuple of (is_sufficient, required_missing_slots, differential_missing_slots)
    """
    if not slots:
        return False, REQUIRED_SLOTS.copy(), []
    
    stage, missing_slot = next_missing_slot(slots)
    
    if missing_slot:
        # Gather all missing required slots
        missing = []
        for s in STAGE_FLOW:
            for slot in REQUIRED_SLOTS_BY_STAGE.get(s, []):
                if is_empty_slot(slots.get(slot)):
                    missing.append(slot)
        
        logger.info(f"[SLOT SUFFICIENCY] Current stage: {stage}, next missing: {missing_slot}")
        logger.info(f"[SLOT SUFFICIENCY] Total missing required: {len(missing)}")
        return False, missing, []
    
    logger.info(f"[SLOT SUFFICIENCY] ✅ ALL REQUIRED SLOTS FILLED - intake complete")
    return True, [], []
```

### 2.7. Cập nhật build_slot_context() với slots mới

```python
def build_slot_context(slots: Dict[str, Any]) -> str:
    """
    Build formatted context string from slots for answer generation.
    Updated with DSM-5 structure.
    """
    if not slots:
        return ""

    context_parts: List[str] = []

    # A. Presenting problem
    if slots.get("presenting_problem"):
        context_parts.append(f"Presenting problem: {', '.join(slots['presenting_problem'])}")
    
    # B. Core emotions/mood
    if slots.get("emotion"):
        context_parts.append(f"Emotions: {', '.join(slots['emotion'])}")
    if slots.get("primary_mood"):
        context_parts.append(f"Primary mood: {', '.join(slots['primary_mood'])}")
    
    # C. Timeline
    if slots.get("onset"):
        context_parts.append(f"Onset: {', '.join(slots['onset'])}")
    if slots.get("duration"):
        certainty = slots.get("duration_certainty", "unknown")
        context_parts.append(f"Duration: {', '.join(slots['duration'])} (certainty: {certainty})")
    if slots.get("frequency"):
        context_parts.append(f"Frequency: {', '.join(slots['frequency'])}")
    if slots.get("symptom_fluctuation"):
        context_parts.append(f"Pattern: {', '.join(slots['symptom_fluctuation'])}")
    
    # D. Severity
    if slots.get("intensity"):
        context_parts.append(f"Intensity: {', '.join(slots['intensity'])}")
    if slots.get("distress_level"):
        context_parts.append(f"Distress level: {', '.join(slots['distress_level'])}")
    if slots.get("stress_level"):
        context_parts.append(f"Stress level: {', '.join(slots['stress_level'])}")
    
    # E. Impairment (CRITICAL)
    impairment_domains = []
    if slots.get("daily_functioning"):
        impairment_domains.append(f"daily: {', '.join(slots['daily_functioning'])}")
    if slots.get("work_school_impact"):
        impairment_domains.append(f"work/school: {', '.join(slots['work_school_impact'])}")
    if slots.get("social_functioning"):
        impairment_domains.append(f"social: {', '.join(slots['social_functioning'])}")
    if slots.get("self_care_functioning"):
        impairment_domains.append(f"self-care: {', '.join(slots['self_care_functioning'])}")
    if impairment_domains:
        context_parts.append(f"⚠️ Functional impairment: {' | '.join(impairment_domains)}")
    
    # F. Physical/somatic
    if slots.get("physical_symptoms"):
        context_parts.append(f"Physical symptoms: {', '.join(slots['physical_symptoms'])}")
    if slots.get("sleep_quality") or slots.get("sleep_duration"):
        sleep_info = []
        if slots.get("sleep_quality"):
            sleep_info.append(f"quality: {', '.join(slots['sleep_quality'])}")
        if slots.get("sleep_duration"):
            sleep_info.append(f"duration: {', '.join(slots['sleep_duration'])}")
        context_parts.append(f"Sleep: {' | '.join(sleep_info)}")
    if slots.get("energy_level"):
        context_parts.append(f"Energy: {', '.join(slots['energy_level'])}")
    if slots.get("appetite_changes"):
        context_parts.append(f"Appetite: {', '.join(slots['appetite_changes'])}")
    
    # G. Context
    if slots.get("trigger"):
        context_parts.append(f"Triggers: {', '.join(slots['trigger'])}")
    if slots.get("current_stressors"):
        context_parts.append(f"Current stressors: {', '.join(slots['current_stressors'])}")
    if slots.get("recent_life_events"):
        context_parts.append(f"Recent life events: {', '.join(slots['recent_life_events'])}")
    
    # H. Exclusion criteria (CRITICAL)
    exclusion_info = []
    
    substance_any = slots.get("substance_use_any", "unknown")
    if substance_any == "no":
        exclusion_info.append("no substance use")
    elif substance_any == "yes" and slots.get("substance_use"):
        exclusion_info.append(f"substance use: {', '.join(slots['substance_use'])}")
    
    medical_any = slots.get("medical_history_any", "unknown")
    if medical_any == "no":
        exclusion_info.append("no medical conditions")
    elif medical_any == "yes" and slots.get("medical_history"):
        exclusion_info.append(f"medical history: {', '.join(slots['medical_history'])}")
    
    if slots.get("medication_changes"):
        exclusion_info.append(f"medication changes: {', '.join(slots['medication_changes'])}")
    
    if slots.get("caffeine_nicotine_use"):
        exclusion_info.append(f"caffeine/nicotine: {', '.join(slots['caffeine_nicotine_use'])}")
    
    if exclusion_info:
        context_parts.append(f"⚠️ Exclusion criteria: {' | '.join(exclusion_info)}")
    
    # I. Cross-cutting screens (CRITICAL)
    screens = []
    mania = slots.get("mania_like_symptoms", "unknown")
    if mania != "unknown":
        screens.append(f"mania-like: {mania}")
    
    psychosis = slots.get("psychotic_like_symptoms", "unknown")
    if psychosis != "unknown":
        screens.append(f"psychotic-like: {psychosis}")
    
    if screens:
        context_parts.append(f"⚠️ Cross-cutting screens: {' | '.join(screens)}")
    
    # J. Support/coping
    if slots.get("support_system"):
        context_parts.append(f"Support: {', '.join(slots['support_system'])}")
    if slots.get("coping_mechanisms"):
        context_parts.append(f"Coping: {', '.join(slots['coping_mechanisms'])}")
    
    # K. Diagnostic meta-info
    confidence = slots.get("diagnostic_confidence", "low")
    intake_done = slots.get("intake_complete", False)
    context_parts.append(f"Diagnostic confidence: {confidence} | Intake complete: {intake_done}")
    
    if not context_parts:
        return ""

    return "Clinical Context from Intake:\n" + "\n".join(f"- {part}" for part in context_parts)
```

---

## FILE 3: backend/src/rag/workflow/graph_nodes/slot_filling.py

### 3.1. Cập nhật Logic Node với Stage Awareness

```python
async def slot_filling_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Extract structured information (slots) from user input.
    Now follows DSM-5 stage-based intake flow.
    
    Args:
        state: State dict with question, conversation_buffer, slots
    
    Returns:
        Updated state with merged slots, stage info, follow-up questions
    """
    question = state["question"]
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")
    
    # Get existing slots from state
    existing_slots = state.get("slots")
    
    if not existing_slots:
        existing_slots = get_default_slots()
        logger.info("[SLOT FILLING] First turn - initialized default slots")
    else:
        filled_count = len([k for k, v in existing_slots.items() if not is_empty_slot(v)])
        logger.info(f"[SLOT FILLING] Existing slots: {filled_count} filled")
    
    # Determine current stage
    from src.rag.utils.slots import get_current_stage, next_missing_slot
    current_stage = get_current_stage(existing_slots)
    next_stage, next_slot = next_missing_slot(existing_slots)
    
    logger.info(f"[SLOT FILLING] Current stage: {current_stage}")
    if next_slot:
        logger.info(f"[SLOT FILLING] Next required: {next_stage}.{next_slot}")
    
    # Build enhanced context for extraction
    enhanced_question = question
    if conversation_buffer or summary_context:
        context_parts = []
        
        if summary_context:
            context_parts.append(f"Previous summary: {summary_context}")
        
        if conversation_buffer:
            context_parts.append("Recent conversation:")
            for i, pair in enumerate(conversation_buffer[-3:], 1):
                context_parts.append(f"Q{i}: {pair.get('user', '')}")
                context_parts.append(f"A{i}: {pair.get('bot', '')}")
        
        context_parts.append(f"\nCurrent: {question}")
        enhanced_question = "\n".join(context_parts)
    
    # Extract new slots
    result = await process_slot_filling(enhanced_question, existing_slots=existing_slots)
    new_slots = result.get("slots", {})
    
    # Merge with existing
    merged_slots = merge_slots(existing_slots, new_slots)
    result["slots"] = merged_slots
    
    # Update stage info
    current_stage = get_current_stage(merged_slots)
    result["current_stage"] = current_stage
    
    # Check intake completion
    from src.rag.utils.slots import is_intake_complete
    intake_done = is_intake_complete(merged_slots)
    result["intake_complete"] = intake_done
    
    # Check sufficiency (for backward compatibility)
    is_sufficient, required_missing, _ = has_sufficient_slots(merged_slots)
    result["has_sufficient_slots"] = is_sufficient
    result["required_missing_slots"] = required_missing
    
    # Log progress
    filled_count = len([k for k, v in merged_slots.items() if not is_empty_slot(v)])
    logger.info(f"[SLOT FILLING] Merge complete: {filled_count} total filled slots")
    logger.info(f"[SLOT FILLING] Stage: {current_stage} | Intake complete: {intake_done}")
    
    if not intake_done:
        next_stage, next_slot = next_missing_slot(merged_slots)
        logger.info(f"[SLOT FILLING] Next required: {next_stage}.{next_slot}")
    
    # Handle follow-up questions based on stage
    follow_up_questions = result.get("follow_up_questions", [])
    
    if not is_sufficient:
        # Filter to focus on current stage
        logger.info(f"❌ Incomplete required slots. Asking about stage: {next_stage}")
        result["optional_follow_up_questions"] = []
    else:
        # Sufficient - save optional for answer
        logger.info(f"✅ Required slots sufficient for retrieval")
        result["optional_follow_up_questions"] = follow_up_questions
        result["follow_up_questions"] = []
    
    state.update(result)
    return state
```

---

## 📋 CHECKLIST IMPLEMENTATION

### Phase 1: Prompt Update (File 1)
- [ ] Đổi prompt header sang tiếng Anh
- [ ] Cập nhật slot definitions theo 9 groups DSM-5
- [ ] Thêm tri-state field rules
- [ ] Thêm "no/none" → string in list rules
- [ ] Cập nhật examples với English input
- [ ] Cập nhật JSON output schema với tất cả slots mới

### Phase 2: Core Utils Update (File 2)
- [ ] Thêm constants: STAGE_FLOW, DIAGNOSTIC_SLOTS, REQUIRED_SLOTS_BY_STAGE, TRI_STATE_FIELDS
- [ ] Cập nhật get_default_slots() với 30+ slots mới
- [ ] Fix merge_slots():
  - [ ] Không skip "no"/"none"
  - [ ] Handle tri-state fields correctly
  - [ ] Fix severity merge cho list fields
- [ ] Fix validate_duration(): "2 weeks" = specific
- [ ] Thêm is_empty_slot()
- [ ] Thêm next_missing_slot()
- [ ] Thêm is_intake_complete()
- [ ] Thêm get_current_stage()
- [ ] Cập nhật has_sufficient_slots() dùng stage logic
- [ ] Cập nhật build_slot_context() với slots mới
- [ ] Cập nhật get_slot_keywords() (nếu cần)

### Phase 3: Node Update (File 3)
- [ ] Import helpers mới
- [ ] Thêm stage detection logic
- [ ] Log current stage và next required slot
- [ ] Update follow-up filtering theo stage
- [ ] Test với conversation flow

### Phase 4: Testing
- [ ] Test "no" không bị skip: "No substance use" → substance_use = ["no substance use"]
- [ ] Test tri-state: substance_use_any = "no" → không hỏi chi tiết
- [ ] Test duration: "2 weeks" → specific, "lately" → vague
- [ ] Test severity merge: intensity = ["moderate", "severe"] → intensity_current = "severe"
- [ ] Test stage flow: presenting → timeline → severity → functioning → ...
- [ ] Test intake_complete flag

---

## 🔍 TESTING SCENARIOS

### Test Case 1: "No" should be preserved
**Input:** "I don't use any drugs or alcohol"
**Expected:**
```python
substance_use_any = "no"
substance_use = ["no substance use"]
```
**NOT:** `substance_use = []` (empty)

### Test Case 2: Tri-state detail skip
**Input:** Turn 1: "No medical conditions"
**Expected:**
```python
medical_history_any = "no"
medical_history = ["no medical conditions"]
# Next turn: Should NOT ask medical_history details
```

### Test Case 3: Duration specificity
**Input:** "I've been feeling this way for 2 weeks"
**Expected:**
```python
duration = ["2 weeks"]
duration_certainty = "specific"  # NOT "approximate"
```

### Test Case 4: Severity merge
**Turn 1:** intensity = ["moderate"]  
**Turn 2:** intensity = ["severe"]  
**Expected:**
```python
intensity = ["moderate", "severe"]
intensity_current = "severe"  # max severity
```

### Test Case 5: Stage flow
**Turn 1:** presenting_problem filled → current_stage = "timeline"  
**Turn 2:** timeline filled → current_stage = "severity"  
**Turn 3:** ... → current_stage = "complete"

---

## ⚠️ CRITICAL NOTES

### 1. English Input Assumption
- Tất cả prompt giả định input đã được translate sang tiếng Anh
- Slot values lưu bằng tiếng Anh
- Follow-up questions generate bằng tiếng Anh (sẽ được translate ngược sang tiếng Việt ở node khác)

### 2. "No" vs Empty
- `[]` = chưa hỏi
- `["no ..."]` = user trả lời "không"
- KHÔNG BAO GIỜ skip "no" trong merge

### 3. Tri-state Logic
- `substance_use_any = "unknown"` → phải hỏi
- `substance_use_any = "no"` → skip detail, lưu ["no substance use"]
- `substance_use_any = "yes"` → BẮT BUỘC hỏi substance_use details

### 4. Stage Flow
- Phải hỏi đủ theo thứ tự: presenting → timeline → severity → functioning → ...
- KHÔNG cho skip stage (trừ optional slots)
- intake_complete = True chỉ khi TẤT CẢ required slots của TẤT CẢ stages đã filled

### 5. Safety Removed
- Đã loại bỏ tất cả safety slots (suicidal_ideation, etc.) khỏi kịch bản
- Safety được xử lý ở node riêng

---

## 📊 SUMMARY OF CHANGES

| Component | Changes | Impact |
|-----------|---------|--------|
| **Prompt** | English only, 30+ slots, tri-state, "no" preservation | High - core behavior |
| **Slots structure** | 9 DSM-5 groups, stage flow | High - architecture |
| **Merge logic** | Fix "no" skip, tri-state, severity | Critical - data integrity |
| **Validation** | Fix duration, add stage check | Medium - quality |
| **Node logic** | Stage awareness, intake complete | High - flow control |

---

## 🎯 EXPECTED OUTCOMES

Sau khi implement:

1. ✅ Slot filling làm việc hoàn toàn bằng tiếng Anh
2. ✅ "No" responses được preserve, không hỏi lại
3. ✅ Tri-state fields giảm số câu hỏi không cần thiết
4. ✅ Stage flow đảm bảo intake đầy đủ theo DSM-5
5. ✅ Duration "2 weeks" được nhận dạng chính xác
6. ✅ Severity merge hoạt động đúng
7. ✅ Exclusion criteria (substance/medical/meds/caffeine) được check đầy đủ
8. ✅ Cross-cutting screens (mania/psychosis) phát hiện comorbidity

---

**END OF SCENARIO DOCUMENT**
