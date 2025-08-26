# app/api/routers/analyze.py

import os
from pathlib import Path
import shutil
from typing import List

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from app.core.config import UPLOAD_DIRECTORY, ANALYZE_DIRECTORY
from app.services.doc_generator import generate_documentation_for_project
from app.core.config import settings
from app.core.redis_client import get_redis_client

from app.schemas.task_schema import Task
import redis
from enum import Enum
from app.schemas.task_schema import TaskStatus, TaskStatusDetail

router = APIRouter(
    prefix="/analyze",
    tags=["Analysis"]
)

@router.post("/{file_name}", status_code=200)
async def analyze_repository(
    file_name: str,
    background_tasks: BackgroundTasks,
    redis_client: redis.Redis = Depends(get_redis_client) 
):
    repo_file_path = UPLOAD_DIRECTORY / file_name

    if not repo_file_path.exists() or not repo_file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Repository file '{file_name}' not found.")

    # 1. Buat instance Task menggunakan blueprint kita
    new_task = Task(source_file=file_name)

    # 4. Simpan dictionary yang sudah dikonversi ke Redis
    await redis_client.hset(
        f"task:{new_task.task_id}", 
        mapping=new_task.model_dump() # <-- Gunakan dictionary yang sudah aman
    )

    # 3. Jadwalkan background task
    background_tasks.add_task(
        generate_documentation_for_project, 
        source_file_path=repo_file_path,
        task_id=new_task.task_id
    )

# --- Endpoint download-result tidak berubah, sudah menangani tipe file .docx ---
@router.get("/download-result/{result_filename}")
async def download_analysis_result(result_filename: str):
    RESULTS_DIRECTORY = UPLOAD_DIRECTORY / "analysis_results"
    file_path = RESULTS_DIRECTORY / result_filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File hasil '{result_filename}' tidak ditemukan.")
    
    media_type = "application/octet-stream" 
    if result_filename.endswith(".json"):
        media_type = "application/json"
    elif result_filename.endswith(".png"):
        media_type = "image/png"
    elif result_filename.endswith(".svg"):
        media_type = "image/svg+xml"
    elif result_filename.endswith(".md"):
        media_type = "text/markdown"
    elif result_filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif result_filename.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=result_filename,
    )