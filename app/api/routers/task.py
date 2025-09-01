# app/api/routers/files.py

from pathlib import Path
import shutil
from typing import List

from starlette.responses import JSONResponse
from fastapi import APIRouter, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
import redis
from fastapi import Depends
from app.schemas.task_schema import Task
from app.core.websocket_manager import websocket_manager
from app.schemas.response.task_schema import RedisClearSuccessData
from app.schemas.response_schema import StandardResponse
from app.core.redis_client import get_redis_client
from app.core.config import UPLOAD_DIRECTORY

# Router khusus untuk fungsionalitas terkait file
router = APIRouter(
    prefix="/red_tasks",        # Prefix baru -> /api/files
    tags=["Redis Tasks"]          # Tag baru untuk dokumentasi Swagger
)

@router.delete(
    "/clear-all", 
    status_code=200,
    response_model=StandardResponse[RedisClearSuccessData]
)
async def clear_all_redis_data(
    redis_client: redis.Redis = Depends(get_redis_client)
):
    try:
        # Perintah FLUSHDB akan menghapus semua data di database saat ini.
        keys_to_delete_count = await redis_client.dbsize() # Hitung jumlah kunci sebelum dihapus
        await redis_client.flushdb()
        
        response_data = RedisClearSuccessData(
            message=f"All data in the current Redis DB has been successfully cleared.",
            keys_deleted=keys_to_delete_count
        )
        
        # Wrap the data in our StandardResponse
        return StandardResponse(data=response_data)
    except Exception as e:
        # Menangkap error jika Redis tidak dapat diakses atau terjadi masalah lain
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to clear Redis data: {e}"
        )