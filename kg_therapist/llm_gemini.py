import google.generativeai as genai

from .config import GEMINI_API_KEY, GEMINI_MODEL_NAME

if not GEMINI_API_KEY:
    raise RuntimeError("Set GOOGLE_API_KEY environment variable for Gemini")

genai.configure(api_key=GEMINI_API_KEY)


class LLMClient:
    def __init__(self, model_name: str = GEMINI_MODEL_NAME):
        self.model = genai.GenerativeModel(model_name)

    def invoke(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        if not response:
            return "Based on the information available, I don't know. Could you provide more details about your situation?"
        return response.text


llm = LLMClient()
