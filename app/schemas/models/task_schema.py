# app/schemas/task_schema.py

from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional
import uuid

# --- Mapping untuk Status Detail ---
# Menggunakan Enum memastikan kita hanya menggunakan nilai yang valid dan terdefinisi.
class TaskStatusDetail(str, Enum):
    QUEUED = "Task received and queued."
    EXTRACTING = "Extracting project files..."
    ANALYZING_STRUCTURE = "Analyzing project structure..."
    PARSING_FILES = "Parsing source code files..."
    GENERATING_DOCUMENTATION = "Generating documentation with LLM..."
    FORMATTING_OUTPUT = "Formatting final output..."
    COMPLETED = "Documentation generated successfully."
    FAILED = "An error occurred during the process."

# --- Mapping untuk Status Utama ---
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# --- Blueprint Utama untuk Task ---
# Ini adalah model Pydantic yang mendefinisikan semua data yang kita simpan di Redis.
class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_file: str
    root_module_name: str = ""
    
    status: str = TaskStatus.PENDING.value
    status_detail: str = TaskStatusDetail.QUEUED.value
    
    # Progress Tracking
    target_process: int = 0
    current_process: int = 0

    discovered_files: Optional[List[str]] = []
    
    # Hasil atau Error
    result_url: str = ""
    error: str = ""