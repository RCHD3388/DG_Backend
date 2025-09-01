from pydantic import BaseModel # Pastikan BaseModel diimpor
from app.schemas.response_schema import StandardResponse # Impor StandardResponse
from typing import List
# ... import lainnya ...

# --- Skema Data untuk Respons Sukses Upload ---
class UploadSuccessData(BaseModel):
    message: str
    uploaded_files: List[str]

# --- Schema for a single file's metadata ---
class FileMetadata(BaseModel):
    id: str
    name: str
    size: int # size in bytes

# --- Schema for the overall success data payload ---
class FileListSuccessData(BaseModel):
    files: List[FileMetadata]

class ClearDirectorySuccessData(BaseModel):
    message: str
    deleted_items_count: int = 0

# --- Schema for a partially failed directory clear operation ---
class ClearDirectoryPartialFailData(BaseModel):
    message: str
    deleted_items_count: int
    errors: List[str]