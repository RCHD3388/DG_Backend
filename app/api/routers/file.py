# app/api/routers/files.py

from pathlib import Path
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from app.schemas.response.file_schema import ClearDirectorySuccessData, FileListSuccessData, UploadSuccessData, FileMetadata
from app.schemas.response_schema import MessageResponseData, StandardResponse

from app.services.file_service import FileService
from app.utils.file_utils import clear_directory_contents
from app.api.dependencies import get_file_service
from app.core.exceptions import FileNotFound, FileOperationError, InvalidFileNameError
# --------------------------------------------------------
from app.core.config import EXTRACTED_PROJECTS_DIR, DEPENDENCY_GRAPHS_DIR, PYCG_OUTPUT_DIR

router = APIRouter(
    prefix="/files",
    tags=["Files"]
)

@router.post(
    "/upload", 
    status_code=201,
    response_model=StandardResponse[UploadSuccessData]
)
async def upload_files(
    files: List[UploadFile] = File(...),
    # Injeksi service
    file_service: FileService = Depends(get_file_service)
):
    """
    Menerima satu atau lebih file proyek dan menyimpannya.
    Logika inti kini ditangani oleh FileService.
    """
    try:
        # 1. Panggil service
        saved_paths = await file_service.upload_files(files)
    except FileOperationError as e:
        # 2. Tangkap error service -> ubah ke HTTP
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

    if not saved_paths:
        raise HTTPException(status_code=400, detail="No valid files were uploaded.")

    # 3. Bungkus respons
    response_data = UploadSuccessData(
        message=f"Successfully uploaded {len(saved_paths)} file(s).",
        uploaded_files=[p.name for p in saved_paths]
    )
    return StandardResponse(data=response_data)

@router.get(
    "/", 
    status_code=200,
    response_model=StandardResponse[FileListSuccessData]
)
async def get_all_uploaded_files(
    file_service: FileService = Depends(get_file_service)
):
    """
    Mengembalikan daftar metadata untuk semua file yang sudah diunggah.
    """
    try:
        file_metadata_list = await file_service.get_all_uploaded_files()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")
    
    response_data = FileListSuccessData(files=file_metadata_list)
    return StandardResponse(data=response_data)

# @router.delete("/")
@router.delete(
    "/", 
    status_code=200,
    response_model=StandardResponse[ClearDirectorySuccessData]
)
async def clear_all_directories_files():
    deleted_items_count = 0
    errors = []

    if not EXTRACTED_PROJECTS_DIR.exists() or not DEPENDENCY_GRAPHS_DIR.exists() or not PYCG_OUTPUT_DIR.exists():
        response_data = ClearDirectorySuccessData(
            message=f"Some directory not found, nothing to clear."
        )
        return StandardResponse(data=response_data)

    deleted_items_count += clear_directory_contents(EXTRACTED_PROJECTS_DIR)
    deleted_items_count += clear_directory_contents(DEPENDENCY_GRAPHS_DIR)
    deleted_items_count += clear_directory_contents(PYCG_OUTPUT_DIR)
    
    success_data = ClearDirectorySuccessData(
        message=f"Successfully cleared all the directory files",
        deleted_items_count=deleted_items_count
    )
    return StandardResponse(data=success_data)

@router.delete(
    "/extracted_projects", 
    status_code=200,
    response_model=StandardResponse[ClearDirectorySuccessData]
)
async def clear_extracted_projects_directory(
    file_service: FileService = Depends(get_file_service)
):
    """
    Membersihkan direktori extracted_projects.
    """
    try:
        deleted_count = await file_service.clear_extracted_projects_directory()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear directory: {e}")
    
    success_data = ClearDirectorySuccessData(
        message=f"Successfully cleared the '{EXTRACTED_PROJECTS_DIR.name}' directory.",
        deleted_items_count=deleted_count
    )
    return StandardResponse(data=success_data)


# @router.delete("/dependency_graphs")
@router.delete(
    "/dependency_graphs", 
    status_code=200,
    response_model=StandardResponse[ClearDirectorySuccessData]
)
async def clear_dependency_graphs_directory():
    deleted_items_count = 0
    errors = []

    if not DEPENDENCY_GRAPHS_DIR.exists():
        response_data = ClearDirectorySuccessData(
            message=f"Directory '{DEPENDENCY_GRAPHS_DIR.name}' not found, nothing to clear."
        )
        return StandardResponse(data=response_data)

    deleted_items_count = clear_directory_contents(DEPENDENCY_GRAPHS_DIR)
    
    success_data = ClearDirectorySuccessData(
        message=f"Successfully cleared the '{DEPENDENCY_GRAPHS_DIR.name}' directory.",
        deleted_items_count=deleted_items_count
    )
    return StandardResponse(data=success_data)

# @router.delete("/pycg_outputs")
@router.delete(
    "/pycg_outputs", 
    status_code=200,
    response_model=StandardResponse[ClearDirectorySuccessData]
)
async def clear_pycg_outputs_directory():
    deleted_items_count = 0
    errors = []

    if not PYCG_OUTPUT_DIR.exists():
        response_data = ClearDirectorySuccessData(
            message=f"Directory '{PYCG_OUTPUT_DIR.name}' not found, nothing to clear."
        )
        return StandardResponse(data=response_data)

    deleted_items_count = clear_directory_contents(PYCG_OUTPUT_DIR)
    
    success_data = ClearDirectorySuccessData(
        message=f"Successfully cleared the '{PYCG_OUTPUT_DIR.name}' directory.",
        deleted_items_count=deleted_items_count
    )
    return StandardResponse(data=success_data)

@router.delete(
    "/{file_name}",
    response_model=StandardResponse[MessageResponseData],
    status_code=200
)
async def delete_uploaded_file(
    file_name: str,
    file_service: FileService = Depends(get_file_service)
):
    """
    Menghapus file yang sudah diunggah berdasarkan nama file-nya.
    """
    try:
        await file_service.delete_uploaded_file(file_name)
    except FileNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidFileNameError, FileOperationError) as e:
        # Tangkap error 400 (Bad Request)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch-all
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
    
    response_data = MessageResponseData(
        message=f"File '{file_name}' was successfully deleted."
    )
    return StandardResponse(data=response_data)
