# app/api/documentation_router.py

import shutil
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException
from starlette.responses import JSONResponse

# Import konfigurasi UPLOAD_DIRECTORY dari file config
from app.core.config import UPLOAD_DIRECTORY

# Membuat instance APIRouter. Semua endpoint di file ini akan menggunakan 'router'
router = APIRouter(
    prefix="/api",  # Memberikan prefix /api untuk semua endpoint di router ini
    tags=["File Upload"] # Mengelompokkan endpoint di dokumentasi Swagger
)


@router.post("/upload_files/", status_code=200)
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Menerima satu atau lebih file dan menyimpannya ke direktori 'uploaded_files'.
    """
    uploaded_file_paths = []
    for file in files:
        # Gunakan UPLOAD_DIRECTORY yang sudah diimpor
        file_location = UPLOAD_DIRECTORY / file.filename
        try:
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(file.file, file_object)
            uploaded_file_paths.append(str(file_location))
            print(f"File '{file.filename}' berhasil disimpan di {file_location}")
        except Exception as e:
            if file_location.exists():
                file_location.unlink()
            print(f"Gagal menyimpan file '{file.filename}': {e}")
            raise HTTPException(status_code=500, detail=f"Gagal mengunggah file {file.filename}.")
        finally:
            file.file.close()

    return {
        "message": f"Successfully uploaded {len(files)} files!",
        "file_paths": uploaded_file_paths
    }