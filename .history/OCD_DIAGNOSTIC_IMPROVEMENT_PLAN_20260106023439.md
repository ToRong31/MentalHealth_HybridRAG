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
    OCD = "ocd"
    GAD = "gad"
    MDD = "major_depressive_disorder"
    PANIC = "panic_disorder"
    PTSD = "ptsd"
    SOCIAL_ANXIETY = "social_anxiety_disorder"
    SPECIFIC_PHOBIA = "specific_phobia"

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
# OCD SCREENER
# ============================================================================

class OCDScreener:
    """
    Screen for Obsessive-Compulsive Disorder based on DSM-5 criteria.
    
    DSM-5 Criteria (simplified):
    A. Obsessions and/or compulsions
    B. Time-consuming (>1 hour/day) OR significant distress/impairment
    C. Not due to substances or medical condition
    D. Not better explained by another mental disorder
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
