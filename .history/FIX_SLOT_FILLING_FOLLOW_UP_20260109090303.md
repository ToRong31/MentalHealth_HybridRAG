# Fix: Slot Filling Follow-up Questions

## Vấn đề đã fix

**Nguyên nhân:** Hàm `filter_follow_up_for_required_only` đang sử dụng logic **1:1 index mapping** giữa `follow_up_questions` và `relevant_missing_slots`. Điều này sai vì:

1. LLM có thể tạo nhiều câu hỏi cho 1 slot
2. LLM tạo câu hỏi không theo thứ tự slots
3. Khi không match được index → `filtered = []` → fallback về câu hỏi chung chung

**Ví dụ lỗi:**
```python
relevant_missing_slots = ["onset", "duration", "intensity"]  # 3 slots
follow_up_questions = [
    "Bạn cảm thấy như vậy từ khi nào?",
    "Tình trạng này đã kéo dài bao lâu?",
    "Cường độ khó chịu ở mức nào?",
    "Có ảnh hưởng đến công việc không?"  # 4 câu hỏi (nhiều hơn slots!)
]

# Old logic: Chỉ lấy 3 câu đầu theo index (mất câu thứ 4)
# Nếu REQUIRED_SLOTS không chứa slot nào trong top 3 → filtered = [] → câu hỏi chung chung!
```

## Giải pháp

**Cách fix:** Thay đổi logic từ **index-based filtering** sang **presence-based filtering**:

```python
# OLD (SAI):
for i, slot_name in enumerate(relevant_missing_slots):
    if slot_name in REQUIRED_SLOTS and i < len(follow_up_questions):
        filtered.append(follow_up_questions[i])  # ← Giả định mapping 1:1

# NEW (ĐÚNG):
has_required_missing = any(slot in REQUIRED_SLOTS for slot in relevant_missing_slots)
if has_required_missing:
    return follow_up_questions  # ← Tin tưởng LLM đã tạo câu hỏi phù hợp
else:
    return []  # Chỉ có optional slots → không hỏi bây giờ
```

**Lý do:** 
- LLM đã được train với prompt chi tiết, biết cách tạo câu hỏi phù hợp context
- Việc filter theo index là không đáng tin cậy
- Chỉ cần check: "Có REQUIRED slots nào missing không?" → Nếu có → Hỏi tất cả câu LLM đã tạo

## File đã sửa

- `backend/src/rag/utils/slot_utils.py` - Hàm `filter_follow_up_for_required_only()`

## Test ngay

### Cách 1: Test qua Postman

1. Mở Postman collection: `Mental_Health_API.postman_collection.json`
2. Chạy flow: Register → Login → Chat
3. Gửi tin nhắn: "Tôi buồn quá"
4. **Mong đợi:** Chatbot sẽ hỏi các câu hỏi CỤ THỂ như:
   - "Cảm giác buồn này bắt đầu từ khi nào?"
   - "Đã kéo dài bao lâu rồi?"
   - "Có chuyện gì xảy ra gần đây không?"

   **KHÔNG phải câu chung chung:** "Bạn có thể chia sẻ thêm chi tiết..."

### Cách 2: Test qua cURL (nhanh)

```powershell
# 1. Health check
curl http://localhost:8000/health

# 2. Register (nếu chưa có account)
curl -X POST http://localhost:8000/api/v1/auth/register `
  -H "Content-Type: application/json" `
  -d '{\"username\":\"testuser\",\"password\":\"Test123!\",\"email\":\"test@example.com\"}'

# 3. Login
$response = curl -X POST http://localhost:8000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"username\":\"testuser\",\"password\":\"Test123!\"}' | ConvertFrom-Json

$token = $response.access_token

# 4. Chat - Test slot filling
curl -X POST http://localhost:8000/api/v1/chat `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -d '{\"message\":\"Tôi buồn quá\"}'
```

### Cách 3: Xem logs để debug

```powershell
# Real-time logs
docker logs -f chatbot-backend

# Tìm slot filling results
docker logs chatbot-backend --tail 200 | Select-String "SLOT FILLING" -Context 5

# Tìm follow-up questions
docker logs chatbot-backend --tail 200 | Select-String "follow_up_questions" -Context 3
```

## Kiểm tra kết quả

### ✅ Success indicators:

1. **Logs sẽ show:**
   ```
   [SLOT FILLING] Stage: presenting | Intake complete: False
   ❌ Incomplete required slots. Asking 3 REQUIRED questions
   ```

2. **Response sẽ có các câu hỏi CỤ THỂ:**
   - "Cảm giác buồn này bắt đầu từ khi nào?"
   - "Đã kéo dài bao lâu rồi?"
   - "Có ảnh hưởng đến công việc/học tập không?"

3. **LangSmith trace sẽ show:**
   - `slot_filling_node`: follow_up_questions = [...] (có câu hỏi)
   - `request_more_info_node`: Sử dụng các câu hỏi từ slot filling

### ❌ Failure indicators (nếu vẫn lỗi):

1. **Response vẫn là câu chung chung:**
   ```
   "Bạn có thể chia sẻ thêm chi tiết về tình huống..."
   ```

2. **Logs show:**
   ```
   ❌ Incomplete required slots. Asking 0 REQUIRED questions
   ```

3. **Nguyên nhân có thể:**
   - LLM không generate `follow_up_questions` (check raw LLM response)
   - `relevant_missing_slots` = [] (LLM nghĩ không cần hỏi)
   - API quota vẫn còn hết (check error logs)

## Summary

**Before:**
- Filter theo index → Mất câu hỏi → Empty list → Câu chung chung

**After:**
- Tin tưởng LLM → Giữ tất cả câu hỏi nếu có REQUIRED slots missing → Câu hỏi cụ thể

**Key insight:** LLM đã được prompt rất chi tiết để tạo câu hỏi phù hợp. Việc của chúng ta chỉ là **đừng filter quá mạnh** và tin tưởng output của LLM.
