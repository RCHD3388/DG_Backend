# app/core/config.py

from pathlib import Path

# Mendefinisikan direktori root dari proyek
# Path(__file__) -> file ini (config.py)
# .resolve() -> /path/lengkap/ke/doc_generator_backend/app/core/config.py
# .parent -> /path/lengkap/ke/doc_generator_backend/app/core
# .parent -> /path/lengkap/ke/doc_generator_backend/app
# .parent -> /path/lengkap/ke/doc_generator_backend/
APP_BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = APP_BASE_DIR.parent

# Direktori untuk menyimpan file yang di-upload, relatif terhadap root proyek
UPLOAD_DIRECTORY = APP_BASE_DIR / "uploaded_files"