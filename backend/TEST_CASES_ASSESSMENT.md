# TEST CASES CHO ASSESSMENT NODE

## MỤC ĐÍCH
Test cases để kiểm tra cách tính score mới (weighted average) và routing logic sau khi:
1. Apply score mapping (data mới)
2. Implement severity boost logic (Option 2 + 4)

## LƯU Ý
- Tất cả test cases đã được format với đầy đủ 25 required slots để pass slot filling
- Duration phải có số + đơn vị (ví dụ: "3 ngày", "2 tuần", "1 tháng")
- Tri-state fields phải là "yes" hoặc "no" (không phải "unknown")
- Test cases được sắp xếp từ nhẹ đến nặng
- **Expected scores đã được cập nhật dựa trên:**
  - **Data mới sau mapping:**
    - Generic symptoms (Depressed mood, Anxiety, Dysphoria): score 3 (giảm từ 5)
    - Severe mood symptoms (Anhedonia, Hopelessness, Avolition): score 4 (giảm từ 5)
    - Normal stress items: score 1-2 (tăng từ -1)
    - Severe symptoms (psychotic/cognitive/neurological): score 5 (giữ nguyên)
  - **Severity boost logic:**
    - Case nhẹ: Boost items score 1-3 (weight * 1.2), penalize items score 4-5 (weight * 0.7)
    - Case nặng: Boost items score 4-5 (weight * 1.2), penalize items score 1-3 (weight * 0.7)

---

## TEST CASE 1: NORMAL STRESS - NHẸ

**Mục tiêu:** Test case nhẹ nhất, expected score thấp, route đến normal_coping_retrieval

**Lưu ý:** Với data mới, normal_stress có score 1-2 (tăng từ -1), nên sẽ có contribution tốt hơn.

**Query:**
```
Tôi vừa cãi nhau với bạn thân 3 ngày trước, cảm thấy hơi buồn và lo lắng một chút. Vấn đề chính là xung đột với bạn thân. Cảm xúc của tôi là buồn nhẹ và lo lắng nhẹ. Tâm trạng chính là hơi buồn. Triệu chứng bắt đầu 3 ngày trước sau khi cãi nhau với bạn. Kéo dài 3 ngày, xảy ra thỉnh thoảng khi nghĩ đến bạn. Triệu chứng dao động nhiều, có lúc quên đi. Cường độ nhẹ, mức độ đau khổ nhẹ, căng thẳng ở mức nhẹ. Hoạt động hàng ngày không bị ảnh hưởng, công việc bình thường, giao tiếp xã hội giảm một chút, tự chăm sóc tốt. Yếu tố kích thích là cãi nhau với bạn thân, căng thẳng hiện tại là suy nghĩ về mối quan hệ, sự kiện gần đây là cãi nhau với bạn thân 3 ngày trước. Tôi không sử dụng chất kích thích, không có bệnh nền, không có thay đổi thuốc, uống cà phê bình thường. Tôi có gia đình hỗ trợ, và tôi đang cố gắng giải quyết vấn đề bằng cách nói chuyện với bạn. Tôi không có triệu chứng giống hưng cảm, và không có triệu chứng giống loạn thần.
```

**Expected (sau severity boost):**
- Query severity: "mild" (detected từ "nhẹ", "mild intensity")
- normal_stress_score: ~1-2
- adjustment_reaction_score: ~2-3 (items score 3 được boost * 1.2, items score 5 bị penalize * 0.7)
- assessment_category: "normal_response" hoặc "adjustment_reaction"
- Route: normal_coping_retrieval hoặc adjustment_retrieval

---

## TEST CASE 2: ADJUSTMENT REACTION - NHẸ

**Mục tiêu:** Test case adjustment reaction nhẹ, expected score ~2-3, route đến adjustment_retrieval

**Lưu ý:** Với data mới, generic symptoms (Anxiety, Depressed mood) có score 3, nên score sẽ thấp hơn so với trước.

**Query:**
```
Tôi vừa chuyển công việc mới 1 tuần trước, cảm thấy hơi lo lắng và căng thẳng. Vấn đề chính là thích nghi với môi trường làm việc mới. Cảm xúc của tôi là lo lắng nhẹ và căng thẳng nhẹ. Tâm trạng chính là lo lắng. Triệu chứng bắt đầu 1 tuần trước sau khi bắt đầu công việc mới. Kéo dài 1 tuần, xảy ra hàng ngày khi đi làm. Triệu chứng dao động ít, ổn định. Cường độ nhẹ, mức độ đau khổ nhẹ, căng thẳng ở mức nhẹ. Hoạt động hàng ngày hơi bị ảnh hưởng, công việc hơi khó tập trung, giao tiếp xã hội bình thường, tự chăm sóc tốt. Yếu tố kích thích là thay đổi công việc, căng thẳng hiện tại là lo lắng về hiệu suất làm việc, sự kiện gần đây là bắt đầu công việc mới 1 tuần trước. Tôi không sử dụng chất kích thích, không có bệnh nền, không có thay đổi thuốc, uống cà phê bình thường. Tôi có đồng nghiệp hỗ trợ, và tôi đang cố gắng thích nghi bằng cách học hỏi từ đồng nghiệp. Tôi không có triệu chứng giống hưng cảm, và không có triệu chứng giống loạn thần.
```

**Expected (sau severity boost):**
- Query severity: "mild" (detected từ "nhẹ", "mild intensity")
- normal_stress_score: ~1-2
- adjustment_reaction_score: ~2-3 (items score 3 được boost, items score 5 bị penalize)
- assessment_category: "adjustment_reaction"
- Route: adjustment_retrieval

---

## TEST CASE 3: ADJUSTMENT REACTION - VỪA

**Mục tiêu:** Test case adjustment reaction vừa, expected score ~3-4, route đến adjustment_retrieval

**Lưu ý:** Với data mới, generic symptoms giảm từ 5 → 3, nên score sẽ thấp hơn. Case vừa chủ yếu match generic (3) + một số severe mood (4).

**Query:**
```
Tôi vừa ly dị 2 tuần trước, cảm thấy buồn, tức giận và khó ngủ. Vấn đề chính là thay đổi cuộc sống sau ly dị. Cảm xúc của tôi là buồn vừa, tức giận và lo lắng. Tâm trạng chính là buồn. Triệu chứng bắt đầu 2 tuần trước sau khi ly dị. Kéo dài 2 tuần, xảy ra hàng ngày, đặc biệt vào buổi tối. Triệu chứng dao động vừa, có lúc tốt hơn. Cường độ vừa, mức độ đau khổ vừa, căng thẳng ở mức vừa. Hoạt động hàng ngày bị ảnh hưởng vừa, công việc khó tập trung, giao tiếp xã hội giảm, tự chăm sóc vẫn tốt. Yếu tố kích thích là ly dị, căng thẳng hiện tại là lo lắng về tương lai và tài chính, sự kiện gần đây là ly dị 2 tuần trước. Tôi không sử dụng chất kích thích, không có bệnh nền, không có thay đổi thuốc, uống cà phê bình thường. Tôi có gia đình hỗ trợ, và tôi đang cố gắng thích nghi bằng cách tập thể dục và nói chuyện với bạn bè. Tôi không có triệu chứng giống hưng cảm, và không có triệu chứng giống loạn thần.
```

**Expected (sau severity boost):**
- Query severity: "moderate" hoặc "unknown" (không có keywords rõ ràng)
- normal_stress_score: ~1-2
- adjustment_reaction_score: ~3-4 (mix generic score 3 + severe mood score 4, không có boost/penalty)
- assessment_category: "adjustment_reaction"
- Route: adjustment_retrieval

---

## TEST CASE 4: ADJUSTMENT REACTION - NẶNG

**Mục tiêu:** Test case adjustment reaction nặng, expected score ~4-5, có thể route đến diagnostic_retrieval nếu > 5.5

**Lưu ý:** Với data mới, case nặng chủ yếu match severe mood symptoms (score 4) + có thể có một số severe symptoms (score 5). Score sẽ thấp hơn so với trước, có thể không vượt 5.5.

**Query:**
```
Tôi vừa mất việc 1 tháng trước, cảm thấy rất buồn, tuyệt vọng và mất ngủ. Vấn đề chính là thất nghiệp và lo lắng về tài chính. Cảm xúc của tôi là buồn nặng, tuyệt vọng và lo lắng. Tâm trạng chính là buồn. Triệu chứng bắt đầu 1 tháng trước sau khi mất việc. Kéo dài 1 tháng, xảy ra hàng ngày, đặc biệt vào buổi sáng. Triệu chứng dao động ít, ổn định ở mức nặng. Cường độ nặng, mức độ đau khổ nặng, căng thẳng ở mức nặng. Hoạt động hàng ngày bị ảnh hưởng nhiều, công việc không thể tìm được, giao tiếp xã hội giảm nhiều, tự chăm sóc kém. Yếu tố kích thích là mất việc, căng thẳng hiện tại là lo lắng về tài chính và tương lai, sự kiện gần đây là mất việc 1 tháng trước. Tôi không sử dụng chất kích thích, không có bệnh nền, không có thay đổi thuốc, uống cà phê bình thường. Tôi có gia đình hỗ trợ một phần, và tôi đang cố gắng tìm việc nhưng chưa thành công. Tôi không có triệu chứng giống hưng cảm, và không có triệu chứng giống loạn thần.
```

**Expected (sau severity boost):**
- Query severity: "severe" (detected từ "nặng", "severe intensity")
- normal_stress_score: ~1-2
- adjustment_reaction_score: ~4-5 (items score 4-5 được boost * 1.2, items score 3 bị penalize * 0.7)
- assessment_category: "adjustment_reaction" (nếu ≤ 5.5) hoặc "possible_disorder" (nếu > 5.5)
- Route: adjustment_retrieval (nếu ≤ 5.5) hoặc diagnostic_retrieval (nếu > 5.5)

---

## TEST CASE 5: POSSIBLE DISORDER - VỪA

**Mục tiêu:** Test case có thể là disorder, expected score ~4-5.5, route đến diagnostic_retrieval nếu > 5.5

**Lưu ý:** Với data mới, case vừa chủ yếu match severe mood (4) + một số severe symptoms (5). Score có thể không vượt 5.5 nếu không match đủ nhiều severe symptoms (score 5).

**Query:**
```
Tôi cảm thấy buồn, mệt mỏi và mất hứng thú với mọi thứ trong 2 tháng qua. Vấn đề chính là trầm cảm và mất động lực. Cảm xúc của tôi là buồn nặng, tuyệt vọng và lo lắng. Tâm trạng chính là buồn. Triệu chứng bắt đầu 2 tháng trước không rõ nguyên nhân cụ thể. Kéo dài 2 tháng, xảy ra hàng ngày, cả ngày. Triệu chứng dao động ít, ổn định ở mức nặng. Cường độ nặng, mức độ đau khổ nặng, căng thẳng ở mức nặng. Hoạt động hàng ngày bị ảnh hưởng nhiều, công việc khó tập trung và hiệu suất giảm, giao tiếp xã hội giảm nhiều, tự chăm sóc kém. Yếu tố kích thích không rõ ràng, căng thẳng hiện tại là lo lắng về tương lai và cảm giác vô vọng, sự kiện gần đây không có sự kiện cụ thể. Tôi không sử dụng chất kích thích, không có bệnh nền, không có thay đổi thuốc, uống cà phê bình thường. Tôi có gia đình hỗ trợ, và tôi đang cố gắng nhưng không hiệu quả, không có cách nào để cải thiện. Tôi không có triệu chứng giống hưng cảm, và không có triệu chứng giống loạn thần.
```

**Expected (sau severity boost):**
- Query severity: "severe" (detected từ "nặng", "severe intensity")
- normal_stress_score: ~2-3
- adjustment_reaction_score: ~4-5.5 (items score 4-5 được boost * 1.2, items score 3 bị penalize * 0.7)
- assessment_category: "adjustment_reaction" (nếu ≤ 5.5) hoặc "possible_disorder" (nếu > 5.5)
- Route: adjustment_retrieval (nếu ≤ 5.5) hoặc diagnostic_retrieval (nếu > 5.5)

---

## TEST CASE 6: POSSIBLE DISORDER - NẶNG

**Mục tiêu:** Test case disorder nặng, expected score ~5-6, route đến diagnostic_retrieval

**Lưu ý:** Với data mới, case nặng sẽ match nhiều severe symptoms (score 5) → score có thể vượt 5.5 và route đến diagnostic_retrieval.

**Query:**
```
Tôi cảm thấy rất buồn, tuyệt vọng, mất ngủ và không muốn làm gì cả trong 3 tháng qua. Vấn đề chính là trầm cảm nặng và mất động lực hoàn toàn. Cảm xúc của tôi là buồn rất nặng, tuyệt vọng và lo lắng. Tâm trạng chính là buồn. Triệu chứng bắt đầu 3 tháng trước không rõ nguyên nhân cụ thể. Kéo dài 3 tháng, xảy ra hàng ngày, cả ngày. Triệu chứng dao động ít, ổn định ở mức rất nặng. Cường độ rất nặng, mức độ đau khổ rất nặng, căng thẳng ở mức rất nặng. Hoạt động hàng ngày bị ảnh hưởng rất nhiều, công việc không thể hoàn thành, giao tiếp xã hội gần như không có, tự chăm sóc rất kém. Yếu tố kích thích không rõ ràng, căng thẳng hiện tại là lo lắng về tương lai và cảm giác vô vọng, sự kiện gần đây không có sự kiện cụ thể. Tôi không sử dụng chất kích thích, không có bệnh nền, không có thay đổi thuốc, uống cà phê bình thường. Tôi có gia đình hỗ trợ nhưng không giúp được nhiều, và tôi không có cách nào để cải thiện, không có cơ chế đối phó hiệu quả. Tôi không có triệu chứng giống hưng cảm, và không có triệu chứng giống loạn thần.
```

**Expected (sau severity boost):**
- Query severity: "severe" (detected từ "rất nặng", "very severe", "profound")
- normal_stress_score: ~2-3
- adjustment_reaction_score: ~5-6 (items score 4-5 được boost * 1.2 mạnh, items score 3 bị penalize * 0.7)
- assessment_category: "possible_disorder" (nếu > 5.5)
- Route: diagnostic_retrieval (nếu > 5.5)

---

## TEST CASE 7: SEVERE SYMPTOMS (Score 4-5 items)

**Mục tiêu:** Test case có nhiều symptoms nghiêm trọng, expected score cao, route đến diagnostic_retrieval

**Lưu ý:** Với data mới, "Hopelessness", "Anhedonia", "Avolition" có score 4 (giảm từ 5), nhưng vẫn có thể match nhiều severe symptoms (score 5) khác → score có thể vượt 5.5.

**Query:**
```
Tôi cảm thấy rất tuyệt vọng, mất hứng thú hoàn toàn và không có động lực làm gì cả trong 2 tháng qua. Vấn đề chính là trầm cảm nặng với nhiều triệu chứng nghiêm trọng. Cảm xúc của tôi là tuyệt vọng rất nặng, buồn và lo lắng. Tâm trạng chính là tuyệt vọng. Triệu chứng bắt đầu 2 tháng trước không rõ nguyên nhân cụ thể. Kéo dài 2 tháng, xảy ra hàng ngày, cả ngày. Triệu chứng dao động ít, ổn định ở mức rất nặng. Cường độ rất nặng, mức độ đau khổ rất nặng, căng thẳng ở mức rất nặng. Hoạt động hàng ngày bị ảnh hưởng rất nhiều, công việc không thể làm được, giao tiếp xã hội không có, tự chăm sóc rất kém. Yếu tố kích thích không rõ ràng, căng thẳng hiện tại là cảm giác vô vọng và mất hứng thú hoàn toàn, sự kiện gần đây không có sự kiện cụ thể. Tôi không sử dụng chất kích thích, không có bệnh nền, không có thay đổi thuốc, uống cà phê bình thường. Tôi có gia đình hỗ trợ nhưng không giúp được, và tôi cảm thấy không có cách nào, không có cơ chế đối phó hiệu quả. Tôi không có triệu chứng giống hưng cảm, và không có triệu chứng giống loạn thần.
```

**Expected (sau severity boost):**
- Query severity: "severe" (detected từ "rất nặng", "very severe", "profound")
- normal_stress_score: ~2-3
- adjustment_reaction_score: ~5-6.5 (items score 4-5 được boost * 1.2 mạnh, items score 3 bị penalize * 0.7)
- assessment_category: "possible_disorder" (nếu > 5.5)
- Route: diagnostic_retrieval (nếu > 5.5)
- Note: Với data mới, "Hopelessness", "Anhedonia", "Avolition" có score 4 (không còn 5), nhưng vẫn có thể match nhiều severe symptoms (score 5) khác → với severity boost, weighted average có thể vượt 5.5

---

## CHECKLIST CÁC SLOTS CẦN CÓ

Mỗi test case phải có đầy đủ các thông tin sau:

### 1. PRESENTING (3 slots)
- ✅ presenting_problem: "Vấn đề chính là..."
- ✅ emotion: "Cảm xúc là..."
- ✅ primary_mood: "Tâm trạng chính là..."

### 2. TIMELINE (4 slots)
- ✅ onset: "Triệu chứng bắt đầu..."
- ✅ duration: "Kéo dài X ngày/tuần/tháng" (phải có số + đơn vị)
- ✅ frequency: "Xảy ra..."
- ✅ symptom_fluctuation: "Triệu chứng dao động..."

### 3. SEVERITY (3 slots)
- ✅ intensity: "Cường độ..."
- ✅ distress_level: "Mức độ đau khổ..."
- ✅ stress_level: "Căng thẳng ở mức..."

### 4. FUNCTIONING (4 slots)
- ✅ daily_functioning: "Hoạt động hàng ngày..."
- ✅ work_school_impact: "Công việc..."
- ✅ social_functioning: "Giao tiếp xã hội..."
- ✅ self_care_functioning: "Tự chăm sóc..."

### 5. CONTEXT (3 slots)
- ✅ trigger: "Yếu tố kích thích là..."
- ✅ current_stressors: "Căng thẳng hiện tại là..."
- ✅ recent_life_events: "Sự kiện gần đây là..."

### 6. EXCLUSION (4 slots)
- ✅ substance_use_any: "Tôi không sử dụng chất kích thích" → "no"
- ✅ medical_history_any: "Không có bệnh nền" → "no"
- ✅ medication_changes: "Không có thay đổi thuốc"
- ✅ caffeine_nicotine_use: "Uống cà phê bình thường"

### 7. SUPPORT_COPING (2 slots)
- ✅ support_system: "Tôi có..."
- ✅ coping_mechanisms: "Tôi đang cố gắng... bằng cách..."

### 8. SCREENS (2 slots)
- ✅ mania_like_symptoms: "Tôi không có triệu chứng giống hưng cảm" → "no"
- ✅ psychotic_like_symptoms: "Tôi không có triệu chứng giống loạn thần" → "no"

**Tổng: 25 required slots**

---

## TEST SCRIPT

### Script để test và verify kết quả:

```bash
# 1. Test với test case nhẹ (expected score < 5)
# Copy query từ TEST CASE 1 và paste vào hệ thống
# Kiểm tra logs:
docker logs chatbot-backend --tail 100 | grep -E "\[SEVERITY DETECTION\]|\[SCORES\]|\[SEVERITY BOOST\]"

# 2. Test với test case nặng (expected score > 5.5)
# Copy query từ TEST CASE 6 và paste vào hệ thống
# Kiểm tra logs tương tự

# 3. Verify severity boost hoạt động:
docker logs chatbot-backend --tail 200 | grep -E "SEVERITY BOOST|weight.*→|SEVERITY DETECTION"

# 4. Check routing decision:
docker logs chatbot-backend --tail 50 | grep -E "\[ROUTING\]|assessment_category"

# 5. Check query rewrite có severity context words:
docker logs chatbot-backend --tail 100 | grep -E "\[QUERY\]|Rewritten:" | grep -i "mild\|severe\|profound"
```

### Metrics cần kiểm tra:

1. **Severity Detection:**
   - Query có "mild" → detect "mild"
   - Query có "severe/profound" → detect "severe"
   - Log: `[SEVERITY DETECTION] Query severity: mild/severe`

2. **Severity Boost:**
   - Case nhẹ: Items score 1-3 được boost (weight tăng 20%)
   - Case nhẹ: Items score 4-5 bị penalize (weight giảm 30%)
   - Case nặng: Items score 4-5 được boost (weight tăng 20%)
   - Case nặng: Items score 1-3 bị penalize (weight giảm 30%)
   - Log: `[SEVERITY BOOST] ... weight=0.6276 → 0.7531 (+20.0%)`

3. **Final Scores:**
   - Case nhẹ: adjustment_reaction_score < 5
   - Case nặng: adjustment_reaction_score > 5.5
   - Log: `[SCORES] normal_stress: X.XX, adjustment_reaction: X.XX`

4. **Routing:**
   - Case nhẹ: route đến normal_coping_retrieval hoặc adjustment_retrieval
   - Case nặng: route đến diagnostic_retrieval
   - Log: `[ROUTING] ✅ ... -> ...`

---

## HƯỚNG DẪN SỬ DỤNG

1. **Copy từng test case query** và paste vào hệ thống
2. **Kiểm tra logs** để xem:
   - Severity detection có đúng không
   - Severity boost có được apply không
   - Scores được tính như thế nào
   - Top items match được
   - Routing decision
3. **So sánh với expected results** để đánh giá

## CÁC METRICS CẦN KIỂM TRA

1. **Scores:**
   - normal_stress_score
   - adjustment_reaction_score
   - So sánh với expected scores

2. **Routing:**
   - assessment_category
   - Route đến node nào (normal_coping_retrieval, adjustment_retrieval, diagnostic_retrieval)

3. **Logs:**
   - [SEVERITY DETECTION] Query severity detected
   - [SEVERITY BOOST] Items được boost/penalize
   - [FILTER] Total reranked items vs Items after similarity filter
   - [SCORES] Final scores
   - [TOP ITEMS] Top 3 items của mỗi type với score, weight, contribution

## ĐIỀU CHỈNH THRESHOLD

Nếu sau khi test, scores không phản ánh đúng mức độ nghiêm trọng:
- Điều chỉnh `SIMILARITY_THRESHOLD` (hiện tại 0.5)
- Điều chỉnh `THRESHOLD` routing (hiện tại 5.5)

## LƯU Ý VỀ EXPECTED SCORES (SAU MAPPING + SEVERITY BOOST)

### Thay đổi trong data:
- **Generic symptoms** (Depressed mood, Anxiety, Dysphoria, Apathy): score 5 → **3**
- **Severe mood symptoms** (Anhedonia, Hopelessness, Avolition, Demoralization): score 5 → **4**
- **Severe symptoms** (psychotic/cognitive/neurological): score **5** (giữ nguyên)
- **Normal stress items**: score -1 → **1-2** (tăng)

### Severity Boost Logic (Option 2 + 4):
- **Query rewrite**: Tự động thêm severity context words (mild, moderate, severe, profound)
- **Severity detection**: Detect severity từ query keywords
- **Boost/Penalty**:
  - **Mild query**: Boost items score 1-3 (weight * 1.2), penalize items score 4-5 (weight * 0.7)
  - **Severe query**: Boost items score 4-5 (weight * 1.2), penalize items score 1-3 (weight * 0.7)
  - **Moderate/Unknown**: Không boost/penalty

### Ảnh hưởng đến expected scores:
- **Case nhẹ**: 
  - Score thấp hơn (~2-3) vì:
    - Generic symptoms giảm từ 5 → 3
    - Items score 3 được boost (tăng contribution)
    - Items score 5 bị penalize (giảm contribution)
- **Case vừa**: 
  - Score ~3-4 vì:
    - Generic symptoms giảm từ 5 → 3
    - Không có boost/penalty (moderate/unknown)
- **Case nặng**: 
  - Score cao hơn (~5-6) vì:
    - Match nhiều severe symptoms (score 5)
    - Items score 4-5 được boost (tăng contribution)
    - Items score 3 bị penalize (giảm contribution)
- **Normal stress**: Có contribution tốt hơn (score 1-2 thay vì 0)

### Threshold routing:
- Threshold vẫn là **5.5**
- Case nhẹ: Score < 5 → route đến normal_coping hoặc adjustment_retrieval
- Case nặng: Score > 5.5 → route đến diagnostic_retrieval
- Severity boost giúp phân biệt rõ hơn giữa case nhẹ và nặng

### Cần test lại:
- Scores có thể dao động tùy theo items match được từ normal_responses.jsonl
- Severity boost có thể cần điều chỉnh multipliers (hiện tại 1.2x và 0.7x)
- Cần test nhiều lần để xác nhận consistency
- Có thể cần điều chỉnh threshold nếu scores không phản ánh đúng mức độ nghiêm trọng
