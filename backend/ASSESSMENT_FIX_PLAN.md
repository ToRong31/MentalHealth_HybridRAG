# KỊCH BẢN CHỈNH SỬA ASSESSMENT NODE

## MỤC ĐÍCH
Sửa cách tính score trong assessment node để scores phản ánh đúng mức độ nghiêm trọng và phân loại chính xác 3 labels (normal_response, adjustment_reaction, possible_disorder).

## VẤN ĐỀ HIỆN TẠI
- Test case nhẹ: score 150 (> 60) → đi diagnostic_retrieval (SAI)
- Test case nặng: score 162 (> 60) → đi diagnostic_retrieval (ĐÚNG nhưng không phân biệt được)
- Threshold 60 không phân biệt được nhẹ và nặng
- Scores phụ thuộc số lượng items thay vì mức độ nghiêm trọng

## NGUYÊN NHÂN
1. Cách tính score: Cộng dồn tất cả scores từ items → phụ thuộc số lượng items
2. Không xử lý score đặc biệt: Score -1 và 99 được tính như bình thường
3. Không sử dụng weight: Không dùng cohere_score (relevance score) làm weight → tất cả items có trọng số bằng nhau
4. Không filter theo similarity: Tính từ tất cả items sau rerank, kể cả items có similarity thấp → noise

---

## CÁC THAY ĐỔI CẦN THỰC HIỆN

### 1. SỬA CÁCH TÍNH SCORE: Weighted Average thay vì Cộng Dồn

**File:** `backend/src/rag/workflow/graph_nodes/assessment.py`

**Vị trí:** Dòng 163-183 (trong vòng lặp tính score)

**Thay đổi:**

**TRƯỚC:**
```python
for item in reranked:
    item_type = item.get("type", "").lower()
    original_score = item.get("original_score", 0.0)
    chunk_id = item.get("chunk_id", "")
    title = item.get("text", "")
    
    if "normal" in item_type or "stress" in item_type:
        type_scores["normal_stress"] += original_score  # ❌ CỘNG DỒN
        type_score_details["normal_stress"].append({
            "chunk_id": chunk_id,
            "title": title,
            "score": original_score,
        })
    elif "adjustment" in item_type or "điều chỉnh" in item_type:
        type_scores["adjustment_reaction"] += original_score  # ❌ CỘNG DỒN
        type_score_details["adjustment_reaction"].append({
            "chunk_id": chunk_id,
            "title": title,
            "score": original_score,
        })
```

**SAU:**
```python
# Filter items theo similarity threshold (lấy hết items có cohere_score > threshold)
# Cohere rerank đã sắp xếp items theo relevance từ cao xuống thấp
# Chỉ tính items có similarity đủ cao để đảm bảo độ chính xác
SIMILARITY_THRESHOLD = 0.5  # Chỉ tính items có cohere_score > 0.5

filtered_items = []
for item in reranked:
    # Lấy cohere_score (từ Cohere Rerank API) làm weight
    cohere_score = item.get("cohere_score") or item.get("rerank_score") or item.get("milvus_score", 0.0)
    
    # Chỉ tính items có similarity đủ cao
    if cohere_score > SIMILARITY_THRESHOLD:
        filtered_items.append(item)

logger.info(f"[FILTER] Total reranked items: {len(reranked)}, "
           f"Items after similarity filter (> {SIMILARITY_THRESHOLD}): {len(filtered_items)}")

# Track tổng weight cho mỗi type (cần để tính weighted average)
normal_stress_total_weight = 0.0
adjustment_reaction_total_weight = 0.0

for item in filtered_items:
    item_type = item.get("type", "").lower()
    original_score = item.get("original_score", 0.0)
    chunk_id = item.get("chunk_id", "")
    title = item.get("text", "")
    
    # Xử lý score đặc biệt
    # Bỏ qua score -1 (không tính)
    if original_score == -1:
        continue
    
    # Xử lý score 99 (emergency cases): Cap thành 10
    # Score 99 thường là emergency cases (ví dụ: "Homicidal ideation", "Suicidal ideation")
    # Cap thành 10 để tránh score quá cao nhưng vẫn phản ánh mức độ nghiêm trọng
    if original_score == 99:
        capped_score = 10
    else:
        capped_score = original_score
    
    # Lấy cohere_score làm weight (từ Cohere Rerank API)
    cohere_score = item.get("cohere_score") or item.get("rerank_score") or item.get("milvus_score", 0.0)
    
    # Tính weighted contribution
    weighted_contribution = capped_score * cohere_score
    
    if "normal" in item_type or "stress" in item_type:
        type_scores["normal_stress"] += weighted_contribution  # Weighted sum
        normal_stress_total_weight += cohere_score  # Track tổng weight
        type_score_details["normal_stress"].append({
            "chunk_id": chunk_id,
            "title": title,
            "score": capped_score,
            "weight": cohere_score,
            "weighted_contribution": weighted_contribution,
        })
    elif "adjustment" in item_type or "điều chỉnh" in item_type:
        type_scores["adjustment_reaction"] += weighted_contribution  # Weighted sum
        adjustment_reaction_total_weight += cohere_score  # Track tổng weight
        type_score_details["adjustment_reaction"].append({
            "chunk_id": chunk_id,
            "title": title,
            "score": capped_score,
            "weight": cohere_score,
            "weighted_contribution": weighted_contribution,
        })

# Tính weighted average
# Final scores = weighted average (không phụ thuộc số lượng items)
if normal_stress_total_weight > 0:
    type_scores["normal_stress"] = type_scores["normal_stress"] / normal_stress_total_weight
else:
    type_scores["normal_stress"] = 0.0

if adjustment_reaction_total_weight > 0:
    type_scores["adjustment_reaction"] = type_scores["adjustment_reaction"] / adjustment_reaction_total_weight
else:
    type_scores["adjustment_reaction"] = 0.0
```

**Lưu ý:** 
- Sử dụng `cohere_score` (từ Cohere Rerank API) làm weight vì nó phản ánh độ relevant chính xác hơn `milvus_score`
- Filter theo similarity threshold (0.6) để loại bỏ items có similarity quá thấp → giảm noise
- Lấy hết items có similarity > threshold (không giới hạn số lượng) → không bỏ sót items quan trọng
- Weighted average đảm bảo score không phụ thuộc số lượng items

---

### 2. ĐIỀU CHỈNH THRESHOLD: Từ 60 → 5-6

**File:** `backend/src/rag/workflow/graph_nodes/assessment.py`

**Vị trí:** Dòng 200 (logic routing)

**Thay đổi:**

**TRƯỚC:**
```python
if normal_stress_score > 60 or adjustment_reaction_score > 60:
    state["assessment_category"] = "possible_disorder"
```

**SAU:**
```python
# Threshold mới: 5-6 (sau khi sửa cách tính score thành weighted average)
THRESHOLD = 5.5  # Có thể điều chỉnh sau khi test

if normal_stress_score > THRESHOLD or adjustment_reaction_score > THRESHOLD:
    state["assessment_category"] = "possible_disorder"
```

**Lưu ý:** Threshold này cần test lại sau khi sửa cách tính score. Có thể điều chỉnh trong khoảng 5-6 dựa trên test results.

---

### 3. THÊM LOGGING ĐỂ DEBUG

**File:** `backend/src/rag/workflow/graph_nodes/assessment.py`

**Vị trí:** Sau khi tính scores (dòng 185-186)

**Thêm:**

```python
logger.info(f"[SCORES] normal_stress: {type_scores['normal_stress']:.2f}, "
           f"adjustment_reaction: {type_scores['adjustment_reaction']:.2f}")
logger.info(f"[SCORE DETAILS] Normal stress items: {len(type_score_details['normal_stress'])}, "
           f"Adjustment reaction items: {len(type_score_details['adjustment_reaction'])}")
logger.info(f"[TOP ITEMS] Normal stress top 3:")
for i, detail in enumerate(type_score_details["normal_stress"][:3], 1):
    logger.info(f"  {i}. {detail['title']}: score={detail['score']}, weight={detail.get('weight', 0):.4f}, "
               f"contribution={detail.get('weighted_contribution', 0):.2f}")
logger.info(f"[TOP ITEMS] Adjustment reaction top 3:")
for i, detail in enumerate(type_score_details["adjustment_reaction"][:3], 1):
    logger.info(f"  {i}. {detail['title']}: score={detail['score']}, weight={detail.get('weight', 0):.4f}, "
               f"contribution={detail.get('weighted_contribution', 0):.2f}")
```

---

## THỨ TỰ THỰC HIỆN

1. **Backup code hiện tại:**
   - Copy file `assessment.py` thành `assessment.py.backup`
   - Hoặc commit code hiện tại trước khi sửa

2. **Sửa cách tính score (Phần 1):**
   - Thay đổi logic tính score từ cộng dồn → weighted average
   - Xử lý score đặc biệt (-1, 99)
   - Filter items theo similarity threshold (cohere_score > 0.6)
   - Sử dụng cohere_score làm weight (từ Cohere Rerank API)

3. **Điều chỉnh threshold (Phần 2):**
   - Thay đổi threshold từ 60 → 5.5
   - Có thể điều chỉnh sau khi test

4. **Thêm logging (Phần 3):**
   - Thêm logging chi tiết để debug

5. **Test:**
   - Test với các test cases từ nhẹ đến nặng
   - Kiểm tra scores có phản ánh đúng mức độ nghiêm trọng không
   - Điều chỉnh threshold nếu cần

---

## ROLLBACK PLAN

Nếu xảy ra lỗi:

1. **Khôi phục code:**
   ```bash
   # Nếu đã backup
   cp backend/src/rag/workflow/graph_nodes/assessment.py.backup \
      backend/src/rag/workflow/graph_nodes/assessment.py
   
   # Hoặc nếu đã commit
   git checkout backend/src/rag/workflow/graph_nodes/assessment.py
   ```

2. **Kiểm tra logs:**
   - Xem logs để tìm lỗi cụ thể
   - Kiểm tra xem có lỗi syntax không
   - Kiểm tra xem có lỗi runtime không

3. **Test lại:**
   - Test với test case đơn giản trước
   - Kiểm tra scores có được tính đúng không

---

## KIỂM TRA SAU KHI SỬA

1. **Kiểm tra syntax:**
   ```bash
   python -m py_compile backend/src/rag/workflow/graph_nodes/assessment.py
   ```

2. **Kiểm tra imports:**
   - Đảm bảo tất cả imports đều đúng
   - Không có circular imports

3. **Test với test cases:**
   - Test case nhẹ: expected score ~2-3
   - Test case vừa: expected score ~4-5
   - Test case nặng: expected score ~6-8
   - Kiểm tra routing có đúng không

4. **Kiểm tra logs:**
   - Xem logs để đảm bảo scores được tính đúng
   - Kiểm tra top items có hợp lý không

---

## GHI CHÚ

- **Threshold routing (5.5):** Giá trị đề xuất ban đầu, cần test lại để điều chỉnh
- **Similarity threshold (0.6):** Chỉ tính items có cohere_score > 0.6, có thể điều chỉnh (0.5-0.7) tùy theo kết quả test
- **Score 99 (Emergency cases):** Được cap thành 10 để tránh score quá cao nhưng vẫn phản ánh mức độ nghiêm trọng (10 > 5.5 threshold). Score 99 thường là emergency cases như "Homicidal ideation", "Suicidal ideation"
- **Weighted average:** Đảm bảo items có similarity cao (cohere_score cao) có trọng số cao hơn
- **Cohere score:** Sử dụng `cohere_score` từ Cohere Rerank API làm weight vì nó phản ánh độ relevant chính xác hơn `milvus_score`
- **Filter strategy:** Lấy hết items có similarity > threshold (không giới hạn số lượng) để không bỏ sót items quan trọng

---

## CÁC FILE CẦN SỬA

1. `backend/src/rag/workflow/graph_nodes/assessment.py`
   - Sửa cách tính score (dòng 163-183)
   - Điều chỉnh threshold (dòng 200)
   - Thêm logging (sau dòng 186)

---

## TIMELINE

1. **Backup:** 5 phút
2. **Sửa code:** 30-45 phút
3. **Test:** 30-60 phút
4. **Điều chỉnh:** Tùy theo kết quả test

**Tổng thời gian ước tính:** 1.5-2 giờ

