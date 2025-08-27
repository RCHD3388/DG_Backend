# app/api/documentation_router.py

import shutil
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException, FastAPI
from app.api.routers import analyze, file, task
from starlette.responses import JSONResponse

# Import konfigurasi UPLOAD_DIRECTORY dari file config
from app.core.config import UPLOAD_DIRECTORY

# Membuat instance APIRouter. Semua endpoint di file ini akan menggunakan 'router'
router = APIRouter(
    prefix="/api",  # Memberikan prefix /api untuk semua endpoint di router ini
    tags=["File Upload"] # Mengelompokkan endpoint di dokumentasi Swagger
)

router.include_router(file.router)
router.include_router(analyze.router)
router.include_router(task.router)