# Kế Hoạch Cải Thiện Hệ Thống Chẩn Đoán

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
- ❌ **Nhiều rối loạn bị bỏ sót** vì có stress trigger → classify "normal stress"
- ❌ **False negatives** khi có life event → classify "adjustment reaction"
- ❌ **Pattern recognition bị skip** do premature routing
- ❌ **CRITICAL FLAW**: Assessment node acts as gatekeeper, blocks diagnostic investigation

### **Case Studies**

**Case 1: Rối loạn A bị bỏ sót**
- Triệu chứng: Các triệu chứng đặc trưng của rối loạn
- LLM kết luận: "Stress bình thường"
- Lý do sai: Có trigger → route về normal_stress → BỎ QUA diagnostic

**Case 2: Rối loạn B bị bỏ sót**
- Triệu chứng: Các triệu chứng rõ ràng, duration đủ dài
- LLM kết luận: "Phản ứng với áp lực thường"
- Lý do sai: Có life event → score không đủ cao → route về adjustment

**Case 3: Rối loạn C bị bỏ sót**
- Triệu chứng: Nhiều triệu chứng core, ảnh hưởng chức năng
- LLM kết luận: "Cảm xúc bình thường do sự kiện sống"
- Lý do sai: Có life event → classify adjustment reaction → không check criteria chẩn đoán

**Case 4: Normal stress FALSE POSITIVE**
- Triệu chứng: Stress ngắn hạn, triệu chứng nhẹ
- LLM kết luận: "Rối loạn có khả năng cao"
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
1. **Score thresholds arbitrary**: Các rối loạn khác nhau có patterns khác nhau
2. **Life event bias**: Có stressor → assume adjustment, không check co-morbidity
3. **No disorder-specific criteria**: Chỉ dựa vào generic scores

### **3. Missing Differential Diagnosis Framework**

**Không có module:**
- ❌ Disorder-specific criteria checking (clinical guidelines)
- ❌ Differential diagnosis logic (phân biệt các rối loạn tương tự)
- ❌ Exclusion criteria checking (medical conditions, substances)
- ❌ Severity spectrum (subclinical → clinical threshold)

**Thiếu slots cho differential diagnosis:**
```yaml
# Disorder-specific criterion slots
- Các slots đặc trưng cho từng rối loạn (time patterns, specific behaviors, cognitive patterns)
- Severity indicators cho các triệu chứng chính
- Functional impairment details
- Pattern characteristics

# Common exclusion criteria
- medical_conditions_ruled_out, substance_use_timeline, medication_effects
- bereavement_context, trauma_history, developmental_context
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
│  │ Type A  │ Type B  │  Type C  │  Type D  │  Type E...  │     │
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
│  2. Check diagnostic thresholds (≥ 7/10 for clinical level)    │
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
- ✅ Screen for multiple disorder types simultaneously
- ✅ Detect co-morbidities

**3. THRESHOLD-BASED ROUTING**
- ❌ Don't use arbitrary total scores
- ✅ Each disorder type has specific threshold (based on clinical criteria)
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

### **Module 1: Disorder Screening Engine**

**File mới:** `backend/src/rag/diagnosis/disorder_screeners.py`

```python
"""
Disorder-specific screening modules based on clinical criteria.
Each screener returns a score 0-10 indicating likelihood.
"""

from typing import Dict, Any, List, Tuple
from enum import Enum

class DisorderType(Enum):
    """Enum for different disorder categories.
    Actual disorder types defined in configuration."""
    # Disorder types loaded from config/disorder_definitions.yaml
    pass

class ScreeningResult:
    def __init__(self, disorder: DisorderType, score: float, 
                 confidence: float, matched_criteria: List[str],
                 missing_info: List[str], explanation: str):
        self.disorder = disorder
        self.score = score  # 0-10
        self.confidence = confidence  # 0-1
        self.matched_criteria = matched_criteria
        self.missing_info = missing_info
        self.explanation = explanation
    
    def is_above_threshold(self, threshold: float = 7.0) -> bool:
        """Check if score suggests clinical significance"""
        return self.score >= threshold

# ============================================================================
# BASE DISORDER SCREENER (Example Template)
# ============================================================================

class BaseDisorderScreener:
    """
    Base template for disorder-specific screeners.
    
    Each screener implements:
    - Keyword/pattern matching for characteristic symptoms
    - Criteria checking based on clinical guidelines
    - Scoring algorithm (0-10 scale)
    - Missing information detection
    """
    
    CHARACTERISTIC_KEYWORDS = []  # Override in subclasses
    CHARACTERISTIC_PATTERNS = []  # Override in subclasses
    
    @staticmethod
    def screen(slots: Dict[str, Any]) -> ScreeningResult:
        """
        Screen for disorder and return likelihood score.
        Override this method in each specific screener.
        """
        score = 0.0
        matched_criteria = []
        missing_info = []
        
        # Extract relevant fields
        symptoms = BaseDisorderScreener._extract_symptoms(slots)
        duration = slots.get("duration", "")
        impact = slots.get("impact", "")
        
        # Criterion checking logic here
        # Each disorder implements its own specific criteria
        
        # Calculate confidence based on missing info
        confidence = 1.0 - (len(missing_info) * 0.15)
        
        explanation = BaseDisorderScreener._generate_explanation(score, matched_criteria, missing_info)
        
        return ScreeningResult(
            disorder=DisorderType.EXAMPLE,  # Replace with specific type
            score=min(score, 10.0),
            confidence=confidence,
            matched_criteria=matched_criteria,
            missing_info=missing_info,
            explanation=explanation
        )
    
    @staticmethod
    def _extract_symptoms(slots: Dict[str, Any]) -> str:
        """Combine all symptom fields into single text"""
        fields = ["emotion", "primary_symptoms", "physical_symptoms", 
                 "trigger", "impact", "daily_functioning"]
        text = " ".join([str(slots.get(f, "")) for f in fields])
        return text.lower()
    
    @staticmethod
    def _check_core_criteria(symptoms: str, keywords: List[str]) -> float:
        """Check for core diagnostic criteria"""
        score = 0.0
        for keyword in keywords:
            if keyword in symptoms:
                score += 0.5
        return score
    
    @staticmethod
    def _generate_explanation(score: float, matched: List[str], missing: List[str]) -> str:
        if score >= 7.0:
            return f"HIGH likelihood (score: {score:.1f}/10). Matched criteria: {', '.join(matched)}"
        elif score >= 4.0:
            return f"MODERATE likelihood (score: {score:.1f}/10). Need more info: {', '.join(missing)}"
        else:
            return f"LOW likelihood (score: {score:.1f}/10)."

# ============================================================================
# DISORDER SCREENING ORCHESTRATOR
# ============================================================================

def screen_all_disorders(slots: Dict[str, Any]) -> Dict[DisorderType, ScreeningResult]:
    """
    Run all disorder screeners in parallel and return results.
    
    Returns:
        {DisorderType.TYPE_A: ScreeningResult(...), ...}
    """
    # Load all registered screeners from config
    screeners = load_screeners_from_config()
    
    results = {}
    for disorder_type, screener_class in screeners.items():
        results[disorder_type] = screener_class.screen(slots)
    
    return results

def rank_disorders_by_likelihood(results: Dict[DisorderType, ScreeningResult]) -> List[Tuple[DisorderType, ScreeningResult]]:
    """
    Rank disorders by score (descending).
    """
    return sorted(results.items(), key=lambda x: x[1].score, reverse=True)

def load_screeners_from_config():
    """
    Load disorder screeners from configuration file.
    Allows adding new disorders without code changes.
    """
    # Implementation: Load from YAML config
    pass
```

### **Module 2: Differential Diagnosis Engine**

**File mới:** `backend/src/rag/diagnosis/differential_engine.py`

```python
"""
Differential diagnosis engine - combines screening results with clinical logic.
"""

from typing import Dict, List, Tuple, Optional
from .disorder_screeners import DisorderType, ScreeningResult, screen_all_disorders, rank_disorders_by_likelihood

class DiagnosisDecision:
    """Final diagnosis output"""
    def __init__(self, primary_disorder: Optional[DisorderType], 
                 confidence: float, explanation: str,
                 comorbidities: List[DisorderType],
                 is_subclinical: bool,
                 requires_targeted_questions: List[str],
                 exclusions_applied: List[str]):
        self.primary_disorder = primary_disorder
        self.confidence = confidence
        self.explanation = explanation
        self.comorbidities = comorbidities
        self.is_subclinical = is_subclinical
        self.requires_targeted_questions = requires_targeted_questions
        self.exclusions_applied = exclusions_applied
    
    def is_normal_response(self) -> bool:
        """Check if this is a normal stress response (not a disorder)"""
        return self.primary_disorder is None and not self.is_subclinical

class DifferentialEngine:
    """
    Apply clinical logic to screening results.
    """
    
    # Thresholds for diagnosis
    THRESHOLD_HIGHLY_LIKELY = 7.0
    THRESHOLD_POSSIBLE = 4.0
    THRESHOLD_SUBCLINICAL = 2.0
    
    @staticmethod
    def diagnose(slots: Dict[str, Any]) -> DiagnosisDecision:
        """
        Main differential diagnosis function.
        
        Steps:
        1. Screen for all disorders
        2. Rank by scores
        3. Apply exclusion criteria
        4. Determine if above clinical threshold
        5. Identify comorbidities
        6. Decide if need targeted questions
        """
        
        # Step 1: Screen all disorders
        screening_results = screen_all_disorders(slots)
        
        # Step 2: Rank
        ranked = rank_disorders_by_likelihood(screening_results)
        
        # Step 3: Apply exclusions
        exclusions = DifferentialEngine._apply_exclusion_criteria(slots, ranked)
        
        # Filter out excluded disorders
        valid_candidates = [(d, r) for d, r in ranked if d not in exclusions]
        
        if not valid_candidates:
            return DiagnosisDecision(
                primary_disorder=None,
                confidence=0.9,
                explanation="No disorder detected. Symptoms consistent with normal stress response.",
                comorbidities=[],
                is_subclinical=False,
                requires_targeted_questions=[],
                exclusions_applied=[f"{d.value}: {reason}" for d, reason in exclusions.items()]
            )
        
        # Step 4: Check top candidate
        top_disorder, top_result = valid_candidates[0]
        
        if top_result.score >= DifferentialEngine.THRESHOLD_HIGHLY_LIKELY:
            # High confidence - likely disorder
            confidence = min(top_result.confidence, 0.85)
            
            # Check for comorbidities
            comorbid = [d for d, r in valid_candidates[1:] 
                       if r.score >= DifferentialEngine.THRESHOLD_POSSIBLE]
            
            # Check if need more targeted questions
            targeted_qs = top_result.missing_info if top_result.confidence < 0.8 else []
            
            return DiagnosisDecision(
                primary_disorder=top_disorder,
                confidence=confidence,
                explanation=top_result.explanation,
                comorbidities=comorbid,
                is_subclinical=False,
                requires_targeted_questions=targeted_qs,
                exclusions_applied=[f"{d.value}: {r}" for d, r in exclusions.items()]
            )
        
        elif top_result.score >= DifferentialEngine.THRESHOLD_POSSIBLE:
            # Moderate - need targeted questions to confirm
            return DiagnosisDecision(
                primary_disorder=top_disorder,
                confidence=0.5,
                explanation=f"Possible {top_disorder.value}. Need more information to confirm.",
                comorbidities=[],
                is_subclinical=False,
                requires_targeted_questions=top_result.missing_info,
                exclusions_applied=[]
            )
        
        elif top_result.score >= DifferentialEngine.THRESHOLD_SUBCLINICAL:
            # Subclinical - symptoms present but below threshold
            return DiagnosisDecision(
                primary_disorder=None,
                confidence=0.7,
                explanation=f"Subclinical {top_disorder.value} symptoms. Monitoring recommended.",
                comorbidities=[],
                is_subclinical=True,
                requires_targeted_questions=[],
                exclusions_applied=[]
            )
        
        else:
            # Below threshold - normal response
            return DiagnosisDecision(
                primary_disorder=None,
                confidence=0.85,
                explanation="Symptoms do not meet clinical threshold for any disorder. Likely normal stress response.",
                comorbidities=[],
                is_subclinical=False,
                requires_targeted_questions=[],
                exclusions_applied=[]
            )
    
    @staticmethod
    def _apply_exclusion_criteria(slots: Dict[str, Any], 
                                  ranked: List[Tuple[DisorderType, ScreeningResult]]) -> Dict[DisorderType, str]:
        """
        Apply exclusion criteria to rule out disorders.
        
        Returns:
            {DisorderType: "reason for exclusion"}
        """
        exclusions = {}
        
        # Medical condition exclusions
        medical_history = str(slots.get("medical_history", "")).lower()
        substance_use = str(slots.get("substance_use", "")).lower()
        
        if any(kw in medical_history for kw in ["tuyến giáp", "thyroid", "tim", "heart"]):
            # Medical conditions can mimic various disorders
            for disorder, _ in ranked:
                exclusions[disorder] = "Medical condition should be ruled out first"
        
        if any(kw in substance_use for kw in ["rượu", "alcohol", "ma túy", "drugs", "caffeine"]):
            # Substance-induced symptoms
            for disorder, _ in ranked:
                if disorder not in exclusions:
                    exclusions[disorder] = "Substance use present - may explain symptoms"
        
        # Duration exclusions
        duration = slots.get("duration", "")
        if any(kw in duration.lower() for kw in ["ngày", "days"]):
            # Too short for most disorders
            for disorder, _ in ranked:
                if disorder not in exclusions:
                    exclusions[disorder] = "Duration too short (most disorders require ≥2 weeks)"
        
        # Recent bereavement
        trigger = str(slots.get("trigger", "")).lower()
        recent_events = str(slots.get("recent_life_events", "")).lower()
        if any(kw in trigger + recent_events for kw in ["mất", "death", "qua đời", "funeral"]):
            if any(kw in duration for kw in ["tuần", "weeks", "tháng gần", "recent"]):
                for disorder, _ in ranked:
                    if disorder not in exclusions:
                        exclusions[disorder] = "Recent bereavement - may be normal grief"
        
        return exclusions
```

---

## 📝 IMPLEMENTATION ROADMAP

### **Phase 1: Remove Premature Routing (Week 1) - CRITICAL**

**Objective:** Eliminate normal_coping bypass, force all cases through diagnostic flow.

**Changes:**

**1.1 Update workflow.py**
```python
# File: backend/src/rag/workflow/workflow.py

# OLD (DELETE THIS):
def route_after_assessment(state: KGState) -> str:
    category = state.get("assessment_category")
    if category == "normal_stress":
        return "normal_coping_retrieval"  # ❌ DELETE
    if category == "adjustment_reaction":
        return "adjustment_retrieval"  # ❌ DELETE
    return "query_rewriter"

# NEW (REPLACE WITH THIS):
def route_after_severity_assessment(state: KGState) -> str:
    """
    ALL cases go through diagnostic screening.
    Severity only determines priority/urgency.
    """
    severity = state.get("severity_level", "moderate")
    
    # Log for monitoring
    logger.info(f"[ROUTING] Severity: {severity} → ALWAYS go to diagnostic_screening")
    
    # Set crisis flag if severe
    if severity == "crisis":
        state["requires_urgent_referral"] = True
    
    # ALWAYS route to diagnostic screening
    return "diagnostic_screening"
```

**1.2 Update assessment.py**
```python
# File: backend/src/rag/utils/assessment.py

# REMOVE assess_disorder_likelihood() - it's making premature decisions
# REPLACE with severity_only_assessment()

def assess_severity_only(slots: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Assess SEVERITY only, NOT disorder vs normal.
    
    Returns:
        (severity_level, severity_breakdown)
        
    Levels:
        - mild: Minimal impairment, symptoms present but manageable
        - moderate: Noticeable impairment, affecting daily life
        - severe: Significant impairment, major life disruption
        - crisis: Immediate risk (suicidal, psychotic, unable to function)
    """
    
    # Factors for severity
    duration_score = parse_duration_score(slots.get("duration", ""))
    impact_score = assess_functional_impairment(slots)
    intensity = slots.get("intensity", "medium")
    risk_level = slots.get("risk_level", "")
    
    # Crisis detection (immediate risk)
    if any(kw in str(slots).lower() for kw in ["tự tử", "suicide", "tự hại", "self-harm"]):
        return ("crisis", {"reason": "Suicidal ideation detected", "requires_emergency": True})
    
    if risk_level == "high" or "cao" in risk_level.lower():
        return ("crisis", {"reason": "High risk level reported"})
    
    # Severe: Major impairment
    if impact_score >= 7 and duration_score >= 2:
        return ("severe", {
            "impact_score": impact_score,
            "duration_score": duration_score,
            "explanation": "Significant functional impairment + chronic duration"
        })
    
    # Moderate: Noticeable impairment
    if impact_score >= 4 or duration_score >= 1:
        return ("moderate", {
            "impact_score": impact_score,
            "duration_score": duration_score
        })
    
    # Mild: Minimal impairment
    return ("mild", {"impact_score": impact_score, "duration_score": duration_score})

def assess_functional_impairment(slots: Dict[str, Any]) -> float:
    """
    Score functional impairment 0-10 based on multiple domains.
    """
    score = 0.0
    
    functional_impact = str(slots.get("functional_impairment", "")).lower()
    work_impact = str(slots.get("work_school_impact", "")).lower()
    relationship_impact = str(slots.get("relationship_impact", "")).lower()
    
    # Work/school domain
    if any(kw in work_impact for kw in ["không thể", "unable", "nghỉ", "quit"]):
        score += 3.0
    elif any(kw in work_impact for kw in ["khó khăn", "difficult", "ảnh hưởng", "affect"]):
        score += 1.5
    
    # Relationship domain
    if any(kw in relationship_impact for kw in ["tránh", "avoid", "cô lập", "isolate"]):
        score += 2.0
    elif any(kw in relationship_impact for kw in ["căng thẳng", "tension", "xung đột", "conflict"]):
        score += 1.0
    
    # Self-care domain
    if any(kw in functional_impact for kw in ["không chăm", "neglect", "vệ sinh", "hygiene"]):
        score += 2.0
    
    # Sleep domain
    if any(kw in str(slots).lower() for kw in ["khó ngủ", "insomnia", "mất ngủ"]):
        score += 1.0
    
    return min(score, 10.0)
```

**1.3 Create diagnostic_screening_node**
```python
# File: backend/src/rag/workflow/graph_nodes/diagnostic_screening.py

from src.rag.diagnosis.disorder_screeners import screen_all_disorders, rank_disorders_by_likelihood
from src.rag.diagnosis.differential_engine import DifferentialEngine

async def diagnostic_screening_node(state: KGState) -> KGState:
    """
    Screen for all disorders systematically.
    This node ALWAYS runs - no bypassing.
    """
    logger.info("[DIAGNOSTIC SCREENING] Starting universal disorder screening...")
    
    slots = state.get("slots", {})
    
    # Run differential diagnosis
    diagnosis_decision = DifferentialEngine.diagnose(slots)
    
    # Store results in state
    state["diagnosis_decision"] = {
        "primary_disorder": diagnosis_decision.primary_disorder.value if diagnosis_decision.primary_disorder else None,
        "confidence": diagnosis_decision.confidence,
        "explanation": diagnosis_decision.explanation,
        "comorbidities": [d.value for d in diagnosis_decision.comorbidities],
        "is_subclinical": diagnosis_decision.is_subclinical,
        "is_normal": diagnosis_decision.is_normal_response(),
        "requires_targeted_questions": diagnosis_decision.requires_targeted_questions,
        "exclusions_applied": diagnosis_decision.exclusions_applied
    }
    
    logger.info(f"[DIAGNOSIS] Primary: {diagnosis_decision.primary_disorder}, "
               f"Confidence: {diagnosis_decision.confidence:.2f}, "
               f"Normal: {diagnosis_decision.is_normal_response()}")
    
    return state

def route_after_diagnostic_screening(state: KGState) -> str:
    """
    Route based on diagnostic results.
    """
    diagnosis = state.get("diagnosis_decision", {})
    
    # Check if need targeted questions
    if diagnosis.get("requires_targeted_questions"):
        logger.info("[ROUTING] Need targeted questions → targeted_questions_node")
        return "targeted_questions"
    
    # Check if disorder detected
    if diagnosis.get("primary_disorder"):
        logger.info(f"[ROUTING] Disorder detected: {diagnosis['primary_disorder']} → diagnostic_retrieval")
        return "diagnostic_retrieval"
    
    # Subclinical - monitoring recommended
    if diagnosis.get("is_subclinical"):
        logger.info("[ROUTING] Subclinical → monitoring_advice")
        return "monitoring_advice"
    
    # Normal response
    logger.info("[ROUTING] Normal response → normal_coping_retrieval")
    return "normal_coping_retrieval"
```

**1.4 Update workflow graph**
```python
# File: backend/src/rag/workflow/workflow.py

workflow = StateGraph(KGState)

# ... (existing nodes)

# CHANGE: assessment node now only does severity
workflow.add_node("assessment", assessment_node)  # Now returns severity only

# NEW: All cases go through diagnostic screening
workflow.add_node("diagnostic_screening", diagnostic_screening_node)

# NEW: Targeted questions node
workflow.add_node("targeted_questions", targeted_questions_node)

# NEW: Monitoring advice for subclinical
workflow.add_node("monitoring_advice", monitoring_advice_node)

# ... (existing retrieval nodes)

# ROUTING CHANGES:
workflow.add_conditional_edges(
    "assessment",
    route_after_severity_assessment,
    {
        "diagnostic_screening": "diagnostic_screening"  # ALWAYS go here
    }
)

workflow.add_conditional_edges(
    "diagnostic_screening",
    route_after_diagnostic_screening,
    {
        "targeted_questions": "targeted_questions",
        "diagnostic_retrieval": "diagnostic_retrieval",
        "monitoring_advice": "monitoring_advice",
        "normal_coping_retrieval": "normal_coping_retrieval"
    }
)
```

### **Phase 2: Add Disorder-Specific Slots (Week 2)**

**2.1 Expand slots.py with comprehensive disorder-specific slots**
```python
# File: backend/src/rag/utils/slots.py

# DIFFERENTIAL DIAGNOSIS SLOTS (add to existing)
# Load from config/disorder_specific_slots.yaml for flexibility

DISORDER_SPECIFIC_SLOTS_CONFIG = "config/disorder_specific_slots.yaml"

# Example structure in YAML:
"""
disorder_types:
  type_a:
    - slot_1
    - slot_2
    - slot_3
  
  type_b:
    - slot_4
    - slot_5
    - slot_6
    
  # ... more disorder types
  
common_exclusion_criteria:
  - medical_conditions_ruled_out
  - substance_use_timeline
  - medication_effects
  - bereavement_context
  - trauma_history
"""

def load_disorder_specific_slots():
    """Load disorder-specific slots from configuration"""
    with open(DISORDER_SPECIFIC_SLOTS_CONFIG) as f:
        return yaml.safe_load(f)
```

**2.2 Update slot_filling_prompt.yaml with disorder-specific extraction**
```yaml
# File: backend/src/rag/prompts/slot_filling_prompt.yaml

# Add section:
DISORDER-SPECIFIC INFORMATION EXTRACTION:

Based on symptom patterns detected, extract relevant disorder-specific information:

Pattern Type A indicators (repetitive behaviors, intrusive thoughts):
  → Extract relevant time/frequency/pattern slots

Pattern Type B indicators (excessive worry, multiple domains, uncontrollability):
  → Extract worry characteristics and control difficulty

Pattern Type C indicators (mood, anhedonia, worthlessness):
  → Extract mood changes and cognitive symptoms

Pattern Type D indicators (sudden onset, physical symptoms, fear):
  → Extract attack characteristics and avoidance

EXCLUSION CRITERIA (ALWAYS ask if not volunteered):
  - "Bác sĩ có kiểm tra các vấn đề y tế chưa?"
  - "Có dùng thuốc, rượu, hoặc chất kích thích không?"
  - "Có sự kiện mất mát/thay đổi lớn gần đây không?"
```

### **Phase 3: Implement Targeted Questions (Week 2-3)**

**3.1 Create targeted_questions_prompt.yaml template**
```yaml
# File: backend/src/rag/prompts/targeted_questions_template.yaml

targeted_questions_template:
  time_pattern:
    question_vn: "Mỗi ngày bạn dành khoảng bao nhiêu thời gian cho [behavior]?"
    slot_to_fill: "time_spent_per_day"
    criteria: "Clinical threshold check"
    
  frequency:
    question_vn: "Tần suất [symptom] xảy ra như thế nào?"
    slot_to_fill: "symptom_frequency"
    criteria: "Frequency assessment"
    
  impact_verification:
    question_vn: "[Symptom] ảnh hưởng cụ thể thế nào đến: công việc, quan hệ, giấc ngủ?"
    slot_to_fill: "specific_impact_domains"
    criteria: "Functional impairment verification"
```

**3.2 Create targeted_questions_node**
```python
# File: backend/src/rag/workflow/graph_nodes/targeted_questions.py

async def targeted_questions_node(state: KGState) -> KGState:
    """
    Ask disorder-specific questions to confirm/refute diagnosis.
    """
    diagnosis = state.get("diagnosis_decision", {})
    primary_disorder = diagnosis.get("primary_disorder")
    missing_info = diagnosis.get("requires_targeted_questions", [])
    
    if not missing_info:
        return state
    
    # Load disorder-specific questions
    questions_map = load_targeted_questions(primary_disorder)
    
    # Generate questions for missing slots
    questions_to_ask = []
    for slot_name in missing_info:
        if slot_name in questions_map:
            questions_to_ask.append(questions_map[slot_name]["question_vn"])
    
    # Store in state for chatbot to ask
    state["targeted_questions_pending"] = questions_to_ask
    state["awaiting_user_response"] = True
    
    logger.info(f"[TARGETED Q] Need to ask {len(questions_to_ask)} questions for {primary_disorder}")
    
    return state
```

### **Phase 4: Configuration-Driven Disorder Definitions (Week 3)**

**4.1 Create disorder_definitions.yaml**
```yaml
# File: backend/config/disorder_definitions.yaml

disorders:
  type_a:
    name: "Disorder Type A"
    screener_class: "TypeAScreener"
    keywords:
      - "keyword1"
      - "keyword2"
    patterns:
      - "pattern1.*pattern2"
    clinical_threshold: 7.0
    targeted_questions:
      - "question_slot_1"
      - "question_slot_2"
  
  type_b:
    name: "Disorder Type B"
    screener_class: "TypeBScreener"
    keywords:
      - "keyword3"
      - "keyword4"
    patterns:
      - "pattern3.*pattern4"
    clinical_threshold: 7.0
    targeted_questions:
      - "question_slot_3"
      - "question_slot_4"
  
  # ... more disorders
```

### **Phase 5: Testing & Validation (Week 3-4)**

**Test Cases:**
```yaml
test_cases:
  disorder_a_case:
    symptoms: "Characteristic symptoms for disorder A"
    expected: Score ≥7, asks targeted questions
    
  disorder_b_case:
    symptoms: "Characteristic symptoms for disorder B"
    expected: Score ≥5, checks duration exclusion
    
  disorder_c_case:
    symptoms: "Core symptoms with functional impact"
    expected: Score ≥6, asks about exclusion criteria
    
  normal_stress_case:
    symptoms: "Brief stress with mild symptoms"
    expected: All scores <4, routes to normal_coping after screening
    
  false_positive_prevention:
    symptoms: "Similar keywords but different context"
    expected: All scores <3, exclusion criteria applied
```

**Metrics to track:**
- True positive rate (TPR) per disorder: ≥85%
- False positive rate (FPR): ≤15%
- Average questions to diagnosis: ≤12 turns
- User satisfaction: ≥4/5

---

## 🎯 SUCCESS METRICS & VALIDATION

### **Accuracy Targets**

**Per-Disorder Detection:**
- Detection rate for all disorder types: ≥85% (current: varies, some ~0%)

**False Positive Control:**
- Overall FPR: ≤15%
- Normal stress correctly identified: ≥80%
- Subclinical cases identified (not over-diagnosed): ≥70%

**User Experience:**
- Average questions to diagnosis: ≤15 turns
- Average conversation time: ≤10 minutes
- User satisfaction with accuracy: ≥4/5
- Clarity of explanation: ≥4/5

### **Validation Strategy**

**1. Retrospective Case Review**
- Review 50+ past conversations where diagnosis was missed
- Re-run with new system, measure improvement

**2. Prospective Testing**
- Test with 20 simulated cases per disorder type
- Include edge cases: comorbidities, subclinical, normal stress

**3. A/B Testing (if feasible)**
- 50% traffic to new system, 50% to old
- Compare accuracy, user satisfaction, conversation length

**4. Expert Review**
- Clinical expert reviews 30 random diagnoses
- Check against clinical criteria
- Flag any major errors

---

## ⚠️ RISKS & MITIGATION

### **Risk 1: All cases go through diagnostic → increased latency/cost**

**Mitigation:**
- Screening uses simple keyword/pattern matching (fast)
- Only high-scoring disorders trigger targeted questions
- Cache screening results to avoid re-computation
- **Trade-off accepted**: Accuracy > Speed for mental health

### **Risk 2: False positives increase (over-diagnosing)**

**Mitigation:**
- Set conservative thresholds (score ≥7 for "likely")
- Apply exclusion criteria systematically
- Require multiple criteria matches, not single symptoms
- Output "subclinical" instead of forcing diagnosis
- **Transparency**: Explain reasoning, confidence scores

### **Risk 3: User frustrated with more questions**

**Mitigation:**
- Only ask targeted questions for high-scoring disorders
- Explain WHY asking: "Để xác định rõ hơn, tôi cần hỏi thêm..."
- Limit to 3-5 targeted questions max
- **Context**: Users prefer accuracy over speed for mental health

### **Risk 4: Increased complexity → more bugs**

**Mitigation:**
- Modular design: screeners, differential engine, targeted questions
- Unit tests for each screener (test with known cases)
- Integration tests for full workflow
- Extensive logging for debugging
- **Phased rollout**: Test Phase 1 before Phase 2

### **Risk 5: Screeners miss atypical presentations**

**Mitigation:**
- Start with conservative keywords, iterate based on misses
- Add "other symptoms" free-text field
- Manual review of uncertain cases (confidence <0.5)
- **Continuous improvement**: Update patterns monthly

---

## 📊 COMPARISON: OLD vs NEW ARCHITECTURE

| Aspect | OLD System | NEW System |
|--------|-----------|------------|
| **Routing** | Binary: normal vs disorder | Universal screening → threshold-based |
| **Assessment** | Score → category → route | Severity + Screening → differential |
| **Stressor handling** | Stressor → assume normal | Stressor ≠ exclusion, check comorbidity |
| **Disorder coverage** | Generic "disorder" | Multiple specific disorder types |
| **False negatives** | High (many disorders missed) | Low (systematic screening) |
| **False positives** | Low (conservative) | Moderate (needs tuning) |
| **Transparency** | Opaque scoring | Explicit criteria, confidence scores |
| **Comorbidity** | Not detected | Detected (parallel screening) |
| **Subclinical** | Forced to normal/disorder | Explicit subclinical category |
| **Extensibility** | Hard-coded logic | Configuration-driven (easy to add disorders) |

---

## 🔄 ROLLBACK PLAN

If new system performs worse:

**Phase 1 Rollback:**
```python
# Revert workflow.py routing
def route_after_assessment(state: KGState) -> str:
    # Restore old binary routing
    category = state.get("assessment_category")
    if category == "normal_stress":
        return "normal_coping_retrieval"
    # ...
```

**Data to monitor for rollback decision:**
- False positive rate >25% (vs target ≤15%)
- User satisfaction drops below 3/5
- Average conversation time >15 minutes
- System errors/crashes

**Rollback triggers:**
- Any critical bug affecting >10% of users
- Clinical expert flags dangerous misdiagnosis
- User complaints spike

---

## 💡 FUTURE ENHANCEMENTS (Post-MVP)

**1. Machine Learning Screeners**
- Train ML models on past conversations + ground truth
- Replace keyword-based screeners with ML predictions
- Requires labeled dataset (200+ cases per disorder)

**2. Personalized Thresholds**
- Adjust thresholds based on user demographics, history
- Example: Lower threshold for users with family history

**3. Multi-language Support**
- Currently Vietnamese/English keywords
- Expand to other languages with localized patterns

**4. Real-time Learning**
- Learn from expert corrections
- Auto-update patterns when screener consistently wrong

**5. Integration with Clinical Tools**
- Standardized screening scales integration
- Severity tracking over time

---

## 📚 REFERENCES & RESOURCES

**Clinical Guidelines:**
- International clinical diagnostic manuals
- Evidence-based practice guidelines
- Peer-reviewed diagnostic criteria

**Screening Tools:**
- Validated screening questionnaires
- Standardized assessment scales
- Clinical interview protocols

**Differential Diagnosis:**
- Clinical decision-making frameworks
- Diagnostic reasoning literature
- Evidence-based differential diagnosis methods

---

## ✅ APPROVAL CHECKLIST

Before implementation, ensure:

- [ ] Team reviewed and approved architecture changes
- [ ] Clinical advisor reviewed diagnostic criteria
- [ ] Test cases prepared (20+ per disorder type)
- [ ] Rollback plan documented and tested
- [ ] Monitoring dashboard ready
- [ ] User communication prepared (if user-facing changes)
- [ ] Code review completed
- [ ] Unit tests written (≥80% coverage)
- [ ] Integration tests passing
- [ ] Documentation updated

---

## 📞 NEXT ACTIONS

**Immediate (Today):**
1. Review this proposal with team
2. Get clinical advisor feedback on screening criteria
3. Prioritize: Phase 1 (critical) vs Phase 2-5 (enhancements)

**This Week:**
1. Implement Phase 1 (remove premature routing)
2. Write unit tests for severity_only_assessment()
3. Test with historical missed cases

**Next Week:**
1. Implement disorder screeners from config
2. Add targeted questions framework
3. Integration testing

**Week 3-4:**
1. Full system testing with 100+ test cases
2. A/B testing if feasible
3. Tune thresholds based on results
4. Deploy to production with monitoring

---

**Document Status:** ✅ READY FOR REVIEW  
**Last Updated:** 2026-01-06  
**Author:** GitHub Copilot (AI Assistant)  
**Reviewers Needed:** Backend team, Clinical advisor, Product owner
