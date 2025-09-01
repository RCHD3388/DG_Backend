# app/api/routers/files.py

from pathlib import Path
import shutil
from typing import List

from starlette.responses import JSONResponse
from fastapi import APIRouter, File, UploadFile, HTTPException
from app.schemas.response.file_schema import ClearDirectoryPartialFailData, ClearDirectorySuccessData, FileListSuccessData, UploadSuccessData, FileMetadata
from app.schemas.response_schema import ErrorDetail, MessageResponseData, StandardResponse
from app.core.config import UPLOAD_DIRECTORY, EXTRACTED_PROJECTS_DIR

# Router khusus untuk fungsionalitas terkait file
router = APIRouter(
    prefix="/files",        # Prefix baru -> /api/files
    tags=["Files"]          # Tag baru untuk dokumentasi Swagger
)

@router.post(
    "/upload", 
    status_code=201,
    response_model=StandardResponse[UploadSuccessData]
) # Path menjadi /upload -> /api/files/upload
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
            print(f"File '{file.filename}' successfully saved at {file_location}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file '{file.filename}': {e}")
        finally:
            file.file.close()

    if not uploaded_file_paths:
        raise HTTPException(status_code=400, detail="No valid files were uploaded.")

    response_data = UploadSuccessData(
        message=f"Successfully uploaded {len(uploaded_file_paths)} file(s).",
        uploaded_files=[Path(p).name for p in uploaded_file_paths]
    )
    
    # 2. Bungkus data tersebut di dalam StandardResponse
    return StandardResponse(data=response_data)

@router.get(
    "/", 
    status_code=200,
    response_model=StandardResponse[FileListSuccessData]
) # Path menjadi / -> /api/files/
async def get_all_uploaded_files():
    """
    Mengembalikan daftar metadata untuk semua file yang sudah diunggah.
    """
    file_metadata_list  = []
    if not UPLOAD_DIRECTORY.exists():
        return StandardResponse(data=FileListSuccessData(files=[]))

    for file_path in UPLOAD_DIRECTORY.iterdir():
        if file_path.is_file():
            try:
                stat_info = file_path.stat()
                # Create an instance of the FileMetadata schema
                file_metadata_list.append(
                    FileMetadata(
                        id=file_path.name,
                        name=file_path.name,
                        size=stat_info.st_size,
                    )
                )
            except Exception as e:
                # In a real app, you might log this error but continue
                print(f"Warning: Failed to get info for file '{file_path.name}': {e}")

    # 1. Create an instance of our specific data schema
    response_data = FileListSuccessData(files=file_metadata_list)
    
    # 2. Wrap the data in our StandardResponse
    return StandardResponse(data=response_data)

@router.delete(
    "/{file_name}",
    # Define the response model for a successful operation
    response_model=StandardResponse[MessageResponseData],
    status_code=200
)
async def delete_uploaded_file(file_name: str):
    """
    Menghapus file yang sudah diunggah berdasarkan nama file-nya.
    """
    file_path_to_delete = UPLOAD_DIRECTORY / file_name

    if not file_path_to_delete.exists():
        raise HTTPException(status_code=404, detail=f"File '{file_name}' not found.")
    
    if not file_path_to_delete.is_file():
        raise HTTPException(status_code=400, detail=f"'{file_name}' is not a valid file.")

    try:
        file_path_to_delete.unlink() # Menghapus file
        print(f"File '{file_name}' was successfully deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file '{file_name}': {e}")
    
    response_data = MessageResponseData(
        message=f"File '{file_name}' was successfully deleted."
    )
    return StandardResponse(data=response_data)
@router.delete(
    "/clear-extracted-projects", 
    status_code=200,
    response_model=StandardResponse[ClearDirectorySuccessData]
)
async def clear_extracted_projects_directory():
    """
    Deletes ALL content from the 'extracted_projects' directory,
    but leaves the directory itself.
    
    Useful for cleaning up remnants of previous analysis processes.
    """
    deleted_items_count = 0
    errors = []

    if not EXTRACTED_PROJECTS_DIR.exists():
        response_data = ClearDirectorySuccessData(
            message=f"Directory '{EXTRACTED_PROJECTS_DIR.name}' not found, nothing to clear."
        )
        return StandardResponse(data=response_data)

    for path in EXTRACTED_PROJECTS_DIR.iterdir():
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
            
            deleted_items_count += 1
            
        except Exception as e:
            error_message = f"Failed to delete '{path.name}': {e}"
            print(error_message)
            errors.append(error_message)

    if errors:
        partial_fail_data = ClearDirectoryPartialFailData(
            message="Cleanup finished, but some errors occurred.",
            deleted_items_count=deleted_items_count,
            errors=errors
        )
        
        # Since this isn't a simple HTTPException, we build the response manually
        # and use JSONResponse to send it with the correct status code.
        error_response = StandardResponse(
            success=False,
            data=partial_fail_data,
            error=ErrorDetail(
                code=507, # 507 Insufficient Storage can imply a failed cleanup
                type="PartialCleanupFailure",
                message="One or more items could not be deleted, possibly due to file locks."
            )
        )
        return JSONResponse(
            status_code=507,
            content=error_response.model_dump(exclude_none=True)
        )
    
    success_data = ClearDirectorySuccessData(
        message=f"Successfully cleared the '{EXTRACTED_PROJECTS_DIR.name}' directory.",
        deleted_items_count=deleted_items_count
    )
    return StandardResponse(data=success_data)