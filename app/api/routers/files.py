# app/api/routers/files.py

from pathlib import Path
import shutil
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException
from app.core.config import UPLOAD_DIRECTORY

# Router khusus untuk fungsionalitas terkait file
router = APIRouter(
    prefix="/files",        # Prefix baru -> /api/files
    tags=["Files"]          # Tag baru untuk dokumentasi Swagger
)

@router.post("/upload", status_code=201) # Path menjadi /upload -> /api/files/upload
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Menerima satu atau lebih file proyek dan menyimpannya untuk analisis.
    """
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True) # Pastikan direktori ada
    
    uploaded_file_paths = []
    for file in files:
        if not file.filename:
            continue # Lewati jika ada file tanpa nama

        file_location = UPLOAD_DIRECTORY / file.filename
        try:
            with file_location.open("wb") as file_object:
                shutil.copyfileobj(file.file, file_object)
            uploaded_file_paths.append(str(file_location))
            print(f"File '{file.filename}' berhasil disimpan di {file_location}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan file '{file.filename}': {e}")
        finally:
            file.file.close()

    if not uploaded_file_paths:
        raise HTTPException(status_code=400, detail="Tidak ada file yang valid untuk diunggah.")

    return {
        "message": f"Berhasil mengunggah {len(uploaded_file_paths)} file.",
        "uploaded_files": [Path(p).name for p in uploaded_file_paths]
    }