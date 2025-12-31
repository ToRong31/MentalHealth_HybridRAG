┌─────────────────────────────────────────────────────────────────────────────┐
│                         MENTAL HEALTH HYBRID RAG WORKFLOW                   │
└─────────────────────────────────────────────────────────────────────────────┘

                                    [START]
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │ translate_question   │  ← Phát hiện ngôn ngữ (VI/EN)
                            │ (Detect Language)    │    Dịch sang EN nếu cần
                            └──────────────────────┘
                                       │
                                       ▼
                            ┌──────────────────────────┐
                            │ query_similarity_check   │  ← Check tương tự với
                            │ (Embedding Similarity)   │    conversation context
                            └──────────────────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        │                             │
            [similarity < 0.8]            [similarity >= 0.8 OR no buffer]
                        │                             │
                        ▼                             │
            ┌───────────────────┐                     │
            │  classify_query   │  ← LLM phân loại    │
            │ (LLM Classifier)  │    query type       │
            └───────────────────┘                     │
                        │                             │
                        └──────────────┬──────────────┘
                                       ▼
                              ┌─────────────────┐
                              │  safety_check   │  ← Kiểm tra:
                              │ (Safety Filter) │    • Mental health related?
                              └─────────────────┘    • High-risk?
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
         [high-risk]          [not mental health]      [safe & relevant]
              │                        │                        │
              ▼                        ▼                        ▼
    ┌──────────────────┐    ┌────────────────────┐    ┌─────────────────┐
    │ crisis_response  │    │ not_mental_health  │    │  slot_filling   │ ← Extract slots:
    │ (Crisis Support) │    │  (Out of Scope)    │    │ (Info Extract)  │   • emotion, mood
    └──────────────────┘    └────────────────────┘    └─────────────────┘   • trigger, duration
              │                        │                        │           • intensity, impact
              ▼                        ▼                        │
           [END]                    [END]                       │
                                                        ┌───────┴────────┐
                                                        │                │
                                              [slots sufficient]  [slots insufficient]
                                                        │                │
                                                        ▼                ▼
                                            ┌──────────────────┐  ┌────────────────────┐
                                            │ query_rewriter   │  │ request_more_info  │
                                            │ (Query Enhance)  │  │  (Ask More Info)   │
                                            └──────────────────┘  └────────────────────┘
                                                        │                │
                                                        │                ▼
                                                        │             [END]
                                                        ▼
                                            ┌──────────────────────┐
                                            │  diagnostic_check    │  ← Phân tích triệu chứng
                                            │ (Symptom Analysis)   │    với slots + context
                                            └──────────────────────┘
                                                        │
                                                        ▼
                                            ┌──────────────────────┐
                                            │ disease_conclusion   │  ← Kết luận bệnh
                                            │ (Disease Detection)  │    (nếu có)
                                            └──────────────────────┘
                                                        │
                                        ┌───────────────┴───────────────┐
                                        │                               │
                                [disease detected]            [no disease detected]
                                        │                               │
                                        ▼                               ▼
                        ┌───────────────────────────┐      ┌─────────────────────┐
                        │  treatment_retrieval      │      │  graph_retrieval    │
                        │ (Get Treatment Guidance)  │      │ (Knowledge Graph)   │
                        └───────────────────────────┘      └─────────────────────┘
                                        │                               │
                                        ▼                               ▼
                        ┌───────────────────────────┐      ┌─────────────────────┐
                        │ answer_with_treatment     │      │ answer_with_graph   │
                        │ (Treatment Answer + LLM)  │      │ (Graph Answer + LLM)│
                        └───────────────────────────┘      └─────────────────────┘
                                        │                               │
                                        └───────────────┬───────────────┘
                                                        ▼
                                            ┌──────────────────────┐
                                            │ conversation_memory  │  ← Update buffer
                                            │  (Memory Update)     │    + summary
                                            └──────────────────────┘
                                                        │
                                                        ▼
                                                     [END]