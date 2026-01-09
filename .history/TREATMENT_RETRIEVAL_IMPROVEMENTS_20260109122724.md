# Treatment Retrieval - Cải Tiến Logic với Exact Mapping

## 🎯 Vấn đề cũ

**BEFORE:** LIKE filter không chính xác
```python
expr = 'disease like "%Major Depressive Disorder%"'
```

**Hậu quả:**
- Match nhầm subtypes (Seasonal Depression, Postpartum Depression)
- Không kiểm soát được chính xác chunks nào được retrieve
- Khó debug khi có lỗi

---

## ✨ Giải pháp mới

### **1. Exact Mapping với JSON File**

**File:** `backend/data/raw/treatment_mapping.json`

```json
{
  "Depressive Disorders": [
    "Psychotherapy of Mood Disorders",
    "Pharmacological and Somatic Treatments for Major Depressive Disorder",
    "Brain Stimulation Treatments for Mood Disorders"
  ],
  "Anxiety Disorders": [
    "Cognitive-Behavioral Therapy for Anxiety",
    "Pharmacological Treatment of Anxiety"
  ]
}
```

**Logic:**
1. Detected disease: "Major Depressive Disorder"
2. Map → titles: ["Psychotherapy of Mood Disorders", "Pharmacological...", "Brain Stimulation..."]
3. Milvus filter: `disease in ["title1", "title2", "title3"]`
4. **Exact match only** - không lấy nhầm

### **2. Multi-Disease Support**

```python
disease_list = ["Major Depression", "Persistent Depression"]

# BEFORE: Chỉ retrieve cho disease đầu tiên
target_disease = disease_list[0]

# AFTER: Retrieve cho TẤT CẢ diseases
all_treatment_titles = set()
for disease in disease_list:
    titles = find_treatment_titles(disease, mapping)
    all_treatment_titles.update(titles)
```

**Benefit:** 
- Differential diagnosis → retrieve treatment cho tất cả possibilities
- Comprehensive treatment information

### **3. Fuzzy Matching Strategy**

```python
def find_treatment_titles(disease_name, mapping):
    # Step 1: Exact match (case-insensitive)
    if disease_name.lower() == key.lower():
        return mapping[key]
    
    # Step 2: Partial match (contains)
    if key in disease_name or disease_name in key:
        return mapping[key]
    
    # Step 3: Keyword match (disorder terms)
    # "Major Depressive" matches with "Depressive Disorders"
    if common_keywords(disease_name, key):
        return mapping[key]
```

**Examples:**
- Input: "Major Depressive Disorder" → Match: "Depressive Disorders"
- Input: "GAD" → Match: "Generalized Anxiety Disorder"
- Input: "PTSD" → Match: "Posttraumatic Stress Disorder"

### **4. Dynamic Limit**

```python
# BEFORE: Fixed limit = 5
limit = 5

# AFTER: Adaptive based on number of titles
limit = min(15, max(5, len(all_treatment_titles) * 2))
```

**Logic:**
- 1 title → limit = 5 (enough for single treatment area)
- 3 titles → limit = 6 (cover multiple treatment aspects)
- 5+ titles → limit = 10-15 (comprehensive coverage)

### **5. Caching**

```python
@lru_cache(maxsize=1)
def load_treatment_mapping():
    # Load once, cache in memory
    # Subsequent calls return cached version
    ...
```

**Benefit:** Không load JSON file mỗi request → Faster performance

---

## 📊 Workflow Chi Tiết

### **Step 1: Get Detected Diseases**
```python
disease_list = state.get("disease_detected", [])
# → ["Major Depressive Disorder", "Persistent Depressive Disorder"]
```

### **Step 2: Load Mapping**
```python
mapping = load_treatment_mapping()
# → {
#     "Depressive Disorders": ["Psychotherapy...", "Pharmacological..."],
#     ...
#   }
```

### **Step 3: Map Diseases → Titles**
```python
for disease in disease_list:
    titles = find_treatment_titles(disease, mapping)
    all_treatment_titles.update(titles)

# → all_treatment_titles = {
#     "Psychotherapy of Mood Disorders",
#     "Pharmacological and Somatic Treatments for Major Depressive Disorder",
#     "Brain Stimulation Treatments for Mood Disorders"
#   }
```

### **Step 4: Build Exact Filter**
```python
# Escape quotes
escaped_titles = [title.replace('"', '\\"') for title in all_treatment_titles]

# Build IN expression
title_list_str = ", ".join([f'"{title}"' for title in escaped_titles])
expr = f'disease in [{title_list_str}]'

# → expr = 'disease in ["Psychotherapy of Mood Disorders", "Pharmacological..."]'
```

### **Step 5: Vector Search**
```python
limit = min(15, max(5, len(all_treatment_titles) * 2))

results = col.search(
    data=[query_vector],
    limit=limit,
    expr=expr,  # EXACT match
    output_fields=["node_id", "disease"]
)
```

### **Step 6: Load Full Text**
```python
for hit in results:
    node_id = hit.entity.get("node_id")
    # Load from JSONL file
    text = load_text_by_node_id(node_id)
    treatment_chunks.append(f"[Treatment: {title}]\n{text}")
```

---

## 📈 So Sánh Before/After

### **Case 1: Single Disease**

**Input:** `detected_disease = "Major Depressive Disorder"`

**BEFORE (LIKE filter):**
```python
expr = 'disease like "%Major Depressive Disorder%"'
# Results: 
# ✅ Pharmacological and Somatic Treatments for Major Depressive Disorder
# ✅ Brain Stimulation Treatments for Major Depressive Disorder (partial match?)
# ❌ Seasonal Depression chapters (false positive!)
# ❌ Postpartum Depression chapters (false positive!)
```

**AFTER (Exact mapping):**
```python
titles = ["Psychotherapy of Mood Disorders", 
          "Pharmacological and Somatic Treatments for Major Depressive Disorder",
          "Brain Stimulation Treatments for Mood Disorders"]
expr = 'disease in ["Psychotherapy...", "Pharmacological...", "Brain Stimulation..."]'
# Results:
# ✅ Only exact matches from mapping
# ✅ Controlled, predictable results
# ✅ No false positives
```

### **Case 2: Multiple Diseases (Differential Diagnosis)**

**Input:** `disease_detected = ["Major Depression", "Bipolar II", "Adjustment Disorder"]`

**BEFORE:**
```python
target_disease = disease_detected[0]  # Only "Major Depression"
# Results: Only depression treatment
# ❌ Missing bipolar treatment
# ❌ Missing adjustment disorder treatment
```

**AFTER:**
```python
for disease in disease_detected:
    titles.extend(find_treatment_titles(disease))
# Results:
# ✅ Depression treatment (Psychotherapy, Pharmacological, Brain Stimulation)
# ✅ Bipolar treatment (Psychotherapy of Mood Disorders, Acute and Maintenance...)
# ✅ Adjustment treatment (Adjustment Disorders)
# → Total 7-8 unique treatment chapters
```

### **Case 3: Partial Match**

**Input:** `detected_disease = "GAD"`

**BEFORE:**
```python
expr = 'disease like "%GAD%"'
# Results:
# ❌ Might not match anything (GAD is abbreviation)
# ❌ Or match wrong things like "Sadness", "Gradual onset"
```

**AFTER:**
```python
# Keyword matching: "GAD" → "anxiety" → "Generalized Anxiety Disorder"
titles = ["Generalized Anxiety Disorder"]
expr = 'disease in ["Generalized Anxiety Disorder"]'
# Results:
# ✅ Exact treatment for GAD
```

---

## 🔍 Logging Examples

### **Successful Retrieval:**
```
💊 Retrieving treatment guidance for 2 disease(s): ['Major Depressive Disorder', 'Persistent Depressive Disorder']
✅ Loaded treatment mapping: 48 diseases
📋 Partial match: 'Major Depressive Disorder' → 'Depressive Disorders' → 3 titles
📋 Partial match: 'Persistent Depressive Disorder' → 'Depressive Disorders' → 3 titles
📚 Total unique treatment titles: 3
🔍 Milvus filter: 3 exact titles
   Retrieval limit: 6 chunks
✅ Found 6 treatment records with exact title matching
📊 Retrieved from 3 unique titles:
   • Psychotherapy of Mood Disorders
   • Pharmacological and Somatic Treatments for Major Depressive Disorder
   • Brain Stimulation Treatments for Mood Disorders
✅ Loaded 6 treatment texts
```

### **No Mapping Found:**
```
💊 Retrieving treatment guidance for 1 disease(s): ['Unknown Disorder']
✅ Loaded treatment mapping: 48 diseases
⚠️ No mapping found for disease: 'Unknown Disorder'
⚠️ No treatment titles found for any disease: ['Unknown Disorder']
```

---

## ✅ Advantages

1. **Exact Control:** 
   - Biết chính xác chunks nào sẽ được retrieve
   - Dễ debug và maintain

2. **Multi-Disease Support:**
   - Hỗ trợ differential diagnosis
   - Comprehensive treatment information

3. **Scalable:**
   - Thêm disease mới: Chỉ cần update JSON file
   - Không cần retrain/reindex

4. **Performance:**
   - Cached mapping → Fast lookup
   - Dynamic limit → Không retrieve quá nhiều/ít

5. **Predictable:**
   - Không có false positives từ LIKE filter
   - Kết quả consistent

---

## 🛠️ Maintenance

### **Add New Disease:**
Edit `backend/data/raw/treatment_mapping.json`:
```json
{
  "New Disease Name": [
    "Treatment Chapter Title 1",
    "Treatment Chapter Title 2"
  ]
}
```

### **Update Titles for Existing Disease:**
```json
{
  "Depressive Disorders": [
    "Psychotherapy of Mood Disorders",
    "Pharmacological and Somatic Treatments for Major Depressive Disorder",
    "Brain Stimulation Treatments for Mood Disorders",
    "NEW TREATMENT CHAPTER"  ← Add here
  ]
}
```

### **Verify Titles Match JSONL:**
```bash
# Check available titles in data
grep '"title":' backend/data/raw/mental_health_treatment_guidance.jsonl | sort -u

# Ensure titles in mapping.json match exactly
```

---

## 🎯 Testing

### **Test 1: Single Disease**
```python
state = {"detected_disease": "Major Depressive Disorder"}
result = await treatment_retrieval_node(state)
# Expected: 3-6 chunks from Depression treatment titles
```

### **Test 2: Multiple Diseases**
```python
state = {"disease_detected": ["Panic Disorder", "Social Anxiety Disorder"]}
result = await treatment_retrieval_node(state)
# Expected: Chunks from both Panic and Social Anxiety treatments
```

### **Test 3: Abbreviation**
```python
state = {"detected_disease": "PTSD"}
result = await treatment_retrieval_node(state)
# Expected: Chunks from "Posttraumatic Stress Disorder"
```

### **Test 4: Unknown Disease**
```python
state = {"detected_disease": "Unicorn Syndrome"}
result = await treatment_retrieval_node(state)
# Expected: Empty chunks, warning log
```

---

## 📚 Summary

**Key Changes:**
- ❌ LIKE filter → ✅ Exact IN filter
- ❌ Single disease → ✅ Multi-disease support
- ❌ Fixed limit → ✅ Dynamic limit
- ❌ No mapping → ✅ JSON-based mapping
- ❌ No caching → ✅ LRU cache

**Result:** 
- **Chính xác hơn** (no false positives)
- **Toàn diện hơn** (multi-disease)
- **Nhanh hơn** (caching)
- **Dễ maintain** (JSON file)
