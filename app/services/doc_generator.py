# app/services/doc_generator.py

import zipfile
import shutil
import sys
import logging
from pathlib import Path

from flask import json
from app.core.websocket_manager import websocket_manager
from app.core.redis_client import get_redis_client
from app.core.config import COLLECTED_COMPONENTS_DIR, EXTRACTED_PROJECTS_DIR, DEPENDENCY_GRAPHS_DIR, PROCESS_OUTPUT_DIR
from app.schemas.models.task_schema import TaskStatus, TaskStatusDetail
from app.services.dependency_analyzer.parser import DependencyParser
from app.services.topological_sort.topological import build_graph_from_components, get_topological_sort_from_dependencies

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
    
    items_inside = [item for item in extract_to.iterdir() if item.name != "__MACOSX"]
    
    if len(items_inside) == 0:
        return None
    elif len(items_inside) == 1 and items_inside[0].is_dir():
        return items_inside[0]
    else:
        return extract_to

def get_project_root_name(project_root_path: Path) -> str:
    if not project_root_path or not project_root_path.is_dir():
        logger.error(f"Invalid project root path provided: {project_root_path}")
        raise ValueError("Project root path must be a valid directory.")

    return project_root_path.name

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
        
        # 1 --- FILE EXTRACTION ---
        current_repo_path = extract_zip(source_file_path, project_extract_path)
        root_module_name = get_project_root_name(current_repo_path)

        print(f"[{task_id}] File extracted to {project_extract_path}")

        # -- Create if not exists --
        dependency_graphs_dir = DEPENDENCY_GRAPHS_DIR
        collected_components_dir = COLLECTED_COMPONENTS_DIR 
        collected_components_dir.mkdir(parents=True, exist_ok=True)
        dependency_graphs_dir.mkdir(parents=True, exist_ok=True)

        collected_components_file_name = f"{task_id}_components.json"
        collected_components_path = collected_components_dir / collected_components_file_name
        dependency_graph_file_name = f"{task_id}_dependency_graph.json"
        dependency_graph_path = dependency_graphs_dir / dependency_graph_file_name

        # 2 --- PARSING REPOSITORY ---
        files_update = {
            "root_module_name": root_module_name,
            "status_detail": TaskStatusDetail.PARSING_FILES.value
        }
        await redis_client.hset(f"task:{task_id}", mapping=files_update)
        
        logger.info(f"[{task_id}] Parsing repository at {project_extract_path}")
        parser = DependencyParser(current_repo_path, task_id, root_module_name)
        
        relevant_files = parser.get_relevant_files()
        
        relative_file_paths = [str(p.relative_to(current_repo_path)) for p in relevant_files]
        
        files_update = {
            "discovered_files": json.dumps(relative_file_paths), 
            "status_detail": TaskStatusDetail.PARSING_FILES.value
        }
        await redis_client.hset(f"task:{task_id}", mapping=files_update)
        await websocket_manager.broadcast_task_update(task_id)
        
        # 3 --- REPOSITORY PROJECT ANALYSIS ---
        components = parser.parse_repository()
        parser.save_components(collected_components_path)

        analysis_update = {
            "status_detail": TaskStatusDetail.GENERATING_DOCUMENTATION.value,
            "result_dependency_graph": collected_components_file_name
        }
        await redis_client.hset(f"task:{task_id}", mapping=analysis_update)
        await websocket_manager.broadcast_task_update(task_id)

        # 4 --- TOPOLOGICAL SORTING ---
        graph = build_graph_from_components(components)
        dependency_graph = {}
        for component_id, deps in graph.items():
            dependency_graph[component_id] = list(deps)
        
        # Topological traversal sort
        
        sorted_components = get_topological_sort_from_dependencies(dependency_graph)

        # --- DOCUMENT GENERATION ---

        # --- COMPLETED ---
        final_update = {
            "status": TaskStatus.COMPLETED.value,
            "status_detail": TaskStatusDetail.COMPLETED.value,
            "result_url": "DUMMY URL"
        }
        await redis_client.hset(f"task:{task_id}", mapping=final_update)
        await websocket_manager.broadcast_task_update(task_id)

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