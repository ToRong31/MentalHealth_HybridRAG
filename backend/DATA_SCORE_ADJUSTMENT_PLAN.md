# KỊCH BẢN THAY ĐỔI SCORE TRONG normal_responses.jsonl

## MỤC TIÊU

1. **Giảm điểm cho nhóm "nhạy" (generic symptoms)** - Các symptom rất phổ biến, dễ match cả case nhẹ lẫn nặng
2. **Giữ nguyên điểm cho nhóm "đặc trưng" (severe symptoms)** - Các symptom thực sự nghiêm trọng, đặc hiệu
3. **Tăng điểm cho normal_stress items** - Để normal_stress có "tiếng nói" trong assessment, không bị adjustment_reaction nuốt hết
4. **Giữ nguyên emergency items (score 99)** - Code đã cap thành 10, không cần sửa

## THỐNG KÊ HIỆN TẠI

- **Total items**: 226
- **Adjustment reaction score=5**: 90 items (cần phân loại)
- **Normal stress score=-1**: 31 items (cần tăng lên 1-2)
- **Emergency score=99**: 22 items (giữ nguyên)

## QUY TẮC MAPPING

### 1. ADJUSTMENT REACTION - GIẢM ĐIỂM (5 → 3)

**Nhóm Generic Mood/Affect Symptoms** - Rất phổ biến, dễ match cả case nhẹ:
- `MB24.5` - Depressed mood: **5 → 3**
- `MB24.3` - Anxiety: **5 → 3**
- `MB24.7` - Dysphoria: **5 → 3**
- `MB24.4` - Apathy: **5 → 3**
- `MB24.6` - Disturbance of affect: **5 → 3**

**Lý do**: Đây là các symptom rất rộng, có thể xuất hiện ở cả case nhẹ (stress bình thường) và case nặng. Nếu giữ score 5, case nhẹ dễ bị "đội điểm" lên 5.0.

---

### 2. ADJUSTMENT REACTION - GIẢM ĐIỂM (5 → 4)

**Nhóm Severe Mood/Affect Symptoms** - Nghiêm trọng hơn nhưng vẫn có thể xuất hiện ở case vừa:
- `MB24.2` - Anhedonia: **5 → 4**
- `MB22.2` - Demoralization: **5 → 4**
- `MB22.3` - Hopelessness: **5 → 4**
- `MB22.0` - Avolition: **5 → 4**

**Lý do**: Các symptom này nghiêm trọng hơn generic mood, nhưng vẫn không đủ "đặc trưng" như psychotic symptoms. Giảm xuống 4 để phân biệt với nhóm đặc trưng (giữ 5).

---

### 3. ADJUSTMENT REACTION - GIỮ NGUYÊN (5)

**Nhóm Psychotic/Cognitive/Neurological Severe Symptoms** - Đặc trưng, chỉ xuất hiện ở case nặng:

**Psychotic Symptoms:**
- `MB26.0` - Delusion: **5** (giữ)
- `MB26.1` - Experiences of influence, passivity, and control: **5** (giữ)
- `MB27.0` - Depersonalisation: **5** (giữ)
- `MB27.1` - Derealisation: **5** (giữ)
- `MB27.2` - Hallucinations: **5** (giữ)
- `MB26.4` - Identity disturbance: **5** (giữ)

**Thought Disorder:**
- `MB25.0` - Symptoms or signs of thought disorder: **5** (giữ)
- `MB25.1` - Flight of ideas: **5** (giữ)
- `MB25.2` - Neologisms: **5** (giữ)
- `MB25.3` - Thought blocking: **5** (giữ)

**Severe Cognitive Impairment:**
- `MB21.1` - Amnesia: **5** (giữ)
- `MB21.2` - Anosognosia: **5** (giữ)
- `MB21.3` - Confabulation: **5** (giữ)
- `MB21.4` - Disorientation: **5** (giữ)
- `MB21.5` - Distractibility: **5** (giữ)
- `MB21.6` - Impaired abstract thinking: **5** (giữ)
- `MB21.7` - Impaired executive functioning: **5** (giữ)
- `MB21.8` - Impaired judgment: **5** (giữ)
- `MB21.9` - Perseveration: **5** (giữ)
- `MB20.2` - Clouding of consciousness: **5** (giữ)

**Severe Behavioral Symptoms:**
- `MB23.0` - Aggressive behaviour: **5** (giữ)
- `MB23.1` - Antisocial behaviour: **5** (giữ)
- `MB23.3` - Bradyphrenia: **5** (giữ)
- `MB23.4` - Compulsions: **5** (giữ)
- `MB23.5` - Coprolalia: **5** (giữ)
- `MB23.6` - Disorganised behaviour: **5** (giữ)
- `MB23.9` - Echolalia: **5** (giữ)
- `MB24.9` - Euphoria: **5** (giữ)
- `MB26.2` - Grandiosity: **5** (giữ)
- `MB26.5` - Obsessions: **5** (giữ)
- `MB29.3` - Purging behaviour: **5** (giữ)

**Neurological Severe Symptoms:**
- `MB40.0` - Asomatognosia: **5** (giữ)
- `MB40.1` - Allodynia: **5** (giữ)
- `MB40.2` - Anacusis: **5** (giữ)
- `MB40.3` - Anaesthesia of skin: **5** (giữ)
- `MB40.5` - Hyperaesthesia: **5** (giữ)
- `MB40.6` - Dysesthesia: **5** (giữ)
- `MB40.7` - Acroparaesthesia: **5** (giữ)
- `MB40.9` - Neurological neglect syndrome: **5** (giữ)
- `MB41.0` - Anosmia: **5** (giữ)
- `MB41.1` - Parosmia: **5** (giữ)
- `MB41.2` - Dysgeusia: **5** (giữ)
- `MB41.3` - Hyposmia: **5** (giữ)
- `MB44.0` - Ataxic gait: **5** (giữ)
- `MB44.2` - Difficulty in walking: **5** (giữ)
- `MB45.1` - Automatism: **5** (giữ)
- `MB45.3` - Head drop: **5** (giữ)
- `MB45.4` - Intention tremor: **5** (giữ)
- `MB46.0` - Asterixis: **5** (giữ)
- `MB46.1` - Abnormal head movements: **5** (giữ)
- `MB46.2` - Athetosis: **5** (giữ)
- `MB46.4` - Titubation: **5** (giữ)
- `MB47.0` - Abnormal reflex: **5** (giữ)
- `MB47.1` - Abnormal posture: **5** (giữ)
- `MB47.2` - Clonus: **5** (giữ)
- `MB47.4` - Dystonia: **5** (giữ)
- `MB47.5` - Fasciculation: **5** (giữ)
- `MB47.6` - Meningismus: **5** (giữ)
- `MB47.7` - Muscle fibrillation: **5** (giữ)
- `MB47.8` - Muscular hypertonia: **5** (giữ)
- `MB47.9` - Myotonia: **5** (giữ)
- `MB48.1` - Disorder of equilibrium: **5** (giữ)
- `MB4A` - Apraxia: **5** (giữ)
- `MB4B.0` - Dyslexia and alexia: **5** (giữ)
- `MB4B.1` - Agnosia: **5** (giữ)
- `MB4B.2` - Acalculia: **5** (giữ)
- `MB4B.3` - Agraphia: **5** (giữ)
- `MB4B.4` - Anomia: **5** (giữ)
- `MB4B.5` - Dyscalculia: **5** (giữ)
- `MB4C` - Gerstmann syndrome: **5** (giữ)
- `MB70.0` - Abnormal level of enzymes in cerebrospinal fluid: **5** (giữ)
- `MB70.1` - Abnormal level of hormones in cerebrospinal fluid: **5** (giữ)
- `MB70.2` - Abnormal level of drugs...: **5** (giữ)
- `MB70.3` - Abnormal level of substances chiefly nonmedicinal...: **5** (giữ)
- `MB70.4` - Abnormal immunological findings in cerebrospinal fluid: **5** (giữ)
- `MB70.5` - Abnormal microbiological findings in cerebrospinal fluid: **5** (giữ)
- `MB70.6` - Abnormal cytological findings in cerebrospinal fluid: **5** (giữ)
- `MB70.7` - Abnormal histological findings in cerebrospinal fluid: **5** (giữ)
- `MB70.8` - Other abnormal findings in cerebrospinal fluid: **5** (giữ)
- `MB72` - Results of function studies of the nervous system: **5** (giữ)

**Lý do**: Đây là các symptom thực sự nghiêm trọng, đặc trưng cho case nặng. Giữ score 5 để case nặng có thể đạt được weighted average > 5.0 khi match được nhiều items này.

---

### 4. ADJUSTMENT REACTION - GIỮ NGUYÊN (99)

**Emergency Items** - Code đã cap thành 10, không cần sửa:
- `MB20.0` - Stupor: **99** (giữ)
- `MB20.1` - Coma: **99** (giữ)
- `MB26.3` - Homicidal ideation: **99** (giữ)
- `MB40.8` - Analgesia: **99** (giữ)
- `MB44.1` - Paralytic gait: **99** (giữ)
- `MB44.3` - Immobility: **99** (giữ)
- `MB45.2` - Atonia: **99** (giữ)
- `MB46.3` - Drop attack: **99** (giữ)
- `MB50.0` - Flaccid tetraplegia: **99** (giữ)
- `MB50.1` - Spastic tetraplegia: **99** (giữ)
- `MB51.0` - Flaccid diplegia of upper extremities: **99** (giữ)
- `MB51.1` - Spastic diplegia of upper extremities: **99** (giữ)
- `MB52` - Diplegia of lower extremities: **99** (giữ)
- `MB53.0` - Alternating hemiplegia: **99** (giữ)
- `MB53.1` - Flaccid hemiplegia: **99** (giữ)
- `MB53.2` - Spastic hemiplegia: **99** (giữ)
- `MB54.0` - Flaccid monoplegia of upper extremity: **99** (giữ)
- `MB54.1` - Spastic monoplegia of upper extremity: **99** (giữ)
- `MB55.0` - Flaccid monoplegia of lower extremity: **99** (giữ)
- `MB55.1` - Spastic monoplegia of lower extremity: **99** (giữ)
- `MB56` - Paraplegia: **99** (giữ)
- `MB71.0` - Intracranial space-occupying lesion: **99** (giữ)

**Lý do**: Code đã xử lý score 99 bằng cách cap thành 10 trong weighted average. Không cần sửa.

---

### 5. NORMAL STRESS - TĂNG ĐIỂM (-1 → 2)

**Nhóm Stress Events Nặng** - Sự kiện stress nghiêm trọng nhưng vẫn trong phạm vi "normal stress":
- `QE62` - Uncomplicated bereavement: **-1 → 2**
- `QE84` - Acute stress reaction: **-1 → 2**
- `QE80` - Victim of crime or terrorism: **-1 → 2**
- `QE81` - Exposure to disaster, war or other hostilities: **-1 → 2**
- `QE61.0` - Loss or death of child: **-1 → 2**

**Lý do**: Đây là các sự kiện stress nghiêm trọng nhưng vẫn được coi là "normal stress" (phản ứng bình thường với sự kiện bất thường). Tăng lên 2 để normal_stress có "tiếng nói" trong assessment.

---

### 6. NORMAL STRESS - TĂNG ĐIỂM (-1 → 1)

**Nhóm Stress Context** - Bối cảnh khó khăn, thiếu hỗ trợ:
- `QE30.0` - Insufficient social insurance support, aged: **-1 → 1**
- `QE30.1` - Insufficient social insurance support, disability: **-1 → 1**
- `QE30.2` - Insufficient social insurance support, unemployment: **-1 → 1**
- `QE30.3` - Insufficient social insurance support, family support: **-1 → 1**
- `QE31.0` - Insufficient social welfare support, child protection: **-1 → 1**
- `QE31.1` - Insufficient social welfare support, protection against domestic violence: **-1 → 1**
- `QE31.2` - Insufficient social welfare support, protection against homelessness: **-1 → 1**
- `QE31.3` - Insufficient social welfare support, post prison services: **-1 → 1**
- `QE40` - Problem associated with conviction in civil or criminal proceedings: **-1 → 1**
- `QE41` - Problem associated with imprisonment and other incarceration: **-1 → 1**
- `QE42` - Problem associated with release from prison: **-1 → 1**
- `QE82.0` - Personal history of physical abuse: **-1 → 1**
- `QE82.1` - Personal history of sexual abuse: **-1 → 1**
- `QE82.2` - Personal history of psychological abuse: **-1 → 1**
- `QE82.3` - Personal history of neglect: **-1 → 1**
- `QE83` - Personal frightening experience in childhood: **-1 → 1**
- `QE90` - Inadequate parental supervision or control: **-1 → 1**
- `QE91` - Parental overprotection: **-1 → 1**
- `QE92` - Altered pattern of family relationships in childhood: **-1 → 1**
- `QE93` - Removal from home in childhood: **-1 → 1**
- `QE94` - Institutional upbringing: **-1 → 1**
- `QE95` - Inappropriate parental pressure: **-1 → 1**
- `QE96` - Events resulting in loss of self-esteem in childhood: **-1 → 1**
- `QE60` - Absence of family member: **-1 → 1**
- `QE52.1` - Loss of love relationship in childhood: **-1 → 1**

**Lý do**: Đây là các bối cảnh khó khăn, thiếu hỗ trợ xã hội, nhưng không phải là "symptom" bệnh lý. Tăng lên 1 để normal_stress có contribution trong assessment, không bị adjustment_reaction nuốt hết.

---

### 7. CÁC ITEMS KHÁC - GIỮ NGUYÊN

Tất cả các items không được liệt kê ở trên sẽ **giữ nguyên score hiện tại**.

---

## TỔNG KẾT THAY ĐỔI

### Adjustment Reaction:
- **5 → 3**: 5 items (generic mood/affect)
- **5 → 4**: 4 items (severe mood/affect)
- **5 → 5**: ~81 items (psychotic/cognitive/neurological severe)
- **99 → 99**: 22 items (emergency, giữ nguyên)

### Normal Stress:
- **-1 → 2**: 5 items (stress events nặng)
- **-1 → 1**: 26 items (stress context)
- **-1 → -1**: 0 items (không có item nào giữ -1 sau khi điều chỉnh)

---

## KẾT QUẢ MONG ĐỢI

Sau khi áp dụng mapping:

1. **Case nhẹ**: 
   - Match chủ yếu generic symptoms (score 3) → weighted average ~3-4
   - Không vượt threshold 5-5.5

2. **Case nặng**:
   - Match nhiều severe symptoms (score 5) + có thể có emergency (cap 10)
   - Weighted average ~5-6, vượt threshold 5-5.5

3. **Normal stress**:
   - Có contribution (score 1-2) thay vì 0
   - Có thể "cạnh tranh" với adjustment_reaction trong một số trường hợp

---

## CÁCH THỰC HIỆN

### Bước 1: Backup
```bash
cp backend/data/raw/normal_responses.jsonl backend/data/raw/normal_responses_orig.jsonl
```

### Bước 2: Tạo script Python để apply mapping
- Đọc file `normal_responses.jsonl`
- Apply mapping theo kịch bản trên
- Ghi ra file mới `normal_responses_v2.jsonl`

### Bước 3: Test
- Test với các test cases hiện có
- Kiểm tra xem case nhẹ có score < 5, case nặng có score > 5.5 không

### Bước 4: Deploy
- Nếu test OK, thay thế file gốc hoặc update code để point đến file mới

---

## LƯU Ý

1. **Threshold**: Giữ nguyên 5-5.5 như yêu cầu
2. **Emergency items**: Không sửa (code đã cap thành 10)
3. **Rollback**: Luôn có backup để rollback nếu cần
4. **Test**: Phải test kỹ với các test cases trước khi deploy


