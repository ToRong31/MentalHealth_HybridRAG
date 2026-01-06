import os
from typing import Optional
import asyncio

import yaml  # nhớ: pip install pyyaml
import aiofiles

from src.rag.llm.llm_gemini import LLMClient

from src.rag.config import rag_settings

class GeminiTranslator(LLMClient):
    """
    Translator chuyên dụng cho tư vấn tâm lý, kế thừa trực tiếp từ LLMClient.
    Prompts được load từ YAML.
    """

    def __init__(
        self,
        model_name: str = rag_settings.GEMINI_MODEL_NAME,
        default_max_retries: int = 3,
        prompt_config_path: str = "src/rag/prompts/translator_prompts.yaml",
    ):
        # Khởi tạo LLMClient (key_manager, model_name, ...)
        super().__init__(model_name=model_name)

        self.default_max_retries = default_max_retries
        self._question_prompt_template = ""
        self._answer_prompt_template = ""
        self._prompt_config_path = prompt_config_path
        self._prompts_loaded = False

        # Load prompts synchronously in a thread to avoid blocking
        # Will be loaded on first use if not already loaded
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop is running, schedule the load
                asyncio.create_task(self._ensure_prompts_loaded())
            else:
                # If no event loop, load synchronously (fallback)
                loop.run_until_complete(self._load_prompts(prompt_config_path))
                self._prompts_loaded = True
        except RuntimeError:
            # No event loop available, will load on first use
            pass

    # ------------------- PROMPT LOADING ------------------- #

    async def _load_prompts(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt config file not found: {path}")

        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
            data = yaml.safe_load(content) or {}

        # Fallback nhẹ nếu thiếu field trong YAML
        self._question_prompt_template = data.get("question_prompt", "").strip()
        self._answer_prompt_template = data.get("answer_prompt", "").strip()

        if not self._question_prompt_template:
            raise ValueError("question_prompt is missing or empty in YAML config")

        if not self._answer_prompt_template:
            raise ValueError("answer_prompt is missing or empty in YAML config")
        
        self._prompts_loaded = True

    async def _ensure_prompts_loaded(self):
        """Ensure prompts are loaded before use"""
        if not self._prompts_loaded:
            await self._load_prompts(self._prompt_config_path)

    # ------------------- INTERNAL LLM CALL ------------------- #

    def _invoke_llm(self, prompt: str, max_retries: Optional[int] = None) -> str:
        retries = max_retries if max_retries is not None else self.default_max_retries
        response = self.invoke(prompt, max_retries=retries)
        return response.strip() if response else ""

    # ------------------- PUBLIC API (SYNC) ------------------- #

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

    # ------------------- PUBLIC API (ASYNC) ------------------- #

    async def translate_question_async(self, vietnamese_question: str, max_retries: Optional[int] = None) -> str:
        """
        Dịch câu hỏi từ tiếng Việt sang tiếng Anh (async version)
        """
        await self._ensure_prompts_loaded()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.translate_question(vietnamese_question, max_retries)
        )

    async def translate_answer_async(self, english_answer: str, max_retries: Optional[int] = None) -> str:
        """
        Dịch câu trả lời của bác sĩ từ tiếng Anh sang tiếng Việt (async version)
        """
        await self._ensure_prompts_loaded()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.translate_answer(english_answer, max_retries)
        )

    async def vi_to_en_async(self, text: str) -> str:
        """Alias async: Dịch câu hỏi VI -> EN"""
        print(f"Dịch câu hỏi VI -> EN (async): {text}")
        return await self.translate_question_async(text)

    async def en_to_vi_async(self, text: str) -> str:
        """Alias async: Dịch câu trả lời EN -> VI"""
        print(f"Dịch câu trả lời EN -> VI (async): {text}")
        return await self.translate_answer_async(text)

    # ------------------- SYNC ALIASES ------------------- #

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
