import os
import sys
from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate


from api_key_manager import APIKeyManager, load_api_keys_from_file, load_api_keys_by_lines

class GeminiTranslator:
    """
    Translator chuyên dụng cho tư vấn tâm lý:
    - VI -> EN: Dịch câu hỏi của người dùng gửi đến bác sĩ
    - EN -> VI: Dịch câu trả lời của bác sĩ tâm lý
    - Sử dụng LangChain ChatGoogleGenerativeAI với ApiKeyManager
    """
    
    def __init__(
        self, 
        keys_file: str = "../Input/api_key_respone.txt",
        apikey_lines: str = None,
        model_name: str = "gemini-2.5-flash-lite",
        min_delay_between_calls: float = 15.0
    ):
        """
        Args:
            keys_file: Đường dẫn file chứa API keys
            apikey_lines: Chọn dòng cụ thể (vd: "1-10,15,20-25"). None = load tất cả
            model_name: Tên model Gemini
            min_delay_between_calls: Delay tối thiểu giữa các calls (giây)
        """
        # Load API keys từ file
        if apikey_lines:
            API_KEYS = load_api_keys_by_lines(keys_file, apikey_lines)
            print(f"[KEYS] Loaded {len(API_KEYS)} keys from {keys_file} using lines {apikey_lines}")
        else:
            API_KEYS = load_api_keys_from_file(keys_file)
            print(f"[KEYS] Loaded {len(API_KEYS)} keys from {keys_file}")
        
        # Khởi tạo APIKeyManager với automatic rotation
        self.key_manager = APIKeyManager(API_KEYS, min_delay_between_calls=min_delay_between_calls)
        self.model_name = model_name
        self.max_attempts = 5
        
        # Prompt templates
        self.question_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional medical translator specializing in mental health consultation.

            **Task:** Translate this Vietnamese patient question to English for a mental health professional.

            **Guidelines:**
            - Use clear, respectful, professional English
            - Preserve emotional tone and urgency
            - Keep medical/psychological terms accurate
            - Maintain the patient's voice and concerns
            - Only return the translated question, no explanations"""),
                        ("user", "{vietnamese_question}")
                    ])
        
        self.answer_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Vietnamese mental health counselor having a genuine conversation with a patient.

            **Task:** Transform this English mental health response into natural, conversational Vietnamese — as if you're personally speaking to them face-to-face.

            **Guidelines:**
            - Write like a **real conversation**, not a word-by-word translation
            - Use **warm, empathetic tone** like a caring friend or counselor
            - Express ideas the way **Vietnamese people naturally speak**, not literal translations
            - Make medical/psychological terms **simple and relatable**
            - Use natural Vietnamese pronouns: "bạn", "mình", "anh/chị" based on context
            - Add conversational particles like "nhé", "nha", "đấy", "thôi" when appropriate to sound human
            - Preserve the supportive intent, but make it feel **genuinely Vietnamese**
            - **Return only the Vietnamese text**, no explanations or notes
            """),
                ("user", "{english_answer}")
            ])

    
    def _generate_with_retry(self, prompt: ChatPromptTemplate, input_vars: dict) -> str:
        """
        Gọi Gemini với retry logic và automatic key rotation
        """
        last_exc = None
        for attempt in range(self.max_attempts):
            try:
                # Lấy key khả dụng (automatic rotation)
                api_key = self.key_manager.get_next_key()
                
                # Tạo LLM với key hiện tại
                llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=api_key,
                    temperature=0.3
                )
                
                # Gọi chain
                chain = prompt | llm
                response = chain.invoke(input_vars)
                
                # Mark success (reset error count)
                self.key_manager.mark_success(api_key)
                
                return response.content.strip()
                
            except Exception as e:
                last_exc = e
                error_msg = str(e).lower()
                
                # Kiểm tra lỗi 429 hoặc quota
                if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg or "resourceexhausted" in error_msg:
                    self.key_manager.handle_error(api_key, 429, error_msg)
                    print(f"⚠️ Key {api_key[:12]}... hit rate limit (429)")
                    continue
                elif "401" in error_msg or "403" in error_msg:
                    status_code = 401 if "401" in error_msg else 403
                    self.key_manager.handle_error(api_key, status_code, error_msg)
                    print(f"⚠️ Key {api_key[:12]}... authentication error ({status_code})")
                    continue
                else:
                    # Lỗi khác -> raise ngay
                    raise
        
        raise RuntimeError(f"Translation failed after {self.max_attempts} attempts: {last_exc}")
    
    def translate_question(self, vietnamese_question: str) -> str:
        """
        Dịch câu hỏi từ tiếng Việt sang tiếng Anh
        
        Args:
            vietnamese_question: Câu hỏi của người dùng bằng tiếng Việt
        
        Returns:
            Câu hỏi đã dịch sang tiếng Anh
        """
        return self._generate_with_retry(
            self.question_prompt, 
            {"vietnamese_question": vietnamese_question}
        )
    
    def translate_answer(self, english_answer: str) -> str:
        """
        Dịch câu trả lời của bác sĩ từ tiếng Anh sang tiếng Việt
        
        Args:
            english_answer: Câu trả lời của bác sĩ tâm lý bằng tiếng Anh
        
        Returns:
            Câu trả lời đã dịch sang tiếng Việt
        """
        return self._generate_with_retry(
            self.answer_prompt,
            {"english_answer": english_answer}
        )
    
    def vi_to_en(self, text: str) -> str:
        """Alias: Dịch câu hỏi VI -> EN"""
        return self.translate_question(text)
    
    def en_to_vi(self, text: str) -> str:
        """Alias: Dịch câu trả lời EN -> VI"""
        return self.translate_answer(text)

