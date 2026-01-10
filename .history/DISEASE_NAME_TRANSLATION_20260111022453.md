# Disease Name Translation - Implementation

## Vấn đề (Problem)

Chatbot đang trả về tên bệnh bằng tiếng Anh thay vì tiếng Việt:
```
Dựa trên các triệu chứng bạn mô tả, tôi nhận thấy bạn có dấu hiệu có thể mắc Bipolar and Related Disorders.
```

Người dùng Việt Nam sẽ khó hiểu và không tự nhiên khi đọc tên bệnh bằng tiếng Anh.

## Giải pháp (Solution)

### ✅ 1. Tạo Disease Translation Mapping

**File mới**: `backend/src/rag/utils/disease_translation.py`

Chứa:
- Dictionary mapping 100+ tên bệnh từ English → Vietnamese
- Function `translate_disease_name()` để dịch tên bệnh
- Function `translate_disease_list()` để dịch list các bệnh
- Support case-insensitive và partial matching

**Các loại bệnh được hỗ trợ**:
- Mood Disorders (Bipolar, Depression)
- Anxiety Disorders
- OCD and Related
- Trauma and Stressor-Related (PTSD)
- Eating Disorders
- Sleep Disorders
- Schizophrenia Spectrum
- Personality Disorders
- Substance-Related
- Neurodevelopmental (ADHD, Autism)
- Dissociative Disorders
- Somatic Disorders

### ✅ 2. Tích hợp vào Disease Conclusion

**File**: `backend/src/rag/workflow/graph_nodes/disease_conclusion.py`

**Thay đổi**:
1. Import `translate_disease_name`
2. Dịch tên bệnh trước khi hiển thị cho người dùng
3. Giữ nguyên tên tiếng Anh trong `state["detected_disease"]` để logic backend hoạt động đúng

```python
# Translate disease name to Vietnamese if needed
disease_name_display = detected_disease
if language == "vi" or language == "vn":
    disease_name_display = translate_disease_name(detected_disease)
    logger.info(f"📝 Translated: '{detected_disease}' -> '{disease_name_display}'")
```

**Sử dụng trong conclusion message**:
```python
f"Dựa trên các triệu chứng bạn mô tả, tôi nhận thấy bạn có dấu hiệu có thể mắc **{disease_name_display}**."
```

## Ví dụ Translations

### Before:
```
Dựa trên các triệu chứng bạn mô tả, tôi nhận thấy bạn có dấu hiệu có thể mắc Bipolar and Related Disorders.
```

### After:
```
Dựa trên các triệu chứng bạn mô tả, tôi nhận thấy bạn có dấu hiệu có thể mắc Rối loạn Lưỡng cực và các rối loạn liên quan.
```

## Mapping Examples

| English | Vietnamese |
|---------|-----------|
| Bipolar and Related Disorders | Rối loạn Lưỡng cực và các rối loạn liên quan |
| Major Depressive Disorder | Rối loạn Trầm cảm nặng |
| Generalized Anxiety Disorder | Rối loạn Lo âu lan tỏa |
| Obsessive-Compulsive Disorder | Rối loạn Ám ảnh Cưỡng chế |
| Post-Traumatic Stress Disorder | Rối loạn Căng thẳng sau Chấn thương |
| Schizophrenia | Tâm thần phân liệt |
| ADHD | Rối loạn Thiếu tập trung/Tăng động |
| Anorexia Nervosa | Chứng Biếng ăn Tâm thần |

## Testing

Chạy test suite:
```bash
cd /app
python test_disease_translation.py
```

**Test coverage**:
- ✅ Common disease translations
- ✅ Case-insensitive matching
- ✅ Partial matching (plural/singular)
- ✅ Unknown diseases (return original)
- ✅ List translation

## Implementation Details

### Smart Matching Strategy

1. **Exact match**: Tìm khớp chính xác
   ```python
   "Bipolar Disorder" -> "Rối loạn Lưỡng cực"
   ```

2. **Case-insensitive match**: Không phân biệt hoa thường
   ```python
   "bipolar disorder" -> "Rối loạn Lưỡng cực"
   "BIPOLAR DISORDER" -> "Rối loạn Lưỡng cực"
   ```

3. **Partial match**: Khớp một phần (cho plural/singular)
   ```python
   "Depressive Disorders" -> "Các rối loạn Trầm cảm"
   "Anxiety Disorders" -> "Các rối loạn Lo âu"
   ```

4. **Fallback**: Trả về tên gốc nếu không tìm thấy
   ```python
   "Unknown Condition" -> "Unknown Condition"
   ```

### Backend State Management

**Important**: 
- `state["detected_disease"]` vẫn giữ tên tiếng Anh
- Chỉ `disease_name_display` được dịch sang tiếng Việt để hiển thị

**Lý do**:
- Treatment retrieval cần tên tiếng Anh để match với database
- Diagnostic reasoning logic dựa trên tên tiếng Anh
- Chỉ user-facing text được dịch

## Files Modified

1. ✅ `backend/src/rag/utils/disease_translation.py` (NEW)
   - Disease name mapping dictionary
   - Translation functions

2. ✅ `backend/src/rag/workflow/graph_nodes/disease_conclusion.py`
   - Import translation function
   - Translate for display
   - Use Vietnamese name in conclusion message

3. ✅ `backend/test_disease_translation.py` (NEW)
   - Test suite for translation

## Future Enhancements

### Thêm bệnh mới:
```python
DISEASE_NAME_TRANSLATION = {
    "New English Disease Name": "Tên bệnh mới tiếng Việt",
}
```

### Support nhiều ngôn ngữ:
- Có thể mở rộng để support thêm ngôn ngữ khác
- Cần thêm mapping dictionaries cho từng ngôn ngữ

## Impact

### Positive:
- ✅ User experience tốt hơn với tên bệnh tiếng Việt
- ✅ Dễ hiểu và chuyên nghiệp hơn
- ✅ Không ảnh hưởng backend logic
- ✅ Dễ maintain và mở rộng

### Note:
- Tên bệnh trong database vẫn là tiếng Anh
- Chỉ display layer được dịch
- Translation chạy realtime, không có performance impact

---

**Date**: 2026-01-11  
**Version**: 1.0  
**Status**: ✅ Implemented & Tested
