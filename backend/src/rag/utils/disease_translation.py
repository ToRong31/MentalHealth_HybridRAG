"""
Disease Name Translation
Mapping English disease names to Vietnamese
"""

# Mapping: English disease name -> Vietnamese translation
DISEASE_NAME_TRANSLATION = {
    # Mood Disorders
    "Bipolar and Related Disorders": "Rối loạn Lưỡng cực và các rối loạn liên quan",
    "Bipolar Disorder": "Rối loạn Lưỡng cực",
    "Bipolar I Disorder": "Rối loạn Lưỡng cực loại I",
    "Bipolar II Disorder": "Rối loạn Lưỡng cực loại II",
    "Cyclothymic Disorder": "Rối loạn Cyclothymic",
    
    # Depressive Disorders
    "Depressive Disorders": "Các rối loạn Trầm cảm",
    "Depressive Disorder": "Rối loạn Trầm cảm",
    "Major Depressive Disorder": "Rối loạn Trầm cảm nặng",
    "Persistent Depressive Disorder": "Rối loạn Trầm cảm dai dẳng",
    "Dysthymia": "Trầm cảm nhẹ kéo dài",
    "Premenstrual Dysphoric Disorder": "Rối loạn Khó chịu tiền kinh nguyệt",
    "Disruptive Mood Dysregulation Disorder": "Rối loạn Mất kiểm soát Tâm trạng",
    
    # Anxiety Disorders
    "Anxiety Disorders": "Các rối loạn Lo âu",
    "Anxiety Disorder": "Rối loạn Lo âu",
    "Generalized Anxiety Disorder": "Rối loạn Lo âu lan tỏa",
    "Panic Disorder": "Rối loạn Hoảng sợ",
    "Social Anxiety Disorder": "Rối loạn Lo âu Xã hội",
    "Specific Phobia": "Ám ảnh Cụ thể",
    "Agoraphobia": "Sợ Không gian Rộng",
    "Separation Anxiety Disorder": "Rối loạn Lo âu Chia ly",
    
    # OCD and Related
    "Obsessive-Compulsive Disorder": "Rối loạn Ám ảnh Cưỡng chế",
    "OCD": "Rối loạn Ám ảnh Cưỡng chế",
    "Body Dysmorphic Disorder": "Rối loạn Hình thể",
    "Hoarding Disorder": "Rối loạn Tích trữ",
    "Trichotillomania": "Rối loạn Nhổ tóc",
    "Excoriation Disorder": "Rối loạn Bóc da",
    
    # Trauma and Stressor-Related
    "Post-Traumatic Stress Disorder": "Rối loạn Căng thẳng sau Chấn thương",
    "PTSD": "Rối loạn Căng thẳng sau Chấn thương",
    "Acute Stress Disorder": "Rối loạn Căng thẳng Cấp tính",
    "Adjustment Disorders": "Rối loạn Thích nghi",
    "Adjustment Disorder": "Rối loạn Thích nghi",
    
    # Eating Disorders
    "Eating Disorders": "Rối loạn Ăn uống",
    "Anorexia Nervosa": "Chứng Biếng ăn Tâm thần",
    "Bulimia Nervosa": "Chứng Ăn vô độ",
    "Binge-Eating Disorder": "Rối loạn Ăn vô độ",
    "Avoidant/Restrictive Food Intake Disorder": "Rối loạn Hạn chế Thức ăn",
    
    # Sleep Disorders
    "Sleep Disorders": "Rối loạn Giấc ngủ",
    "Insomnia Disorder": "Rối loạn Mất ngủ",
    "Hypersomnolence Disorder": "Rối loạn Ngủ quá nhiều",
    "Narcolepsy": "Chứng Ngủ rũ",
    
    # Schizophrenia Spectrum
    "Schizophrenia Spectrum and Other Psychotic Disorders": "Phổ Tâm thần phân liệt và các rối loạn Loạn thần khác",
    "Schizophrenia": "Tâm thần phân liệt",
    "Schizoaffective Disorder": "Rối loạn Tâm thần-Cảm xúc",
    "Brief Psychotic Disorder": "Rối loạn Loạn thần Ngắn hạn",
    "Delusional Disorder": "Rối loạn Hoang tưởng",
    
    # Personality Disorders
    "Personality Disorders": "Rối loạn Nhân cách",
    "Borderline Personality Disorder": "Rối loạn Nhân cách Biên giới",
    "Antisocial Personality Disorder": "Rối loạn Nhân cách Chống xã hội",
    "Narcissistic Personality Disorder": "Rối loạn Nhân cách Tự ái",
    "Avoidant Personality Disorder": "Rối loạn Nhân cách Né tránh",
    "Dependent Personality Disorder": "Rối loạn Nhân cách Phụ thuộc",
    "Obsessive-Compulsive Personality Disorder": "Rối loạn Nhân cách Cưỡng bức Hoàn hảo",
    
    # Substance-Related
    "Substance-Related and Addictive Disorders": "Rối loạn liên quan đến Chất gây nghiện và Nghiện",
    "Alcohol Use Disorder": "Rối loạn Sử dụng Rượu",
    "Substance Use Disorder": "Rối loạn Sử dụng Chất gây nghiện",
    
    # Neurodevelopmental
    "Attention-Deficit/Hyperactivity Disorder": "Rối loạn Thiếu tập trung/Tăng động",
    "ADHD": "Rối loạn Thiếu tập trung/Tăng động",
    "Autism Spectrum Disorder": "Rối loạn Phổ Tự kỷ",
    
    # Dissociative
    "Dissociative Disorders": "Rối loạn Phân ly",
    "Dissociative Identity Disorder": "Rối loạn Đa nhân cách",
    "Dissociative Amnesia": "Mất trí nhớ Phân ly",
    "Depersonalization/Derealization Disorder": "Rối loạn Mất cảm giác bản thân/Mất cảm giác thực tại",
    
    # Somatic
    "Somatic Symptom and Related Disorders": "Rối loạn Triệu chứng Cơ thể và các rối loạn liên quan",
    "Somatic Symptom Disorder": "Rối loạn Triệu chứng Cơ thể",
    "Illness Anxiety Disorder": "Rối loạn Lo âu về Bệnh tật",
    "Conversion Disorder": "Rối loạn Chuyển hóa",
    
    # Other common terms
    "Mental Health": "Sức khỏe Tâm thần",
    "Mental Health Condition": "Tình trạng Sức khỏe Tâm thần",
    "Mental Health Issue": "Vấn đề Sức khỏe Tâm thần",
    "Mental Illness": "Bệnh Tâm thần",
    "Psychological Disorder": "Rối loạn Tâm lý",
}


def translate_disease_name(english_name: str) -> str:
    """
    Translate disease name from English to Vietnamese.
    
    Args:
        english_name: Disease name in English
        
    Returns:
        Vietnamese translation if available, otherwise original English name
    """
    if not english_name:
        return ""
    
    # Try exact match first
    if english_name in DISEASE_NAME_TRANSLATION:
        return DISEASE_NAME_TRANSLATION[english_name]
    
    # Try case-insensitive match
    for eng, vie in DISEASE_NAME_TRANSLATION.items():
        if eng.lower() == english_name.lower():
            return vie
    
    # Try partial match (for plural/singular variations)
    english_lower = english_name.lower()
    for eng, vie in DISEASE_NAME_TRANSLATION.items():
        eng_lower = eng.lower()
        # Check if one is contained in the other
        if (english_lower in eng_lower or eng_lower in english_lower) and len(english_lower) > 5:
            return vie
    
    # No translation found, return original
    return english_name


def translate_disease_list(disease_list: list) -> list:
    """
    Translate a list of disease names from English to Vietnamese.
    
    Args:
        disease_list: List of disease names in English
        
    Returns:
        List of Vietnamese translations
    """
    return [translate_disease_name(disease) for disease in disease_list]
