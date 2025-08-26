# app/core/config.py

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Model Konfigurasi Pydantic, memuat variabel dari file .env
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')
    
    # --- Konfigurasi Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    REDIS_USERNAME: str = "default"
    REDIS_PASSWORD: str = "******"

# Membuat instance tunggal dari Settings yang akan digunakan di seluruh aplikasi
settings = Settings()


APP_BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = APP_BASE_DIR.parent

# Direktori untuk menyimpan file yang di-upload, relatif terhadap root proyek
UPLOAD_DIRECTORY = APP_BASE_DIR / "uploaded_files"
ANALYZE_DIRECTORY = APP_BASE_DIR / "analyze_results"
EXTRACTED_PROJECTS_DIR = APP_BASE_DIR / "extracted_projects"