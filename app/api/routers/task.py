# app/api/routers/files.py

from pathlib import Path
import shutil
from typing import List

from starlette.responses import JSONResponse
from fastapi import APIRouter, File, UploadFile, HTTPException
import redis
from fastapi import Depends
from app.core.redis_client import get_redis_client
from app.core.config import UPLOAD_DIRECTORY

# Router khusus untuk fungsionalitas terkait file
router = APIRouter(
    prefix="/red_tasks",        # Prefix baru -> /api/files
    tags=["Redis Tasks"]          # Tag baru untuk dokumentasi Swagger
)

@router.delete("/clear-all", status_code=200)
async def clear_all_redis_data(
    redis_client: redis.Redis = Depends(get_redis_client)
):
    try:
        # Perintah FLUSHDB akan menghapus semua data di database saat ini.
        keys_deleted = await redis_client.dbsize() # Hitung jumlah kunci sebelum dihapus
        await redis_client.flushdb()
        
        return {
            "status": "ok", 
            "message": f"Semua data di Redis berhasil dihapus. Jumlah kunci yang dihapus: {keys_deleted}"
        }
    except Exception as e:
        # Menangkap error jika Redis tidak dapat diakses atau terjadi masalah lain
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal membersihkan data Redis: {e}"
        )