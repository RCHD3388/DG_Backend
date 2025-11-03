# app/api/dependencies.py

from functools import lru_cache
from pathlib import Path

# Import konfigurasi Anda
from app.core.config import UPLOAD_DIRECTORY, EXTRACTED_PROJECTS_DIR
# Import service Anda
from app.services.file_service import FileService

@lru_cache()
def get_file_service() -> FileService:
    """
    Dependency provider untuk FileService.
    Menggunakan lru_cache untuk membuat instance singleton.
    """
    return FileService(
        upload_dir=UPLOAD_DIRECTORY,
        extracted_dir=EXTRACTED_PROJECTS_DIR
    )