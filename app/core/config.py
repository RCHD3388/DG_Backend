# app/core/config.py

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Model Konfigurasi Pydantic, memuat variabel dari file .env
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')
    
    # --- Konfigurasi Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    REDIS_USERNAME: str = "default"
    REDIS_PASSWORD: str = "******"

    PYCG_PYTHON_EXECUTABLE: str = "python -3.9"

# Membuat instance tunggal dari Settings yang akan digunakan di seluruh aplikasi
settings = Settings()


APP_BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = APP_BASE_DIR.parent

PROCESS_OUTPUT_DIR = APP_BASE_DIR / "process_outputs"

# Direktori untuk menyimpan file yang di-upload, relatif terhadap root proyek
UPLOAD_DIRECTORY = APP_BASE_DIR / "uploaded_files"
ANALYZE_DIRECTORY = PROCESS_OUTPUT_DIR / "analyze_results"
EXTRACTED_PROJECTS_DIR = APP_BASE_DIR / "extracted_projects"

DEPENDENCY_GRAPHS_DIR = PROCESS_OUTPUT_DIR / "dependency_graphs"
COLLECTED_COMPONENTS_DIR = PROCESS_OUTPUT_DIR / "collected_components"
PYCG_OUTPUT_DIR = PROCESS_OUTPUT_DIR / "pycg_outputs"

def initialize_output_directories():
    """
    Creates the necessary output directories for the application if they don't exist.
    
    Args:
        process_output_dir: The base directory for all processed outputs.
    """
    logger.info("Initializing output directories...")
    
    # Definisikan semua subdirektori yang diperlukan
    dirs_to_create = [
        DEPENDENCY_GRAPHS_DIR,
        COLLECTED_COMPONENTS_DIR,
        PYCG_OUTPUT_DIR
    ]
    
    try:
        for directory in dirs_to_create:
            # Menggunakan Path.mkdir() adalah cara modern dan direkomendasikan.
            # - parents=True: Membuat direktori induk jika diperlukan (misal, membuat 'process_outputs' jika belum ada).
            # - exist_ok=True: Tidak akan menimbulkan error jika direktori sudah ada.
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
            
        logger.info("All output directories are ready.")
        
    except OSError as e:
        logger.error(f"Failed to create one or more output directories: {e}")
        # Melempar kembali exception ini penting agar aplikasi bisa
        # berhenti jika tidak bisa membuat direktori krusial.
        raise