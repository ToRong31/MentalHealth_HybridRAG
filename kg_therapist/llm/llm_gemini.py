import google.generativeai as genai
import os
import logging

from .config import GEMINI_MODEL_NAME
from .manage_apikey.respone.api_key_manager import APIKeyManager, load_api_keys_from_file

logger = logging.getLogger(__name__)

# Đường dẫn tới file API keys
API_KEY_FILE = os.path.join(
    os.path.dirname(__file__), 
    "manage_apikey", 
    "respone", 
    "api_key.txt"
)

# Load tất cả API keys và khởi tạo manager
try:
    api_keys = load_api_keys_from_file(API_KEY_FILE)
    key_manager = APIKeyManager(api_keys, min_delay_between_calls=0.1)
    logger.info(f"✓ Loaded {len(api_keys)} API keys for rotation")
except Exception as e:
    logger.error(f"Failed to load API keys: {e}")
    raise RuntimeError(f"Cannot initialize API Key Manager: {e}")


class LLMClient:
    """
    LLM Client with automatic API key rotation
    
    Sau mỗi lần gọi (thành công hay thất bại), key sẽ tự động rotate sang key tiếp theo.
    """
    
    def __init__(self, model_name: str = GEMINI_MODEL_NAME):
        self.model_name = model_name
        self.key_manager = key_manager
        logger.info(f"Initialized LLMClient with model: {model_name}")
    
    def invoke(self, prompt: str) -> str:
        """
        Gọi Gemini API với automatic key rotation
        
        Key rotation xảy ra TỰ ĐỘNG sau mỗi lần gọi, bất kể thành công hay thất bại.
        
        Args:
            prompt: Prompt để gửi tới LLM
            
        Returns:
            Response text từ LLM
        """
        # Lấy key tiếp theo (tự động rotate)
        current_key = self.key_manager.get_next_key()
        
        try:
            # Configure Gemini với key hiện tại
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(self.model_name)
            
            # Gọi API
            response = model.generate_content(prompt)
            
            if not response or not response.text:
                logger.warning("Empty response from Gemini API")
                return "Based on the information available, I don't know. Could you provide more details about your situation?"
            
            # Đánh dấu thành công
            self.key_manager.mark_success(current_key)
            
            return response.text
            
        except Exception as e:
            # Log lỗi và xử lý error
            error_message = str(e)
            logger.error(f"Error calling Gemini API: {error_message}")
            
            # Cố gắng parse status code từ error message
            status_code = 0
            if "429" in error_message:
                status_code = 429
            elif "401" in error_message or "unauthorized" in error_message.lower():
                status_code = 401
            elif "403" in error_message or "forbidden" in error_message.lower():
                status_code = 403
            
            # Báo lỗi cho key manager
            self.key_manager.handle_error(current_key, status_code, error_message)
            
            # Trả về response mặc định
            return "Based on the information available, I don't know. Could you provide more details about your situation?"
    
    def get_stats(self):
        """Lấy thống kê sử dụng API keys"""
        return self.key_manager.get_stats()
    
    def print_summary(self):
        """In ra tóm tắt sử dụng API keys"""
        self.key_manager.print_summary()


# Global LLM client instance
llm = LLMClient()
