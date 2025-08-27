# app/services/doc_generator.py

import zipfile
import shutil
import sys
import logging
from pathlib import Path
from app.core.redis_client import get_redis_client
from app.core.config import EXTRACTED_PROJECTS_DIR
from app.schemas.task_schema import TaskStatus, TaskStatusDetail
from app.services.dependency_analyzer.parser import DependencyParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("docstring_generator")

def extract_zip(file_path: Path, extract_to: Path):
    if file_path.suffix == '.zip':
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    else: # Jika bukan zip, cukup salin
        extract_to.mkdir(exist_ok=True)
        shutil.copy(file_path, extract_to / file_path.name)
        

async def generate_documentation_for_project(source_file_path: Path, task_id: str):
    """
    Fungsi orkestrator yang mengelola seluruh alur kerja dari awal hingga akhir.
    """
    redis_client = get_redis_client()
    project_extract_path = EXTRACTED_PROJECTS_DIR / task_id
    
    try:
        # --- Update Status Awal ---
        await redis_client.hset(f"task:{task_id}", "status", TaskStatus.PROCESSING.value)
        await redis_client.hset(f"task:{task_id}", "status_detail", TaskStatusDetail.EXTRACTING.value)
        
        # --- Ekstraksi File ---
        extract_zip(source_file_path, project_extract_path)
        print(f"[{task_id}] File extracted to {project_extract_path}")

        # -- Create Dependency Graphs Directory if not exists --
        dependency_graphs_dir = EXTRACTED_PROJECTS_DIR
        dependency_graphs_dir.mkdir(parents=True, exist_ok=True)

        dependency_graph_path = dependency_graphs_dir / f"{task_id}_dependency_graph.json"

        # --- Parsing Repository ---
        await redis_client.hset(f"task:{task_id}", "status_detail", TaskStatusDetail.PARSING_FILES.value)
        
        logger.info(f"[{task_id}] Parsing repository at {project_extract_path}")
        parser = DependencyParser(str(project_extract_path))
        components = parser.parse_repository()



        # --- Analisis Struktur Proyek ---

        # --- Generasi Dokumentasi ---

        # --- Update Status Selesai ---
        await redis_client.hset(f"task:{task_id}", mapping={
            "status": TaskStatus.COMPLETED.value,
            "status_detail": TaskStatusDetail.COMPLETED.value,
            "result_url": "DUMMY URL"
        })

    except Exception as e:
        # --- Tangani Error ---
        print(f"[{task_id}] TERJADI ERROR: {e}")
        await redis_client.hset(f"task:{task_id}", mapping={
            "status": TaskStatus.FAILED.value, 
            "status_detail": TaskStatusDetail.FAILED.value,
            "error": str(e)
        })
    finally:
        # --- Selalu Tutup Koneksi & Bersihkan ---
        await redis_client.close()
        # # Opsional: Hapus direktori file yang diekstrak untuk menghemat ruang
        # if project_extract_path.exists():
        #     shutil.rmtree(project_extract_path)