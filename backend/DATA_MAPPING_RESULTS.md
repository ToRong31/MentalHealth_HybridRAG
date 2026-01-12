# KẾT QUẢ ÁP DỤNG MAPPING

## TỔNG KẾT

✅ **Mapping đã được áp dụng thành công!**

### Thống kê thay đổi:

- **Adjustment Reaction 5 → 3**: 5 items (generic mood/affect)
- **Adjustment Reaction 5 → 4**: 4 items (severe mood/affect)
- **Normal Stress -1 → 2**: 5 items (stress events nặng)
- **Normal Stress -1 → 1**: 25 items (stress context)
- **Unchanged**: 187 items
- **Total**: 226 items

### Phân bố score sau mapping:

**Adjustment Reaction:**
- score -1: 16 items
- score 2: 18 items
- score 3: 45 items (tăng từ 40 do 5 items từ 5 → 3)
- score 4: 11 items (tăng từ 7 do 4 items từ 5 → 4)
- score 5: 81 items (giảm từ 90 do 9 items đã giảm)
- score 99: 22 items (giữ nguyên)

**Normal Stress:**
- score -1: 1 item (còn lại, không nằm trong mapping plan)
- score 1: 27 items (tăng từ 1 do 25 items từ -1 → 1, + 1 item gốc)
- score 2: 5 items (tăng từ 0 do 5 items từ -1 → 2)

---

## FILES HIỆN TẠI

✅ **Đã swap files thành công!**

1. **File gốc (đang dùng)**: `data/raw/normal_responses.jsonl` 
   - ✅ Chứa **data mới** (đã apply mapping)
   - Hệ thống sẽ tự động sử dụng file này

2. **File v2 (backup)**: `data/raw/normal_responses_v2.jsonl`
   - Chứa **data gốc** (backup trước khi mapping)

3. **File orig (backup gốc)**: `data/raw/normal_responses_orig.jsonl`
   - Backup gốc ban đầu (có thể xóa nếu không cần)

4. **Script**: `apply_score_mapping.py`
   - Script để apply mapping (đã chạy thành công)

---

## VERIFICATION

Đã verify các items quan trọng:
- ✅ MB24.5 (Depressed mood): 5 → 3
- ✅ MB24.3 (Anxiety): 5 → 3
- ✅ MB24.2 (Anhedonia): 5 → 4
- ✅ MB22.3 (Hopelessness): 5 → 4
- ✅ QE62 (Uncomplicated bereavement): -1 → 2
- ✅ QE84 (Acute stress reaction): -1 → 2
- ✅ QE30.0 (Insufficient social insurance support): -1 → 1
- ✅ MB26.0 (Delusion): 5 → 5 (giữ nguyên)
- ✅ MB27.2 (Hallucinations): 5 → 5 (giữ nguyên)

---

## NEXT STEPS

### 1. Test với test cases
```bash
# Test với các test cases trong TEST_CASES_ASSESSMENT.md
# Kiểm tra:
# - Case nhẹ: score < 5
# - Case nặng: score > 5.5
# - Normal stress có contribution (không còn = 0)
```

**Lưu ý**: File gốc đã chứa data mới, hệ thống sẽ tự động sử dụng. Chỉ cần test!

### 2. Reload Milvus collection (nếu cần)

Nếu Milvus collection `normal_responses` được load từ file này, cần:
1. Re-index collection với data mới
2. Hoặc restart service để reload

### 4. Monitor và điều chỉnh

Sau khi deploy:
- Monitor logs để xem score distribution
- Điều chỉnh threshold nếu cần (hiện tại 5-5.5)
- Collect feedback từ test cases

---

## ROLLBACK

Nếu cần rollback về data gốc:
```bash
cd backend
# Option 1: Rollback từ file v2 (data gốc)
cp data/raw/normal_responses_v2.jsonl data/raw/normal_responses.jsonl

# Option 2: Rollback từ file orig (backup gốc)
cp data/raw/normal_responses_orig.jsonl data/raw/normal_responses.jsonl
```

---

## LƯU Ý

1. **File gốc đã chứa data mới**: Hệ thống sẽ tự động sử dụng data mới từ `normal_responses.jsonl`
2. **Threshold**: Giữ nguyên 5-5.5 như kịch bản
3. **Emergency items**: Không sửa (code đã cap thành 10)
4. **Normal stress -1**: Còn 1 item không nằm trong mapping plan: `QE01 - Stress, not elsewhere classified` (có thể giữ nguyên)
5. **Test**: Phải test kỹ với các test cases trước khi deploy production
6. **Milvus**: Nếu Milvus collection được load từ file này, cần re-index hoặc restart service

