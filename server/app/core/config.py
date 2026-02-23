import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CUSTOM_BASE_URL = os.getenv("PPT_LLM_URL", "").rstrip("/")
    CUSTOM_TOKEN = os.getenv("CUSTOM_TOKEN")
    AUDIO_LLM_URL = os.getenv("AUDIO_LLM_URL", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
    RESULT_DIR = os.path.join(BASE_DIR, "static", "results")
    
    HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
    
    USERS_FILE = os.path.join(BASE_DIR, "users.json")
    SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-me")
    
    DOCS_DATA_FILE = os.path.join(BASE_DIR, "docs.json")  # 폴더/파일 구조 데이터
    DOCS_STATIC_DIR = os.path.join(BASE_DIR, "static", "docs") # 압축 해제된 파일 저장소

    # 결과물 URL 생성을 위한 base url (배포시 도메인으로 변경)
    BASE_URL = "http://localhost:8000"
    
    MAIL_SENDER = "knpubigmac2024@gmail.com"
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.RESULT_DIR, exist_ok=True)