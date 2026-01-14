# Kịch Bản Implementation - Evaluation Plan

## 📋 Tổng Quan

Kịch bản implementation cho evaluation system sử dụng **RAGAS framework + Custom metrics**, với so sánh **Graph retrieval vs Dense retrieval**.

**Scope**: Đủ cho đồ án, không quá phức tạp

---

## 🏗️ Cấu Trúc Module

```
backend/evaluation/
├── datasets/
│   └── test_queries.jsonl              # Test queries (tạo sau)
├── prompts/
│   ├── completeness_prompt.yaml        # LLM-as-judge prompt cho Completeness
│   └── abstention_prompt.yaml          # LLM-as-judge prompt cho Abstention
├── metrics/
│   ├── chunking_metrics.py             # Custom chunking metrics
│   ├── retrieval_metrics.py            # Recall@K, Precision@K
│   └── answer_metrics.py               # Completeness, Abstention (LLM-as-judge)
├── evaluators/
│   ├── ragas_evaluator.py              # RAGAS metrics wrapper
│   ├── retrieval_comparison.py         # So sánh Graph vs Dense
│   └── end_to_end_evaluator.py         # Full pipeline evaluation
├── utils/
│   ├── dataset_loader.py               # Load test queries
│   └── result_aggregator.py            # Aggregate & format results
├── reports/
│   └── (generated reports)
└── run_evaluation.py                   # Main script
```

**Lưu ý về vị trí files:**
- **Test dataset**: `evaluation/datasets/test_queries.jsonl` (tách biệt với production data ở `data/`)
- **Evaluation prompts**: `evaluation/prompts/*.yaml` (tách biệt với production prompts ở `src/rag/prompts/`)
- **Reports**: `evaluation/reports/` (generated files, không commit vào git)

---

## 📊 Metrics Implementation Plan

### 1️⃣ Chunking Metrics (Custom)

**File**: `metrics/chunking_metrics.py`

**Functions**:
- `semantic_coherence(chunks: List[str]) -> Dict[str, float]`
  - Input: List of chunks (text)
  - Process: Split to sentences → E5 embed → avg cosine similarity
  - Output: Dict {chunk_id: coherence_score}
  
- `boundary_disruption(chunks: List[str]) -> float`
  - Input: List of adjacent chunks
  - Process: Embed last sentence of chunk_i, first sentence of chunk_i+1 → cosine similarity
  - Output: Avg boundary similarity (lower = better boundaries)
  
- `self_retrieval_recall(chunks: List[str], collection_name: str, top_k: int = 5) -> float`
  - Input: Chunks, Milvus collection name, top_k
  - Process: For each chunk, use as query → search Milvus → check if chunk itself in top_k
  - Output: Recall rate (chunks that retrieve themselves)

**Dependencies**: 
- E5 embeddings (đã có sẵn)
- Milvus client (đã có sẵn)

---

### 2️⃣ RAG Core Metrics (RAGAS)

**File**: `evaluators/ragas_evaluator.py`

**Functions**:
- `evaluate_context_recall(query: str, context: str, ground_truth: str) -> float`
  - Wrapper cho RAGAS `context_recall`
  
- `evaluate_faithfulness(query: str, answer: str, context: str) -> float`
  - Wrapper cho RAGAS `faithfulness`
  
- `evaluate_answer_relevance(query: str, answer: str) -> float`
  - Wrapper cho RAGAS `answer_relevancy`

**Dependencies**: 
- `ragas` package (cần install)
- LLM client (Gemini - đã có sẵn) cho RAGAS

**Note**: RAGAS sẽ tự động dùng LLM để evaluate

---

### 3️⃣ Answer Metrics (Custom - LLM-as-judge)

**File**: `metrics/answer_metrics.py`

**Functions**:
- `evaluate_completeness(query: str, answer: str, expected_points: List[str]) -> float`
  - Input: Query, answer, list of expected key points
  - Process: LLM-as-judge prompt → score 1-5
  - Output: Completeness score (1-5)
  - **Prompt template**: (tạo sau)
  
- `evaluate_abstention(query: str, answer: str, has_context: bool) -> bool`
  - Input: Query, answer, flag indicating if context exists
  - Process: LLM-as-judge check if answer says "no information" / "don't know"
  - Output: Boolean (correctly abstained or not)
  - **Prompt template**: (tạo sau)

**Dependencies**: 
- Gemini LLM client (đã có sẵn)

---

### 4️⃣ Retrieval Metrics (Custom)

**File**: `metrics/retrieval_metrics.py`

**Functions**:
- `calculate_recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float`
  - Standard Recall@K calculation
  
- `calculate_precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float`
  - Standard Precision@K calculation

**Usage**: Dùng cho comparison Graph vs Dense retrieval

---

### 5️⃣ System Metrics (Custom - Simple)

**File**: `evaluators/end_to_end_evaluator.py` (include timing/cost)

**Functions**:
- Track latency: `time.time()` before/after pipeline
- Track tokens: Count từ LLM API response

**Note**: Simple implementation, không cần heavy monitoring

---

### 6️⃣ Robustness Metric (Custom)

**File**: `metrics/answer_metrics.py` (có thể thêm function)

**Functions**:
- `evaluate_paraphrase_stability(query: str, paraphrases: List[str], evaluator_func) -> Dict[str, float]`
  - Input: Original query, list of paraphrases, evaluation function (context_recall, answer_relevance)
  - Process: Run evaluator trên original + paraphrases → calculate variance/CV
  - Output: Coefficient of Variation (CV) - lower = more stable

---

## 🔄 Evaluation Flow

### Main Script: `run_evaluation.py`

**Flow**:
```
1. Load test dataset
   ├── Load test_queries.jsonl
   └── Parse queries + ground truth

2. Run Chunking Evaluation (nếu cần)
   ├── Load chunks từ JSONL
   ├── Run semantic_coherence
   ├── Run boundary_disruption
   └── Run self_retrieval_recall

3. Run Retrieval Comparison (Graph vs Dense)
   ├── For each query:
   │   ├── Run Graph retrieval → get context + retrieved IDs
   │   ├── Run Dense retrieval → get context + retrieved IDs
   │   ├── Calculate Recall@K, Precision@K (với ground truth)
   │   └── Store results
   └── Aggregate results

4. Run RAGAS Evaluation (cho cả Graph và Dense)
   ├── For each query + context + answer:
   │   ├── Evaluate Context Recall (RAGAS)
   │   ├── Evaluate Faithfulness (RAGAS)
   │   └── Evaluate Answer Relevance (RAGAS)
   └── Aggregate results

5. Run Custom Answer Metrics
   ├── For each answer:
   │   ├── Evaluate Completeness (LLM-as-judge)
   │   └── Evaluate Abstention (nếu applicable)
   └── Aggregate results

6. Run Robustness Evaluation
   ├── For selected queries:
   │   ├── Generate paraphrases
   │   ├── Run evaluation trên paraphrases
   │   └── Calculate stability (CV)
   └── Aggregate results

7. Run System Metrics
   ├── Track latency per query
   ├── Track token usage per query
   └── Calculate averages

8. Generate Report
   ├── Aggregate all results
   ├── Compare Graph vs Dense
   └── Format output (table, summary)
```

---

## 🔀 Retrieval Comparison Strategy

**File**: `evaluators/retrieval_comparison.py`

**Approach**:
- Run cả Graph retrieval và Dense retrieval trên cùng test queries
- Compare metrics:
  - Retrieval: Recall@K, Precision@K (với ground truth)
  - RAGAS: Context Recall, Faithfulness, Answer Relevance
  - System: Latency, Token usage

**Output format**:
```
Comparison Table:
┌─────────────────────┬──────────────┬──────────────┐
│ Metric              │ Graph        │ Dense        │
├─────────────────────┼──────────────┼──────────────┤
│ Recall@5            │ 0.XX         │ 0.XX         │
│ Precision@5         │ 0.XX         │ 0.XX         │
│ Context Recall      │ 0.XX         │ 0.XX         │
│ Faithfulness        │ 0.XX         │ 0.XX         │
│ Answer Relevance    │ 0.XX         │ 0.XX         │
│ Avg Latency (s)     │ X.XX         │ X.XX         │
│ Avg Tokens          │ XXX          │ XXX          │
└─────────────────────┴──────────────┴──────────────┘
```

---

## 📝 Test Dataset & Prompts

### Test Dataset

**Location**: `backend/evaluation/datasets/test_queries.jsonl`

**File**: `datasets/test_queries.jsonl` (tạo sau, nhưng định nghĩa format)

**Format**:
```json
{
  "query_id": "test_001",
  "query": "Tôi buồn và mệt mỏi suốt 2 tuần",
  "language": "vi",
  "ground_truth": {
    "relevant_chunk_ids": ["chunk_123", "chunk_456"],
    "expected_key_points": ["depression", "2 weeks", "fatigue"]
  },
  "retrieval_type": "both"  // "graph", "dense", or "both"
}
```

**Note**: 
- Ground truth chỉ cần relevant_chunk_ids (cho retrieval metrics)
- Expected_key_points (cho Completeness evaluation)
- Không cần ground truth answer (RAGAS tự evaluate)

---

### LLM-as-Judge Prompts

**Location**: `backend/evaluation/prompts/`

**Files**:
1. `completeness_prompt.yaml` - Prompt để evaluate Completeness (score 1-5)
2. `abstention_prompt.yaml` - Prompt để detect Abstention (correctly says "don't know")

**Format** (YAML, tương tự production prompts):
```yaml
# completeness_prompt.yaml
system: |
  You are evaluating answer completeness...
  
user_template: |
  Query: {query}
  Answer: {answer}
  Expected Key Points: {expected_points}
  
  Rate completeness from 1-5...
```

**Note**: 
- Tách biệt với production prompts (`src/rag/prompts/`)
- Chỉ dùng cho evaluation, không ảnh hưởng production code
- Có thể load tương tự cách load production prompts (YAML loader)

---

## 🔧 Dependencies & Setup

### New Dependencies
```python
# requirements.txt (thêm vào)
ragas>=0.1.0  # RAGAS framework
```

### Existing Dependencies (đã có)
- E5 embeddings (sentence-transformers)
- Milvus client (pymilvus)
- Gemini LLM (google-generativeai)
- Neo4j (neo4j)

---

## 📊 Output Format

### Summary Report Structure

```
# Evaluation Report

## 1. Chunking Metrics
- Semantic Coherence: X.XX (avg)
- Boundary Disruption: X.XX (avg)
- Self-Retrieval Recall: X.XX%

## 2. Retrieval Comparison (Graph vs Dense)
[Comparison Table - như trên]

## 3. RAGAS Metrics (Average)
- Context Recall: X.XX (Graph), X.XX (Dense)
- Faithfulness: X.XX (Graph), X.XX (Dense)
- Answer Relevance: X.XX (Graph), X.XX (Dense)

## 4. Answer Quality
- Completeness: X.XX/5.0 (avg)
- Abstention Correctness: X.XX%

## 5. Robustness
- Paraphrase Stability (CV): X.XX (lower = better)

## 6. System Performance
- Avg Latency: X.XXs (Graph), X.XXs (Dense)
- Avg Tokens: XXX (Graph), XXX (Dense)

## 7. Key Findings
- [Nhận xét ngắn về comparison]
- [Trade-offs]
- [Recommendations]
```

---

## 🎯 Implementation Priority

### Phase 1: Core Setup (1-2 ngày)
1. Setup evaluation module structure
2. Install RAGAS
3. Create dataset loader
4. Test RAGAS integration với 1-2 queries

### Phase 2: Retrieval Comparison (2-3 ngày)
1. Implement retrieval_comparison.py
2. Implement retrieval_metrics.py (Recall@K, Precision@K)
3. Test với test dataset nhỏ

### Phase 3: RAGAS Metrics (1 ngày)
1. Implement ragas_evaluator.py
2. Run evaluation cho cả Graph và Dense
3. Aggregate results

### Phase 4: Custom Metrics (2-3 ngày)
1. Implement chunking_metrics.py
2. Implement answer_metrics.py (Completeness, Abstention)
3. Implement robustness (paraphrase stability)

### Phase 5: System Metrics & Reporting (1-2 ngày)
1. Add latency/token tracking
2. Implement result aggregator
3. Generate report format

**Total estimated time**: 7-11 ngày (tùy experience level)

---

## ⚠️ Lưu Ý Implementation

1. **RAGAS Setup**:
   - Cần LLM API key (Gemini - đã có)
   - RAGAS sẽ gọi LLM để evaluate (có cost)
   - Có thể cache results để tiết kiệm cost

2. **Ground Truth Requirements**:
   - Retrieval metrics: Cần relevant_chunk_ids
   - Context Recall (RAGAS): Cần ground truth answer hoặc expected content
   - Self-Retrieval: Không cần ground truth

3. **LLM-as-judge Prompts**:
   - Completeness prompt (tạo sau)
   - Abstention prompt (tạo sau)
   - Có thể tham khảo RAGAS prompts

4. **Performance Considerations**:
   - RAGAS evaluation có thể chậm (nhiều LLM calls)
   - Nên batch evaluation, không parallel quá nhiều
   - Cache results để tránh re-evaluate

5. **Error Handling**:
   - Handle API failures (Gemini, Milvus)
   - Handle missing ground truth
   - Handle empty retrieval results

---

## 📌 Next Steps

1. ✅ **Kịch bản này** (đã có)
2. ⏳ Tạo test dataset (test_queries.jsonl)
3. ⏳ Tạo LLM-as-judge prompts (Completeness, Abstention)
4. ⏳ Implement code (theo phases trên)
5. ⏳ Run evaluation
6. ⏳ Generate report

---

**Note**: Đây là kịch bản high-level, chi tiết implementation sẽ làm khi code. Focus vào structure và flow, không đi quá sâu vào code details.

