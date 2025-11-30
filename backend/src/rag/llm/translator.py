import os
from typing import Optional

import yaml  # nhớ: pip install pyyaml

from src.rag.llm.llm_gemini import LLMClient

from src.rag.config import GEMINI_MODEL_NAME

class GeminiTranslator(LLMClient):
    """
    Translator chuyên dụng cho tư vấn tâm lý, kế thừa trực tiếp từ LLMClient.
    Prompts được load từ YAML.
    """

    def __init__(
        self,
        model_name: str = GEMINI_MODEL_NAME,
        default_max_retries: int = 3,
        prompt_config_path: str = "src/prompts/translator_prompts.yaml",
    ):
        # Khởi tạo LLMClient (key_manager, model_name, ...)
        super().__init__(model_name=model_name)

        self.default_max_retries = default_max_retries
        self._question_prompt_template = ""
        self._answer_prompt_template = ""

        self._load_prompts(prompt_config_path)

    # ------------------- PROMPT LOADING ------------------- #

    def _load_prompts(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Fallback nhẹ nếu thiếu field trong YAML
        self._question_prompt_template = data.get("question_prompt", "").strip()
        self._answer_prompt_template = data.get("answer_prompt", "").strip()

        if not self._question_prompt_template:
            raise ValueError("question_prompt is missing or empty in YAML config")

        if not self._answer_prompt_template:
            raise ValueError("answer_prompt is missing or empty in YAML config")

    # ------------------- INTERNAL LLM CALL ------------------- #

    def _invoke_llm(self, prompt: str, max_retries: Optional[int] = None) -> str:
        retries = max_retries if max_retries is not None else self.default_max_retries
        response = self.invoke(prompt, max_retries=retries)
        return response.strip() if response else ""

    # ------------------- PUBLIC API ------------------- #

    def translate_question(self, vietnamese_question: str, max_retries: Optional[int] = None) -> str:
        """
        Dịch câu hỏi từ tiếng Việt sang tiếng Anh
        """
        if not vietnamese_question or not vietnamese_question.strip():
            raise ValueError("vietnamese_question cannot be empty")

        prompt = self._question_prompt_template.format(
            vietnamese_question=vietnamese_question.strip()
        )
        return self._invoke_llm(prompt, max_retries=max_retries)

    def translate_answer(self, english_answer: str, max_retries: Optional[int] = None) -> str:
        """
        Dịch câu trả lời của bác sĩ từ tiếng Anh sang tiếng Việt
        """
        if not english_answer or not english_answer.strip():
            raise ValueError("english_answer cannot be empty")

        prompt = self._answer_prompt_template.format(
            english_answer=english_answer.strip()
        )
        return self._invoke_llm(prompt, max_retries=max_retries)

    def vi_to_en(self, text: str) -> str:
        """Alias: Dịch câu hỏi VI -> EN"""
        print(f"Dịch câu hỏi VI -> EN: {text}")
        return self.translate_question(text)

    def en_to_vi(self, text: str) -> str:
        """Alias: Dịch câu trả lời EN -> VI"""
        print(f"Dịch câu trả lời EN -> VI: {text}")
        return self.translate_answer(text)

    # ------------------- LANGUAGE DETECTION ------------------- #

    @staticmethod
    def is_english(text: str) -> bool:
        if not text:
            return True
        non_ascii = sum(1 for c in text if ord(c) > 127)
        return non_ascii / len(text) < 0.1

    @staticmethod
    def detect_language(text: str) -> str:
        return "en" if GeminiTranslator.is_english(text) else "vi"


# Singleton
_translator_instance: Optional[GeminiTranslator] = None


def get_translator() -> GeminiTranslator:
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = GeminiTranslator()
    return _translator_instance
