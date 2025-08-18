import os
import shutil
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse # Untuk custom response jika diperlukan

app = FastAPI()

# --- KONFIGURASI CORS (SANGAT PENTING UNTUK KOMUNIKASI FRONTEND-BACKEND) ---
# Ganti "http://localhost:5173" dengan URL aplikasi React Anda di produksi
origins = [
    "http://localhost",
    "http://localhost:8000", # URL backend sendiri
    "http://localhost:5173", # URL default Vite/React dev server
    # Tambahkan domain frontend produksi Anda di sini jika sudah deploy
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Mengizinkan semua metode HTTP (GET, POST, PUT, DELETE, dll.)
    allow_headers=["*"], # Mengizinkan semua header
)

# --- KONFIGURASI DIREKTORI PENYIMPANAN FILE ---
UPLOAD_DIRECTORY = Path("uploaded_files")

@app.on_event("startup")
async def startup_event():
    """Memastikan direktori upload ada saat aplikasi dimulai."""
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    print(f"Direktori upload '{UPLOAD_DIRECTORY}' siap.")

# --- ENDPOINT UPLOAD FILE ---
@app.post("/api/upload_files/")
async def upload_files(files: List[UploadFile] = File(...)): # 'files' harus match dengan formData.append('files', file) dari frontend
    """
    Menerima satu atau lebih file dan menyimpannya ke direktori 'uploaded_files'.
    """
    uploaded_file_paths = []
    for file in files:
        file_location = UPLOAD_DIRECTORY / file.filename
        try:
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(file.file, file_object)
            uploaded_file_paths.append(str(file_location))
            print(f"File '{file.filename}' berhasil disimpan di {file_location}")
        except Exception as e:
            # Hapus file yang mungkin sudah disimpan sebagian jika terjadi error
            if file_location.exists():
                file_location.unlink()
            print(f"Gagal menyimpan file '{file.filename}': {e}")
            raise HTTPException(status_code=500, detail=f"Gagal mengunggah file {file.filename}.")
        finally:
            file.file.close() # Pastikan file stream ditutup

    return JSONResponse(status_code=200, content={
        "message": f"Successfully uploaded {len(files)} files!",
        "file_paths": uploaded_file_paths
    })

# --- Contoh endpoint lain (opsional) ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to FastAPI backend!"}