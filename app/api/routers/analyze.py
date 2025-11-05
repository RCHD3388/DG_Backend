# app/api/routers/analyze.py

import os
from pathlib import Path
import shutil
from typing import List
import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from app.core.websocket_manager import websocket_manager
from app.schemas.response.analyze_schema import AnalysisStartSuccessData, AnalysisRequestBody
from app.schemas.response_schema import StandardResponse
from app.core.config import UPLOAD_DIRECTORY, DEPENDENCY_GRAPHS_DIR, COLLECTED_COMPONENTS_DIR
from app.services.doc_generator import generate_documentation_for_project
from app.core.config import settings
from app.core.redis_client import get_redis_client

from app.schemas.models.task_schema import Task
import redis
from enum import Enum
from app.schemas.models.task_schema import TaskStatus, TaskStatusDetail

router = APIRouter(
    prefix="/analyze",
    tags=["Analysis"]
)

@router.websocket("/ws/subscribe/{task_id}")
async def websocket_subscribe_to_task(websocket: WebSocket, task_id: str):
    """
    Menghubungkan klien ke WebSocket dan mengirimkan status task awal.
    """
    await websocket_manager.connect(task_id, websocket)
    await websocket_manager.broadcast_task_update(task_id)
    
    try:
        # Jaga koneksi tetap terbuka
        while True:
            try:
                # timeout supaya loop tidak memblokir event loop utama
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                print("Received:", msg)
            except asyncio.TimeoutError:
                await asyncio.sleep(0.01)
                continue
    except WebSocketDisconnect:
        websocket_manager.disconnect(task_id)

@router.post(
    "/{file_name}", 
    status_code=200,
    response_model=StandardResponse[AnalysisStartSuccessData]
)
async def analyze_repository(
    file_name: str,
    body: AnalysisRequestBody,
    background_tasks: BackgroundTasks,
    redis_client: redis.Redis = Depends(get_redis_client) 
):
    print(f"file_name: {file_name}")
    print(f"config_filename: {body.config_filename}")
    print(f"process_name: {body.process_name}")
    
    
    repo_file_path = UPLOAD_DIRECTORY / file_name

    if not repo_file_path.exists() or not repo_file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Repository file '{file_name}' not found.")

    # 1. Buat instance Task menggunakan blueprint kita
    new_task = Task(source_file=file_name)
    task_data = new_task.model_dump()
    task_data_for_redis = {key: str(value) for key, value in task_data.items()}

    # 4. Simpan dictionary yang sudah dikonversi ke Redis
    print(f"Creating new analysis task with ID: {new_task}")
    await redis_client.hset(
        f"task:{new_task.task_id}", 
        mapping=task_data_for_redis # <-- Gunakan dictionary yang sudah aman
    )

    # 3. Jadwalkan background task
    background_tasks.add_task(
        generate_documentation_for_project, 
        source_file_path=repo_file_path,
        task_id=new_task.task_id,
        analyze_name=body.process_name if body.process_name else None
    )

    response_data = AnalysisStartSuccessData(
        task_id=new_task.task_id,
        message=f"Analysis process for file '{file_name}' has been successfully started."
    )
    return StandardResponse(data=response_data)

# --- Endpoint download-result tidak berubah, sudah menangani tipe file .docx ---
@router.get("/download_result/{result_filename}")
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

@router.get("/download_components/{result_filename}")
async def download_dependency_result(result_filename: str):
    file_path = COLLECTED_COMPONENTS_DIR / result_filename

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