# Slot Filling System Redesign - DSM-5 Aligned

## Overview
Redesigning slot filling system to align with DSM-5 diagnostic criteria, working with English input (post-translation), and enforcing structured intake flow.

## Key Changes

### 1. DSM-5 Alignment
The system now follows DSM-5's core diagnostic pillars:
- **Symptoms & Severity**: What + how severe
- **Timeline/Course**: Onset, duration, frequency, pattern
- **Distress/Impairment**: Subjective distress + objective functioning
- **Exclusion**: Substance/medical/medication + context

### 2. Slot Reorganization

#### New Slot Groups (9 stages):
1. **Presenting** - Chief complaint and emotions
2. **Timeline** - Onset, duration, frequency, fluctuation
3. **Severity** - Intensity, distress, stress levels
4. **Functioning** - Daily, work/school, social, self-care impairment
5. **Somatic** - Physical symptoms, sleep, energy, appetite
6. **Context** - Triggers, stressors, life events
7. **Exclusion** - Substance, medical, medication, caffeine
8. **Support/Coping** - Support system, coping mechanisms
9. **Screens** - Mania-like, psychotic-like symptoms (cross-cutting)

### 3. New Slots Added

**Presenting:**
- `presenting_problem` - One-sentence chief complaint

**Timeline:**
- `onset` - When symptoms started
- `frequency` - How often (daily, weekly, episodes)
- `time_of_day_pattern` - When symptoms are worst (optional)

**Severity:**
- `distress_level` - Subjective distress (0-10 or mild/moderate/severe)

**Functioning:**
- `social_functioning` - Impact on relationships/social activities
- `self_care_functioning` - Impact on eating, hygiene, self-care

**Exclusion:**
- `substance_use_any` - Tri-state: yes/no/unknown (gateway)
- `medical_history_any` - Tri-state: yes/no/unknown (gateway)
- `medication_changes` - Recent medication changes
- `caffeine_nicotine_use` - Caffeine/nicotine consumption

**Screens:**
- `mania_like_symptoms` - Tri-state screen for mania
- `psychotic_like_symptoms` - Tri-state screen for psychosis

### 4. Critical Bug Fixes

#### A. No/None Handling
**Problem**: "no" answers were skipped, causing repeated questions
**Solution**: Only skip `None`, empty string, or empty list. Store "no" as text in list

#### B. Severity Merge Not Working
**Problem**: Severity fields are lists, but "max wins" logic only ran for scalars
**Solution**: Add `_current` derived fields computed from list using max severity

#### C. Duration Validation
**Problem**: "2 weeks" marked as "approximate" instead of "specific"
**Solution**: Check for number + time unit FIRST before checking vague/approximate terms

#### D. Stage-Based Flow
**Problem**: Random question order, no systematic intake
**Solution**: Implement `STAGE_FLOW` + `next_missing_slot()` to enforce order

### 5. Required Slots by Stage

```python
REQUIRED_SLOTS_BY_STAGE = {
    "presenting": ["presenting_problem", "emotion", "primary_mood"],
    "timeline": ["onset", "duration", "frequency", "symptom_fluctuation"],
    "severity": ["intensity", "distress_level", "stress_level"],
    "functioning": ["daily_functioning", "work_school_impact", "social_functioning", "self_care_functioning"],
    "context": ["trigger", "current_stressors", "recent_life_events"],
    "exclusion": ["substance_use_any", "medical_history_any", "medication_changes", "caffeine_nicotine_use"],
    "support_coping": ["support_system", "coping_mechanisms", "coping_effectiveness", "need"],
    "screens": ["mania_like_symptoms", "psychotic_like_symptoms"]
}
```

### 6. Implementation Changes

#### Files Modified:
1. **slots.py** - Core slot logic, merge, validation, stage flow
2. **slot_filling_prompt.yaml** - Updated prompt for English input + new slots
3. **slot_filling.py** - Node wrapper with stage-based flow

#### Key Functions Added:
- `is_empty_slot()` - Unified empty check for tri-state + lists
- `next_missing_slot()` - Find next required slot in stage order
- `is_intake_complete()` - Check if all required slots filled
- `max_severity()` - Compute max severity from list

#### Key Functions Modified:
- `get_default_slots()` - Added new slots with correct types
- `merge_slots()` - Fixed no/none handling + severity derivation
- `validate_duration()` - Fixed number+unit detection
- `has_sufficient_slots()` - Use stage-based checking

### 7. Exclusion Notes (Removed)
- All safety-related slots removed (handled by separate safety_check node)
- Safety gate logic removed from slot filling

### 8. English Input Adaptation
- Prompt updated to work with English input (post-translation)
- All extraction happens in English
- Vietnamese follow-up questions removed (handled by response node)

## Migration Notes

### Backward Compatibility
- Old slots preserved in structure (no breaking changes)
- New slots have sensible defaults
- Existing conversations will gradually fill new slots

### Testing Priority
1. Test "no/none" preservation (substance_use_any, medical_history_any)
2. Test stage flow enforcement (should ask in order)
3. Test duration validation ("2 weeks" = specific)
4. Test severity merge (intensity_current derived correctly)
5. Test intake completion detection

## Usage Example

```python
# Turn 1
new_slots = {"emotion": ["anxious"], "duration": ["lately"]}
merged = merge_slots(existing={}, new_slots=new_slots)
stage, missing = next_missing_slot(merged)
# Result: stage="presenting", missing="presenting_problem"

# Turn 2
new_slots = {"presenting_problem": ["I've been having trouble sleeping"]}
merged = merge_slots(existing=merged, new_slots=new_slots)
stage, missing = next_missing_slot(merged)
# Result: stage="presenting", missing="primary_mood"

# ... continues through all stages

# Final turn
is_complete = is_intake_complete(merged)
# Result: True -> handoff to diagnosis node
```

## Timeline
- **Phase 1** (Current): Implement core changes to slots.py
- **Phase 2**: Update prompt for English + new slots
- **Phase 3**: Update node wrapper with stage flow
- **Phase 4**: Test + validation
