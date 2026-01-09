# Phân Tích Treatment Retrieval - Logic và Cơ Chế Hoạt Động

## 📊 Tổng quan Architecture

Treatment retrieval sử dụng **Hybrid approach** kết hợp:
1. **Vector Search** (semantic similarity)
2. **Metadata Filtering** (disease field)
3. **Text Loading** (từ JSONL files)

---

## 🔄 Workflow Chi Tiết

### **Phase 1: Trigger Conditions**

Treatment retrieval được kích hoạt khi:
- `detected_disease` có giá trị (từ disease_conclusion_node)
- Hoặc `disease_detected` list không rỗng
- User xác nhận muốn biết cách điều trị (`wants_treatment = True`)

**Routing logic:**
```python
# workflow.py line ~75
if awaiting_treatment and wants_treatment:
    return "treatment_retrieval"
```

### **Phase 2: Data Retrieval Process**

#### **Step 1: Get Target Disease**
```python
# Ưu tiên disease_detected list (danh sách các bệnh có thể)
disease_list = state.get("disease_detected", [])
if not disease_list:
    # Fallback sang detected_disease (chẩn đoán chính)
    detected_disease = state.get("detected_disease", "")
    disease_list = [detected_disease] if detected_disease else []

# Lấy bệnh đầu tiên (most recent/confident)
target_disease = disease_list[0]
```

**Ví dụ:**
- `disease_detected = ["Major Depressive Disorder", "Persistent Depressive Disorder"]`
- → `target_disease = "Major Depressive Disorder"`

#### **Step 2: Query Preparation**
```python
# Lấy rewritten_query (đã được optimize) hoặc fallback
query = state.get("rewritten_query", 
                  state.get("question", f"Cách điều trị {target_disease}"))

# Encode query thành vector embedding
encoded_query = encode_e5([f"query: {query}"])
query_vector = encoded_query[0].tolist()  # 1024 dimensions
```

**Key point:** Sử dụng **E5-large-v2** model để tạo embedding
- Prefix: `"query: "` (theo E5 best practice)
- Output: Vector 1024 chiều
- Metric: COSINE similarity

#### **Step 3: Milvus Vector Search với Disease Filter**

```python
# Build filter expression - hỗ trợ multiple diseases
disease_filters = []
for disease in disease_list[:3]:  # Top 3 diseases
    disease_escaped = disease.replace('"', '\\"').replace("'", "\\'")
    disease_filters.append(f'disease like "%{disease_escaped}%"')

expr = " or ".join(disease_filters)
# → expr = 'disease like "%Major Depressive Disorder%" or disease like "%Persistent Depressive Disorder%"'
```

**Search parameters:**
```python
search_params = {
    "metric_type": "COSINE",  # Cosine similarity
    "params": {"ef": 64}      # HNSW parameter
}

results = col.search(
    data=[query_vector],
    anns_field="embedding",
    param=search_params,
    limit=5,                  # Top 5 chunks
    expr=expr,                # Disease filter
    output_fields=["node_id", "disease"]
)
```

**Cơ chế:**
1. **Vector search** tìm 5 chunks gần nhất về semantic (COSINE)
2. **Filter trước** bằng disease metadata → Chỉ search trong các chunks có disease match
3. Kết quả: Top 5 chunks relevant nhất VÀ có disease đúng

#### **Step 4: Load Full Text từ JSONL**

Milvus chỉ lưu **embeddings + metadata**, text đầy đủ được lưu trong JSONL:

```python
file_path = Path("data/raw/mental_health_treatment_guidance.jsonl")
node_id_set = {hit.entity.get("node_id") for hit in hits}

# Đọc từng line, match node_id
for line in file:
    item = json.loads(line)
    chunk_id = int(item.get("chunk_id", -1))
    if chunk_id in node_id_set:
        text = item.get("text", "").strip()
        disease = item.get("disease", "")
        treatment_chunks.append(f"[Disease: {disease}]\n{text}")
```

**Output:**
```python
state["treatment_chunks"] = [
    "[Disease: Major Depressive Disorder]\nSSRIs are first-line treatment...",
    "[Disease: Major Depressive Disorder]\nCBT has shown efficacy...",
    ...
]
state["treatment_node_ids"] = [3127, 3145, ...]
```

---

## 📝 Phase 3: Answer Generation

### **Input cho LLM:**

```yaml
system: |
  Bạn là chuyên gia tâm lý lâm sàng...
  
user: |
  Bệnh được chẩn đoán: {detected_disease}
  
  Thông tin từ slot filling:
  {slots}  # Toàn bộ slots (emotion, duration, trigger, etc.)
  
  Lịch sử hội thoại:
  {conversation_history}  # Last 5 messages
  
  Tóm tắt ngữ cảnh:
  {summary}  # Conversation summary
  
  Kiến thức điều trị:
  {treatment_chunks}  # 5 retrieved chunks
```

### **LLM Output Structure:**

LLM được yêu cầu tạo câu trả lời theo cấu trúc:
1. **Giải thích ngắn** về tình trạng
2. **Phương pháp điều trị cụ thể** (từ treatment_chunks)
3. **Lời khuyên thực hành** hàng ngày
4. **Khuyến khích và động viên**

---

## 🔍 Ưu Điểm của Logic Hiện Tại

### ✅ **1. Hybrid Search - Best of Both Worlds**
- **Vector similarity:** Tìm chunks semantically relevant với query
- **Disease filter:** Đảm bảo chỉ retrieve disease đúng
- **Ví dụ:** 
  - Query: "thuốc điều trị trầm cảm"
  - Filter: `disease like "%Depression%"`
  - → Chỉ retrieve SSRIs/CBT cho Depression, không lẫn với Anxiety treatment

### ✅ **2. Multi-Disease Support**
```python
disease_list = ["Major Depression", "Persistent Depression", "Adjustment Disorder"]
# Filter: disease like "%Major Depression%" OR disease like "%Persistent Depression%" OR ...
```
- Hỗ trợ differential diagnosis
- Có thể retrieve treatment cho nhiều bệnh nếu cần

### ✅ **3. Context-Aware Answer**
LLM nhận đủ context:
- Slots: Biết severity, duration, impact → Personalize treatment
- Conversation history: Hiểu user's concerns
- Summary: Long-term context

### ✅ **4. Separation of Concerns**
- **Milvus:** Fast vector search + metadata filter
- **JSONL:** Full text storage (dễ update, không cần reindex)
- **LLM:** Synthesis + personalization

---

## ⚠️ Hạn Chế và Vấn Đề

### ❌ **1. Single Disease Priority**
```python
target_disease = disease_list[0]  # Chỉ dùng disease đầu tiên!
```

**Vấn đề:**
- Nếu có 3 possible diseases, chỉ retrieve treatment cho bệnh đầu tiên
- Mất thông tin về differential treatment

**Ví dụ:**
- `disease_detected = ["GAD", "Panic Disorder", "Social Anxiety"]`
- Chỉ retrieve cho GAD → Mất treatment info cho Panic & Social Anxiety

### ❌ **2. LIKE Filter Không Chính Xác**

```python
expr = 'disease like "%Major Depressive Disorder%"'
```

**Vấn đề:**
- LIKE với `%...%` có thể match sai:
  - Query: "Depression"
  - Match: "**Depression**", "Seasonal **Depression**", "Postpartum **Depression**"
  - Có thể lấy nhầm treatment cho subtypes

**Giải pháp tốt hơn:**
```python
# Option 1: Exact match
expr = 'disease == "Major Depressive Disorder"'

# Option 2: Startswith
expr = 'disease like "Major Depressive Disorder%"'

# Option 3: Multiple exact conditions
expr = 'disease in ["Major Depressive Disorder", "MDD", "Depression"]'
```

### ❌ **3. Fixed Limit = 5 Chunks**

```python
limit=5  # Hardcoded
```

**Vấn đề:**
- 5 chunks có thể không đủ cho treatment phức tạp (e.g., Bipolar)
- Hoặc quá nhiều cho simple conditions (e.g., Adjustment Disorder)

**Dynamic limit dựa trên:**
- Disease complexity
- Severity level
- User's specific questions

### ❌ **4. No Reranking After Retrieval**

**Flow hiện tại:**
```
Milvus search (COSINE) → Top 5 → Load text → Send to LLM
```

**Thiếu:**
- Cross-encoder reranking
- MMR (Maximal Marginal Relevance) để giảm redundancy
- Query-specific relevance filtering

**Ví dụ vấn đề:**
- User hỏi: "thuốc cho trầm cảm có an toàn không?"
- Retrieved chunks:
  1. SSRIs mechanism (relevant: HIGH)
  2. SSRIs side effects (relevant: HIGH)
  3. SSRIs dosing (relevant: MEDIUM)
  4. CBT for depression (relevant: LOW - user hỏi về thuốc!)
  5. Depression statistics (relevant: LOW)

→ Chunk 4 & 5 noise, nên filter out

### ❌ **5. Không Phân Biệt Treatment Types**

Treatment có nhiều loại:
- **Pharmacological** (thuốc)
- **Psychotherapy** (CBT, DBT, etc.)
- **Lifestyle** (exercise, sleep hygiene)
- **Emergency** (crisis intervention)

**Vấn đề:** Retrieve tất cả lẫn lộn, không có organization

**User cần:**
- "thuốc gì cho trầm cảm?" → Chỉ pharmacological
- "liệu pháp tâm lý nào tốt?" → Chỉ psychotherapy

### ❌ **6. No Severity-Aware Retrieval**

```python
slots = {"intensity": "severe", "work_school_impact": "unable to work"}
```

**Hiện tại:** Retrieve treatment chung chung (mild + moderate + severe)

**Nên có:**
- Mild depression → Self-help, therapy first
- Moderate → Therapy + consider medication
- Severe → Medication + intensive therapy + monitoring

---

## 📈 Schema Hiện Tại

### **Milvus Collection: mental_health_treatment_guidance**

```python
fields = [
    FieldSchema(name="node_id", dtype=INT64, is_primary=True),
    FieldSchema(name="embedding", dtype=FLOAT_VECTOR, dim=1024),
    FieldSchema(name="disease", dtype=VARCHAR, max_length=512)
]

index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 8, "efConstruction": 64}
}
```

### **JSONL Structure:**

```json
{
  "chunk_id": "3127",
  "title": "Pharmacological and Somatic Treatments for Major Depressive Disorder",
  "text": "SSRIs with an FDA-approved indication for MDD are fluoxetine, sertraline...",
  "disease": "Major Depressive Disorder"
}
```

**Mapping:**
- `chunk_id` → `node_id` (Milvus)
- `title` → `disease` (Milvus metadata)
- `text` → Embedded thành vector 1024D

---

## 💡 Đề Xuất Cải Tiến

### **1. Multi-Disease Retrieval**
```python
# Instead of:
target_disease = disease_list[0]

# Use all detected diseases:
for disease in disease_list[:3]:
    retrieve_and_merge_treatment(disease)
```

### **2. Treatment Type Classification**
Thêm metadata field:
```python
FieldSchema(name="treatment_type", dtype=VARCHAR, 
            # Values: "pharmacological", "psychotherapy", "lifestyle", "emergency"
)
```

Query-specific filter:
```python
if "thuốc" in query or "medication" in query:
    expr += ' and treatment_type == "pharmacological"'
```

### **3. Severity-Aware Retrieval**
Thêm metadata:
```python
FieldSchema(name="severity_level", dtype=VARCHAR,
            # Values: "mild", "moderate", "severe", "crisis"
)
```

Adaptive filtering:
```python
severity = slots.get("intensity", "moderate")
expr += f' and severity_level in ["{severity}", "all"]'
```

### **4. Reranking Pipeline**
```python
# After Milvus retrieval
hits = col.search(...)  # Top 10

# Cross-encoder reranking
from sentence_transformers import CrossEncoder
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
scores = reranker.predict([(query, chunk) for chunk in hits])

# Filter by threshold + sort
filtered = [chunk for chunk, score in zip(hits, scores) if score > 0.5]
filtered = sorted(filtered, key=lambda x: x.score, reverse=True)[:5]
```

### **5. Dynamic Limit**
```python
complexity_map = {
    "Adjustment Disorder": 3,
    "Major Depressive Disorder": 5,
    "Bipolar Disorder": 8,
    "Schizophrenia": 10
}

limit = complexity_map.get(target_disease, 5)
```

---

## 🎯 Summary

**Điểm mạnh:**
✅ Hybrid search (vector + metadata)
✅ Context-aware answer generation
✅ Clean separation of concerns

**Điểm yếu:**
❌ Single disease retrieval only
❌ LIKE filter không chính xác
❌ No reranking
❌ Không phân biệt treatment types
❌ Không adaptive theo severity

**Priority fixes:**
1. **Multi-disease retrieval** (high impact, low effort)
2. **Exact disease matching** (high impact, low effort)
3. **Reranking pipeline** (medium impact, medium effort)
4. **Treatment type metadata** (high impact, high effort - requires reingestion)
