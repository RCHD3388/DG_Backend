# app/api/routers/files.py

from pathlib import Path
import re
import os
import shutil
from typing import List

from fastapi.responses import FileResponse

from starlette.responses import JSONResponse
from fastapi import APIRouter, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
import redis
from fastapi import Depends, Form
from app.schemas.response.config_schema import ConfigContent, ConfigUploadSuccess, ConfigDeleteSuccess, ConfigListEntry
from app.schemas.response_schema import StandardResponse
from app.core.redis_client import get_redis_client
from app.core.config import UPLOAD_CONFIGS_DIRECTORY

# Router khusus untuk fungsionalitas terkait file
router = APIRouter(
    prefix="/configs",        # Prefix baru -> /api/files
    tags=["Application Configuration"]          # Tag baru untuk dokumentasi Swagger
)

def sanitize_filename(name: str) -> str:
    """Membersihkan nama file dan memastikan ekstensi .yaml."""
    # Ganti spasi dengan garis bawah
    name = name.strip().replace(" ", "_")
    # Hapus karakter yang tidak aman
    name = re.sub(r"[^a-zA-Z0-9_\-.]", "", name)
    
    # Tambahkan ekstensi jika belum ada
    if not (name.endswith(".yaml") or name.endswith(".yml")):
        name = f"{name}.yaml"
    return name

@router.get(
    "/",
    response_model=StandardResponse[List[ConfigListEntry]]
)
async def get_all_configs():
    """
    Mengambil daftar semua file konfigurasi .yaml/.yml yang tersedia.
    """
    configs = []
    try:
        for f in os.listdir(UPLOAD_CONFIGS_DIRECTORY):
            if f.endswith((".yaml", ".yml")):
                # Sesuai kontrak frontend, 'name' dan 'filename' bisa sama
                # di frontend React, kita menggunakan 'filename' untuk aksi
                configs.append(ConfigListEntry(name=f, filename=f))
        
        # Urutkan berdasarkan nama untuk konsistensi
        configs.sort(key=lambda x: x.name)
        
        return StandardResponse(data=configs)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal membaca direktori konfigurasi: {e}"
        )

# === ENDPOINT 2: Upload Konfigurasi Baru ===
@router.post(
    "/",
    response_model=StandardResponse[ConfigUploadSuccess],
    status_code=201 # HTTP 201 Created
)
async def upload_config(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Mengunggah file konfigurasi .yaml baru.
    Nama file akan diambil dari field 'name' yang disanitasi.
    """
    # Validasi tipe file di sisi server
    if not (file.content_type in ["application/x-yaml", "text/yaml"] or \
            file.filename.endswith((".yaml", ".yml"))):
        raise HTTPException(
            status_code=400, 
            detail="Tipe file tidak valid. Harap unggah file .yaml atau .yml."
        )

    filename = sanitize_filename(name)
    save_path = UPLOAD_CONFIGS_DIRECTORY / filename

    # Cek jika file sudah ada untuk menghindari penimpaan
    if save_path.exists():
        raise HTTPException(
            status_code=409, # HTTP 409 Conflict
            detail=f"Konfigurasi dengan nama '{filename}' sudah ada."
        )

    # Simpan file ke disk
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        await file.close()
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal menyimpan file: {e}"
        )
    finally:
        await file.close()
    
    response_data = ConfigUploadSuccess(
        filename=filename,
        message="Konfigurasi berhasil diunggah."
    )
    return StandardResponse(data=response_data, status_code=201)

# === ENDPOINT 3: Mendapatkan Konten Satu Konfigurasi (Preview) ===
@router.get(
    "/{config_name}",
    response_model=StandardResponse[ConfigContent]
)
async def get_config_content(config_name: str):
    """
    Mengambil konten teks dari satu file konfigurasi untuk preview.
    """
    # Keamanan: Cegah directory traversal
    if ".." in config_name or config_name.startswith("/"):
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")

    file_path = UPLOAD_CONFIGS_DIRECTORY / config_name

    if not file_path.is_file():
        raise HTTPException(
            status_code=404, 
            detail=f"Konfigurasi '{config_name}' tidak ditemukan."
        )
    
    try:
        content = file_path.read_text(encoding="utf-8")
        return StandardResponse(data=ConfigContent(content=content))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal membaca file: {e}"
        )

@router.get(
    "/download/{config_name}/",
    response_class=FileResponse, # Penting: Menentukan tipe respons adalah file
    summary="Download a Configuration File"
)
async def download_config(config_name: str):
    """
    Mengunduh satu file konfigurasi spesifik.
    Endpoint ini mengembalikan file mentah (raw file) yang akan memicu
    dialog download di browser.
    """
    # Keamanan: Cegah directory traversal (konsisten dengan endpoint lain)
    if ".." in config_name or config_name.startswith("/"):
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")
        
    file_path = UPLOAD_CONFIGS_DIRECTORY / config_name
    
    # Cek apakah file benar-benar ada
    if not file_path.is_file():
        raise HTTPException(
            status_code=404, 
            detail=f"Konfigurasi '{config_name}' tidak ditemukan."
        )

    # Menggunakan FileResponse untuk mengirim file ke client
    return FileResponse(
        path=str(file_path),
        filename=config_name,
        media_type='application/x-yaml'
    )

# === ENDPOINT 4: Menghapus Satu Konfigurasi ===
@router.delete(
    "/{config_name}",
    response_model=StandardResponse[ConfigDeleteSuccess]
)
async def delete_config(config_name: str):
    """
    Menghapus satu file konfigurasi.
    """
    # Keamanan: Cegah directory traversal
    if ".." in config_name or config_name.startswith("/"):
        raise HTTPException(status_code=400, detail="Nama file tidak valid.")
        
    file_path = UPLOAD_CONFIGS_DIRECTORY / config_name

    if not file_path.is_file():
        raise HTTPException(
            status_code=404, 
            detail=f"Konfigurasi '{config_name}' tidak ditemukan."
        )

    try:
        os.remove(file_path)
        response_data = ConfigDeleteSuccess(
            filename=config_name,
            message="Konfigurasi berhasil dihapus."
        )
        return StandardResponse(data=response_data)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal menghapus file: {e}"
        )