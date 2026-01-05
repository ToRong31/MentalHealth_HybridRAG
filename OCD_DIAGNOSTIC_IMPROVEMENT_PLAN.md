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
- ❌ OCD bị miss vì có stress trigger → classify "normal stress"
- ❌ GAD bị miss vì có life event → classify "adjustment reaction"
- ❌ Depression bị miss vì symptoms overlap với grief/fatigue
- ❌ Panic Disorder bị miss vì physical symptoms → classify "anxiety"
- ❌ **CRITICAL FLAW**: Assessment node acts as gatekeeper, blocks diagnostic investigation

### **Case Studies**

**Case 1: Disorder X missed**
- Triệu chứng: Các triệu chứng đặc trưng của rối loạn
- LLM kết luận: "Stress bình thường"
- Lý do sai: Có trigger → route về normal_stress → BỎ QUA diagnostic

**Case 2: Disorder Y missed**
- Triệu chứng: Các triệu chứng rõ ràng, duration đủ dài
- LLM kết luận: "Phản ứng với áp lực thường"
- Lý do sai: Có life event → score không đủ cao → route về adjustment

**Case 3: Disorder Z missed**
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
Disorder-specific screening modules based on DSM-5/ICD-11 criteria.
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
    
    OBSESSION_KEYWORDS = [
        "ám ảnh", "obsess", "xâm nhập", "intrusive", "không kiểm soát",
        "ý nghĩ lặp lại", "recurring thoughts", "sợ hãi", "contamination",
        "đối xứng", "symmetry", "trật tự", "order"
    ]
    
    COMPULSION_KEYWORDS = [
        "kiểm tra", "checking", "lặp lại", "repeat", "nghi thức", "ritual",
        "phải làm", "must do", "bắt buộc", "compelled", "đếm", "counting",
        "rửa tay", "washing", "sắp xếp", "arranging"
    ]
    
    @staticmethod
    def screen(slots: Dict[str, Any]) -> ScreeningResult:
        """
        Screen for OCD and return likelihood score.
        """
        score = 0.0
        matched_criteria = []
        missing_info = []
        
        # Extract relevant fields
        symptoms = OCDScreener._extract_symptoms(slots)
        duration = slots.get("duration", "")
        impact = slots.get("impact", "")
        compulsion_time = slots.get("compulsion_time_per_day", "")
        has_rituals = slots.get("has_rituals", "")
        anxiety_if_resist = slots.get("anxiety_if_resist", "")
        
        # Criterion A1: Obsessions
        obsession_score = OCDScreener._check_obsessions(symptoms)
        if obsession_score > 0:
            score += obsession_score
            matched_criteria.append(f"Obsessions detected (score: {obsession_score})")
        
        # Criterion A2: Compulsions
        compulsion_score = OCDScreener._check_compulsions(symptoms, has_rituals)
        if compulsion_score > 0:
            score += compulsion_score
            matched_criteria.append(f"Compulsions detected (score: {compulsion_score})")
        
        # Criterion B: Time-consuming or distressing
        time_score = OCDScreener._check_time_impact(compulsion_time, impact)
        if time_score > 0:
            score += time_score
            matched_criteria.append(f"Significant time/impact (score: {time_score})")
        else:
            missing_info.append("compulsion_time_per_day")
        
        # Additional: Anxiety reduction pattern (typical OCD)
        if anxiety_if_resist:
            if any(kw in anxiety_if_resist.lower() for kw in ["tăng", "increase", "worse", "cao hơn"]):
                score += 2.0
                matched_criteria.append("Anxiety increases if resist compulsion (OCD pattern)")
        else:
            missing_info.append("anxiety_if_resist")
        
        # Duration check
        if any(kw in duration.lower() for kw in ["tháng", "months", "năm", "years"]):
            score += 1.0
            matched_criteria.append("Chronic duration")
        
        # Cap score at 10
        score = min(score, 10.0)
        
        # Confidence based on missing info
        confidence = 1.0 - (len(missing_info) * 0.15)
        
        explanation = OCDScreener._generate_explanation(score, matched_criteria, missing_info)
        
        return ScreeningResult(
            disorder=DisorderType.OCD,
            score=score,
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
    def _check_obsessions(symptoms: str) -> float:
        """Check for obsessive thoughts"""
        score = 0.0
        for keyword in OCDScreener.OBSESSION_KEYWORDS:
            if keyword in symptoms:
                score += 0.5
        return min(score, 3.0)  # Max 3 points for obsessions
    
    @staticmethod
    def _check_compulsions(symptoms: str, has_rituals: str) -> float:
        """Check for compulsive behaviors"""
        score = 0.0
        for keyword in OCDScreener.COMPULSION_KEYWORDS:
            if keyword in symptoms:
                score += 0.5
        
        # Rituals strongly suggest compulsions
        if has_rituals and any(kw in has_rituals.lower() for kw in ["có", "yes", "phải"]):
            score += 2.0
        
        return min(score, 4.0)  # Max 4 points for compulsions
    
    @staticmethod
    def _check_time_impact(compulsion_time: str, impact: str) -> float:
        """Check if time-consuming or impactful"""
        score = 0.0
        
        # Check time
        if compulsion_time:
            if any(kw in compulsion_time.lower() for kw in ["giờ", "hour", "nhiều", "much"]):
                score += 2.0
        
        # Check impact
        if any(kw in impact.lower() for kw in ["nặng", "severe", "không thể", "unable"]):
            score += 1.5
        
        return min(score, 3.0)
    
    @staticmethod
    def _generate_explanation(score: float, matched: List[str], missing: List[str]) -> str:
        if score >= 7.0:
            return f"HIGH likelihood of OCD (score: {score:.1f}/10). Matched criteria: {', '.join(matched)}"
        elif score >= 4.0:
            return f"MODERATE likelihood of OCD (score: {score:.1f}/10). Need more info: {', '.join(missing)}"
        else:
            return f"LOW likelihood of OCD (score: {score:.1f}/10)."

# ============================================================================
# GAD SCREENER
# ============================================================================

class GADScreener:
    """
    Screen for Generalized Anxiety Disorder (GAD-7 based + DSM-5).
    
    DSM-5 Criteria:
    A. Excessive worry about multiple topics, most days, ≥6 months
    B. Difficult to control
    C. 3+ associated symptoms (restlessness, fatigue, concentration, 
       irritability, muscle tension, sleep disturbance)
    """
    
    WORRY_KEYWORDS = [
        "lo lắng", "worry", "lo âu", "anxiety", "căng thẳng", "tense",
        "sợ", "fear", "bồn chồn", "restless", "không yên", "nervous"
    ]
    
    @staticmethod
    def screen(slots: Dict[str, Any]) -> ScreeningResult:
        score = 0.0
        matched_criteria = []
        missing_info = []
        
        symptoms_text = GADScreener._extract_symptoms(slots)
        duration = slots.get("duration", "")
        worry_topics = slots.get("worry_topics_count", "")
        uncontrollability = slots.get("uncontrollability", "")
        
        # Criterion A: Excessive worry
        worry_score = GADScreener._check_excessive_worry(symptoms_text, worry_topics)
        if worry_score > 0:
            score += worry_score
            matched_criteria.append(f"Excessive worry detected (score: {worry_score})")
        
        # Duration ≥6 months
        if any(kw in duration.lower() for kw in ["6 tháng", "6 months", "năm", "year"]):
            score += 2.0
            matched_criteria.append("Duration ≥6 months")
        elif any(kw in duration.lower() for kw in ["tháng", "months"]):
            score += 1.0
            matched_criteria.append("Duration several months")
        
        # Criterion B: Difficult to control
        if uncontrollability:
            if any(kw in uncontrollability.lower() for kw in ["khó", "difficult", "không thể", "unable"]):
                score += 2.0
                matched_criteria.append("Worry difficult to control")
        else:
            missing_info.append("uncontrollability")
        
        # Criterion C: Associated symptoms
        associated_score = GADScreener._check_associated_symptoms(slots)
        if associated_score > 0:
            score += associated_score
            matched_criteria.append(f"Associated symptoms (score: {associated_score})")
        
        score = min(score, 10.0)
        confidence = 1.0 - (len(missing_info) * 0.15)
        
        explanation = GADScreener._generate_explanation(score, matched_criteria, missing_info)
        
        return ScreeningResult(
            disorder=DisorderType.GAD,
            score=score,
            confidence=confidence,
            matched_criteria=matched_criteria,
            missing_info=missing_info,
            explanation=explanation
        )
    
    @staticmethod
    def _extract_symptoms(slots: Dict[str, Any]) -> str:
        fields = ["emotion", "primary_symptoms", "trigger", "impact"]
        return " ".join([str(slots.get(f, "")) for f in fields]).lower()
    
    @staticmethod
    def _check_excessive_worry(symptoms: str, worry_topics: str) -> float:
        score = 0.0
        for keyword in GADScreener.WORRY_KEYWORDS:
            if keyword in symptoms:
                score += 0.5
        
        # Multiple worry topics
        if worry_topics:
            if any(kw in worry_topics.lower() for kw in ["nhiều", "multiple", "mọi", "everything"]):
                score += 2.0
        
        return min(score, 4.0)
    
    @staticmethod
    def _check_associated_symptoms(slots: Dict[str, Any]) -> float:
        score = 0.0
        physical = str(slots.get("physical_symptoms", "")).lower()
        
        if any(kw in physical for kw in ["mệt", "fatigue", "tired"]):
            score += 0.5
        if any(kw in physical for kw in ["căng cơ", "muscle", "tension"]):
            score += 0.5
        if any(kw in physical for kw in ["khó ngủ", "insomnia", "sleep"]):
            score += 0.5
        if slots.get("concentration_difficulty"):
            score += 0.5
        
        return min(score, 3.0)
    
    @staticmethod
    def _generate_explanation(score: float, matched: List[str], missing: List[str]) -> str:
        if score >= 7.0:
            return f"HIGH likelihood of GAD (score: {score:.1f}/10). {', '.join(matched)}"
        elif score >= 4.0:
            return f"MODERATE likelihood. Need: {', '.join(missing)}"
        else:
            return f"LOW likelihood of GAD (score: {score:.1f}/10)."

# ============================================================================
# MDD SCREENER
# ============================================================================

class MDDScreener:
    """Screen for Major Depressive Disorder (PHQ-9 based + DSM-5)"""
    
    @staticmethod
    def screen(slots: Dict[str, Any]) -> ScreeningResult:
        score = 0.0
        matched_criteria = []
        missing_info = []
        
        symptoms_text = MDDScreener._extract_symptoms(slots)
        anhedonia = slots.get("anhedonia_severity", "")
        worthlessness = slots.get("worthlessness", "")
        suicidal = slots.get("suicidal_ideation", "")
        
        # Core criterion: Depressed mood OR anhedonia
        if any(kw in symptoms_text for kw in ["buồn", "sad", "depressed", "tuyệt vọng", "hopeless"]):
            score += 2.0
            matched_criteria.append("Depressed mood")
        
        if anhedonia or any(kw in symptoms_text for kw in ["mất hứng", "no interest", "anhedonia"]):
            score += 2.0
            matched_criteria.append("Anhedonia")
        
        # Additional symptoms
        if any(kw in symptoms_text for kw in ["mệt", "fatigue", "năng lượng", "energy"]):
            score += 1.0
            matched_criteria.append("Fatigue")
        
        if any(kw in symptoms_text for kw in ["ngủ", "sleep", "insomnia"]):
            score += 1.0
            matched_criteria.append("Sleep disturbance")
        
        if worthlessness or any(kw in symptoms_text for kw in ["vô giá trị", "worthless", "tự ti", "guilty"]):
            score += 1.5
            matched_criteria.append("Worthlessness/guilt")
        
        if suicidal or any(kw in symptoms_text for kw in ["tự tử", "suicide", "chết", "death"]):
            score += 2.5
            matched_criteria.append("⚠️ Suicidal ideation")
        
        # Duration
        duration = slots.get("duration", "")
        if any(kw in duration for kw in ["tuần", "weeks", "tháng", "months"]):
            score += 1.0
            matched_criteria.append("Duration ≥2 weeks")
        
        score = min(score, 10.0)
        confidence = 0.85  # Depression often has clear symptoms
        
        explanation = MDDScreener._generate_explanation(score, matched_criteria)
        
        return ScreeningResult(
            disorder=DisorderType.MDD,
            score=score,
            confidence=confidence,
            matched_criteria=matched_criteria,
            missing_info=missing_info,
            explanation=explanation
        )
    
    @staticmethod
    def _extract_symptoms(slots: Dict[str, Any]) -> str:
        fields = ["emotion", "primary_symptoms", "physical_symptoms", "impact"]
        return " ".join([str(slots.get(f, "")) for f in fields]).lower()
    
    @staticmethod
    def _generate_explanation(score: float, matched: List[str]) -> str:
        if score >= 7.0:
            return f"HIGH likelihood of MDD (score: {score:.1f}/10). {', '.join(matched)}"
        elif score >= 4.0:
            return f"MODERATE likelihood of depression."
        else:
            return f"LOW likelihood of MDD."

# ============================================================================
# PANIC DISORDER SCREENER
# ============================================================================

class PanicDisorderScreener:
    """Screen for Panic Disorder"""
    
    @staticmethod
    def screen(slots: Dict[str, Any]) -> ScreeningResult:
        score = 0.0
        matched_criteria = []
        missing_info = []
        
        symptoms_text = PanicDisorderScreener._extract_symptoms(slots)
        panic_freq = slots.get("panic_attack_frequency", "")
        fear_of_attacks = slots.get("fear_of_attacks", "")
        
        # Panic attack symptoms (4+ required)
        panic_symptoms = [
            ("tim đập", "heart racing"), ("đổ mồ hôi", "sweating"),
            ("run", "trembling"), ("khó thở", "breathless"),
            ("nghẹt thở", "choking"), ("đau ngực", "chest pain"),
            ("chóng mặt", "dizzy"), ("mất kiểm soát", "losing control"),
            ("sợ chết", "fear of dying")
        ]
        
        panic_count = sum(1 for vn, en in panic_symptoms 
                         if vn in symptoms_text or en in symptoms_text)
        
        if panic_count >= 4:
            score += 3.0
            matched_criteria.append(f"Panic attack symptoms ({panic_count}/13)")
        elif panic_count >= 2:
            score += 1.5
        
        # Recurrent attacks
        if panic_freq or any(kw in symptoms_text for kw in ["lặp lại", "recurring", "nhiều lần"]):
            score += 2.0
            matched_criteria.append("Recurrent panic attacks")
        else:
            missing_info.append("panic_attack_frequency")
        
        # Fear of future attacks
        if fear_of_attacks or any(kw in symptoms_text for kw in ["sợ", "fear", "lo"]):
            score += 2.0
            matched_criteria.append("Fear of future attacks")
        
        # Avoidance
        if any(kw in symptoms_text for kw in ["tránh", "avoid", "không dám"]):
            score += 1.5
            matched_criteria.append("Avoidance behavior")
        
        score = min(score, 10.0)
        confidence = 1.0 - (len(missing_info) * 0.2)
        
        explanation = f"Panic Disorder score: {score:.1f}/10"
        
        return ScreeningResult(
            disorder=DisorderType.PANIC,
            score=score,
            confidence=confidence,
            matched_criteria=matched_criteria,
            missing_info=missing_info,
            explanation=explanation
        )
    
    @staticmethod
    def _extract_symptoms(slots: Dict[str, Any]) -> str:
        fields = ["emotion", "primary_symptoms", "physical_symptoms"]
        return " ".join([str(slots.get(f, "")) for f in fields]).lower()

# ============================================================================
# DISORDER SCREENING ORCHESTRATOR
# ============================================================================

def screen_all_disorders(slots: Dict[str, Any]) -> Dict[DisorderType, ScreeningResult]:
    """
    Run all disorder screeners in parallel and return results.
    
    Returns:
        {DisorderType.OCD: ScreeningResult(...), ...}
    """
    results = {
        DisorderType.OCD: OCDScreener.screen(slots),
        DisorderType.GAD: GADScreener.screen(slots),
        DisorderType.MDD: MDDScreener.screen(slots),
        DisorderType.PANIC: PanicDisorderScreener.screen(slots),
    }
    
    return results

def rank_disorders_by_likelihood(results: Dict[DisorderType, ScreeningResult]) -> List[Tuple[DisorderType, ScreeningResult]]:
    """
    Rank disorders by score (descending).
    """
    return sorted(results.items(), key=lambda x: x[1].score, reverse=True)
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
            # Medical conditions can mimic anxiety/panic
            exclusions[DisorderType.GAD] = "Medical condition (thyroid/heart) should be ruled out first"
            exclusions[DisorderType.PANIC] = "Physical symptoms may be due to medical condition"
        
        if any(kw in substance_use for kw in ["rượu", "alcohol", "ma túy", "drugs", "caffeine"]):
            # Substance-induced symptoms
            for disorder in [DisorderType.GAD, DisorderType.PANIC, DisorderType.MDD]:
                if disorder not in exclusions:
                    exclusions[disorder] = "Substance use present - may explain symptoms"
        
        # Duration exclusions
        duration = slots.get("duration", "")
        if any(kw in duration.lower() for kw in ["ngày", "days", "tuần", "week"]):
            # Too short for most disorders
            exclusions[DisorderType.GAD] = "Duration <6 months (GAD requires ≥6 months)"
            exclusions[DisorderType.MDD] = "Duration may be <2 weeks"
        
        # Recent bereavement (exclude MDD if within 2 months)
        trigger = str(slots.get("trigger", "")).lower()
        recent_events = str(slots.get("recent_life_events", "")).lower()
        if any(kw in trigger + recent_events for kw in ["mất", "death", "qua đời", "funeral"]):
            if any(kw in duration for kw in ["tuần", "weeks", "tháng gần", "recent"]):
                exclusions[DisorderType.MDD] = "Recent bereavement - may be normal grief"
        
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
DISORDER_SPECIFIC_SLOTS = {
    "ocd": [
        "compulsion_time_per_day",      # "Khoảng 2-3 giờ"
        "has_rituals",                  # "Có, phải kiểm tra 5 lần"
        "ritual_description",           # "Phải khóa cửa, mở lại, rồi khóa lại 5 lần"
        "anxiety_if_resist",            # "Rất lo lắng, không yên"
        "obsession_type",               # "contamination/harm/symmetry/hoarding"
        "avoidance_behavior",           # "Tránh chạm vào tay nắm cửa"
        "mental_checking",              # "Có, nhớ lại xem đã khóa chưa"
        "insight_level"                 # "Biết là thái quá nhưng không dừng được"
    ],
    
    "gad": [
        "worry_topics_count",           # "Lo nhiều thứ: công việc, gia đình, sức khỏe..."
        "uncontrollability",            # "Khó kiểm soát"
        "restlessness",                 # "Có, bồn chồn"
        "concentration_difficulty",     # "Khó tập trung"
        "muscle_tension",               # "Căng cơ vai gáy"
        "worry_frequency"               # "Hầu như mỗi ngày"
    ],
    
    "mdd": [
        "anhedonia_severity",           # "Mất hết hứng thú với mọi thứ"
        "worthlessness",                # "Cảm thấy vô giá trị"
        "guilt_feelings",               # "Cảm thấy tội lỗi"
        "suicidal_ideation",            # "Có suy nghĩ không muốn sống"
        "psychomotor_changes",          # "Chậm chạp/bồn chồn"
        "appetite_change",              # "Mất cảm giác đói"
        "weight_change"                 # "Giảm 5kg trong 1 tháng"
    ],
    
    "panic": [
        "panic_attack_frequency",       # "3-4 lần/tuần"
        "panic_attack_duration",        # "Kéo dài 10-15 phút"
        "fear_of_attacks",              # "Rất sợ nó xảy ra lại"
        "physical_symptoms_peak_time",  # "Đạt đỉnh sau 5-10 phút"
        "avoidance_places"              # "Không dám đi chỗ đông người"
    ],
    
    "ptsd": [
        "traumatic_event_description",  # Chi tiết sự kiện
        "intrusive_memories",           # "Liên tục nhớ lại"
        "nightmares",                   # "Ác mộng về sự kiện"
        "flashbacks",                   # "Như đang sống lại"
        "avoidance_triggers",           # "Tránh mọi thứ liên quan"
        "hypervigilance",               # "Luôn cảnh giác"
        "exaggerated_startle"           # "Giật mình với tiếng động nhỏ"
    ]
}

# Update REQUIRED_SLOTS to include exclusion criteria
EXCLUSION_CRITERIA_SLOTS = [
    "medical_conditions_ruled_out",   # "Bác sĩ đã kiểm tra tuyến giáp"
    "substance_use_timeline",         # "Không dùng thuốc/chất kích thích"
    "medication_effects",             # "Không dùng thuốc nào"
    "bereavement_context"             # "Không có mất mát gần đây"
]
```

**2.2 Update slot_filling_prompt.yaml with disorder-specific extraction**
```yaml
# File: backend/src/rag/prompts/slot_filling_prompt.yaml

# Add section:
DISORDER-SPECIFIC INFORMATION EXTRACTION:

If symptoms suggest OCD patterns (repetitive, compulsive, intrusive thoughts):
  → Extract: compulsion_time_per_day, has_rituals, anxiety_if_resist, obsession_type

If symptoms suggest GAD (excessive worry, multiple topics, uncontrollable):
  → Extract: worry_topics_count, uncontrollability, restlessness, concentration_difficulty

If symptoms suggest MDD (depressed mood, anhedonia, worthlessness):
  → Extract: anhedonia_severity, worthlessness, guilt_feelings, suicidal_ideation

If symptoms suggest Panic Disorder (sudden intense fear, physical symptoms):
  → Extract: panic_attack_frequency, fear_of_attacks, physical_symptoms_peak_time

EXCLUSION CRITERIA (ALWAYS ask if not volunteered):
  - "Bác sĩ có kiểm tra các vấn đề y tế (tuyến giáp, tim mạch) chưa?"
  - "Có dùng thuốc, rượu, hoặc chất kích thích không?"
  - "Có sự kiện mất mát/thay đổi lớn gần đây không?"
```

### **Phase 3: Implement Targeted Questions (Week 2-3)**

**3.1 Create targeted_questions_prompt.yaml for each disorder**
```yaml
# File: backend/src/rag/prompts/targeted_questions/ocd_questions.yaml

ocd_targeted_questions:
  time_consumed:
    question_vn: "Mỗi ngày bạn dành khoảng bao nhiêu thời gian cho việc kiểm tra/làm nghi thức này? (ví dụ: 30 phút, 2 giờ...)"
    slot_to_fill: "compulsion_time_per_day"
    criteria: "DSM-5: >1 hour/day"
    
  anxiety_pattern:
    question_vn: "Nếu bạn cố gắng KHÔNG kiểm tra, mức lo lắng của bạn tăng lên thế nào? Và nó có tự giảm sau một thời gian không?"
    slot_to_fill: "anxiety_if_resist"
    criteria: "OCD pattern: Anxiety increases if resist, reduces after compulsion"
    
  rituals:
    question_vn: "Có số lần kiểm tra cụ thể không? Phải kiểm tra đúng cách/đúng trình tự/'đúng cảm giác' nào đó mới có thể thôi được không?"
    slot_to_fill: "has_rituals"
    criteria: "Rigid rituals suggest OCD vs GAD"
    
  mental_checking:
    question_vn: "Ngoài kiểm tra bằng hành động, bạn có 'kiểm tra trong đầu' không? (ví dụ: nhớ lại xem mình đã làm gì, đã làm đúng chưa)"
    slot_to_fill: "mental_checking"
    criteria: "Mental compulsions common in OCD"
    
  insight:
    question_vn: "Khi không ở trong tình huống đó, bạn có nhận ra rằng việc kiểm tra nhiều lần như vậy là 'thái quá' hoặc 'không hợp lý' không?"
    slot_to_fill: "insight_level"
    criteria: "Good insight typical in OCD (vs poor insight in psychosis)"

# Similar files for:
# - gad_questions.yaml
# - mdd_questions.yaml
# - panic_questions.yaml
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

### **Phase 4: Testing & Validation (Week 3-4)**

**Test Cases:**
```yaml
test_cases:
  ocd_case_1:
    symptoms: "Kiểm tra cửa 10 lần, sợ quên khóa"
    expected: OCD score ≥7, asks targeted questions
    
  gad_case_1:
    symptoms: "Lo lắng nhiều thứ, 4 tháng, khó kiểm soát"
    expected: GAD score ≥5, checks duration exclusion
    
  mdd_case_1:
    symptoms: "Buồn, mất hứng thú, mệt mỏi, 3 tuần"
    expected: MDD score ≥6, asks about bereavement
    
  normal_stress_case_1:
    symptoms: "Stress công việc 1 tuần, lo lắng nhẹ"
    expected: All scores <4, routes to normal_coping after screening
    
  false_positive_prevention:
    symptoms: "Lo lắng vì thi, 2 ngày"
    expected: All scores <3, exclusion: duration too short
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
- OCD detection rate: ≥85% (current: ~0%)
- GAD detection rate: ≥85%
- MDD detection rate: ≥85%
- Panic Disorder detection rate: ≥80%

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
- Test with 20 simulated cases per disorder
- Include edge cases: comorbidities, subclinical, normal stress

**3. A/B Testing (if feasible)**
- 50% traffic to new system, 50% to old
- Compare accuracy, user satisfaction, conversation length

**4. Expert Review**
- Clinical psychologist reviews 30 random diagnoses
- Check against DSM-5 criteria
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
| **Disorder coverage** | Generic "disorder" | OCD/GAD/MDD/Panic/PTSD specific |
| **False negatives** | High (OCD, GAD missed) | Low (systematic screening) |
| **False positives** | Low (conservative) | Moderate (needs tuning) |
| **Transparency** | Opaque scoring | Explicit criteria, confidence scores |
| **Comorbidity** | Not detected | Detected (parallel screening) |
| **Subclinical** | Forced to normal/disorder | Explicit subclinical category |

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

**5. Integration with Wearables**
- Heart rate, sleep data to inform panic/anxiety screening
- Activity levels for depression screening

---

## 📚 REFERENCES & RESOURCES

**Clinical Guidelines:**
- DSM-5 (Diagnostic and Statistical Manual of Mental Disorders, 5th Edition)
- ICD-11 (International Classification of Diseases, 11th Revision)
- NICE Guidelines (National Institute for Health and Care Excellence)

**Screening Tools:**
- Y-BOCS (Yale-Brown Obsessive Compulsive Scale) for OCD
- GAD-7 (Generalized Anxiety Disorder 7-item scale)
- PHQ-9 (Patient Health Questionnaire-9) for Depression
- PDSS (Panic Disorder Severity Scale)

**Differential Diagnosis:**
- "Differential Diagnosis in Psychiatry" by Oyewumi & Vollick
- "The Clinical Interview" by Sommers-Flanagan & Sommers-Flanagan

---

## ✅ APPROVAL CHECKLIST

Before implementation, ensure:

- [ ] Team reviewed and approved architecture changes
- [ ] Clinical advisor reviewed diagnostic criteria
- [ ] Test cases prepared (20+ per disorder)
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
3. Prioritize: Phase 1 (critical) vs Phase 2-3 (enhancements)

**This Week:**
1. Implement Phase 1 (remove premature routing)
2. Write unit tests for severity_only_assessment()
3. Test with 10 OCD cases

**Next Week:**
1. Implement disorder screeners (OCD, GAD, MDD)
2. Add targeted questions for OCD
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
