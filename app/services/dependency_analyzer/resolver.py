# app/services/dependency_analyzer/resolvers.py

from abc import ABC, abstractmethod
from typing import Dict, Set
from pathlib import Path
import ast
import logging
import subprocess
import json
import os
from collections import defaultdict

from .collector import ImportCollector, DependencyCollector
from app.schemas.models.code_component_schema import CodeComponent, ResolverStrategy
from app.utils.dependency_analyzer_utils import file_to_module_path, add_parent_to_nodes
from app.core.config import settings
from app.core.config import PYCG_OUTPUT_DIR

logger = logging.getLogger(__name__)

class DependencyResolver(ABC):
    """
    Abstract base class for dependency resolution strategies.
    Defines the contract for all concrete resolver implementations.
    """
    def __init__(self, components: Dict[str, CodeComponent], modules: Set[str], repo_path: Path, task_id: str, root_module_name: str):
        self.components = components
        self.modules = modules
        self.repo_path = repo_path
        self.task_id = task_id
        self.root_module_name = root_module_name

    @abstractmethod
    def resolve(self) -> None:
        """
        The main method to perform dependency resolution.
        This method should iterate through the components and update their
        'depends_on' attribute.
        """
        pass
    
class PrimaryDependencyResolver(DependencyResolver):
    """
    Resolves dependencies using the primary, detailed analysis method.
    (Ini adalah logika dari kode Anda saat ini)
    """
    def resolve(self) -> None:
        for component_id, component in self.components.items():
            file_path = component.file_path

            if component.component_type != "function" or component.id.split(".")[-1] != "main" or component.id.split(".")[-2] != "main":
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    source = f.read()
                
                # Parse file to get imports
                tree = ast.parse(source)
                
                # Add parent field to AST nodes for easier traversal
                add_parent_to_nodes(tree)
                
                # Collect imports
                import_collector = ImportCollector()
                import_collector.visit(tree)

                print(f"\nComponent {component.id} depends on: {import_collector.imports}\n LEN: {len(import_collector.imports)}\n")
                print(f"\nComponent {component.id} depends on: {import_collector.wildcard_modules}\n LEN: {len(import_collector.wildcard_modules)}\n")

                # Find the component node in the tree
                component_node = None
                module_path = file_to_module_path(component.relative_path)

                if component.component_type == "function":
                    # Find top-level function
                    for node in ast.iter_child_nodes(tree):
                        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) 
                                and node.name == component.id.split(".")[-1]):
                            component_node = node
                            break
                
                elif component.component_type == "class":
                    # Find class
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.ClassDef) and node.name == component.id.split(".")[-1]:
                            component_node = node
                            break
                
                elif component.component_type == "method":
                    # Find method inside class
                    class_name, method_name = component.id.split(".")[-2:]
                    class_node = None
                    
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.ClassDef) and node.name == class_name:
                            class_node = node
                            for item in node.body:
                                if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) 
                                        and item.name == method_name):
                                    component_node = item
                                    break
                            break
                
                if component_node:
                    # Collect dependencies for this specific component
                    dependency_collector = DependencyCollector(
                        import_collector.imports,
                        import_collector.wildcard_modules,
                        module_path,
                        self.modules,
                        repo_path=self.repo_path
                    )
                    
                    # For functions and methods, collect variables defined in the function
                    if isinstance(component_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Add function parameters to local variables
                        for arg in component_node.args.args:
                            dependency_collector.local_variables.add(arg.arg)
                            
                    dependency_collector.visit(component_node)

                    print(f"\nHasil Secondary : {component.id} depends on: {dependency_collector.dependencies}\n LEN: {len(dependency_collector.dependencies)}\n")
                    
                    # Add dependencies to the component
                    component.depends_on.update(dependency_collector.dependencies)
                    
                    # Filter out non-existent dependencies
                    component.depends_on = {
                        dep for dep in component.depends_on 
                        if dep in self.components or dep.split(".", 1)[0] in self.modules
                    }
                
            except (SyntaxError, UnicodeDecodeError) as e:
                logger.warning(f"Error analyzing dependencies in {file_path}: {e}")


class AlternativeDependencyResolver(DependencyResolver):
    """
    Resolves dependencies using an alternative, perhaps faster or simpler, method.
    """
    def resolve(self) -> None:
        print("\nResolving dependencies using an alternative method...")
        print(f"REPO PATH : {self.repo_path}")

        exclude_dirs = {"venv", ".venv", "pycg-venv", "__pycache__", "tests", "test"}

        entry_points = [
            # Konversi ke string karena subprocess membutuhkan string, bukan objek Path
            str(p) for p in self.repo_path.rglob('*.py')
            # Filter 1: Jangan sertakan file di dalam direktori yang dikecualikan
            if not any(part in exclude_dirs for part in p.parts)
            # Filter 2: Jangan sertakan file pengujian umum
            and not p.name.startswith("test_")
            and not p.name.endswith("_test.py")
        ]

        if not entry_points:
            logger.warning(f"No Python files found to analyze in {self.repo_path} after filtering.")
            return

        output_json_path = PYCG_OUTPUT_DIR / f"{self.task_id}.json"

        try:
            command = [
                settings.PYCG_PYTHON_EXECUTABLE,
                "-m", "pycg",
                *entry_points,  # <-- Di sinilah keajaibannya terjadi
                "--package", str(self.repo_path),
                "--output", output_json_path,
            ]

            # clean path
            clean_env = os.environ.copy()
            clean_env.pop("PYTHONPATH", None)

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                env=clean_env
            )

            # Load pycg data form json output file
            with open(output_json_path, 'r', encoding='utf-8') as f:
                pycg_data = json.load(f)

            self._map_pycg_to_components(pycg_data)

            logger.info("PyCG execution successful.")

        except FileNotFoundError:
            logger.error(
                f"PyCG executable not found at '{settings.PYCG_PYTHON_EXECUTABLE}'. "
                "Please check the PYCG_PYTHON_EXECUTABLE path in your .env file."
            )
            # Anda bisa melempar exception custom di sini jika perlu
            raise
        except subprocess.CalledProcessError as e:
            # Ini akan terjadi jika PyCG gagal (misal, error parsing)
            logger.error(f"PyCG execution failed with return code {e.returncode}")
            logger.error(f"PyCG stderr: {e.stderr}")
            raise
    
    def _normalize_path(self, path_string: str) -> str:
        return path_string.replace("\\", ".").replace("/", ".")

    def _build_name_index(self) -> dict:
        name_index = defaultdict(list)
        for component in self.components.values():
            if component.component_type == "method":
                short_name = ".".join(component.id.split('.')[-2:])
            else:
                short_name = ".".join(component.id.split('.')[-1:])
                
            name_index[short_name].append(component.id)
        return name_index

    def _map_pycg_to_components(self, raw_pycg_output: dict):
        """
        Maps the complete dependency graph from PyCG's JSON output
        to the internal CodeComponent structure.
        """
        name_index = self._build_name_index()

        for component_id, component in self.components.items():
            
            relative_path_no_ext = component.relative_path.removesuffix(".py")
            relative_path_no_ext_module_path = self._normalize_path(relative_path_no_ext)
            
            # Format key = relative path + spliced relative module path without extension
            formatted_key = component_id.replace(relative_path_no_ext_module_path, relative_path_no_ext)

            # Get raw calles from raw_pycg_output
            raw_callees = raw_pycg_output.get(formatted_key)

            # Check and build dependency
            if raw_callees:
                for callee in raw_callees:
                    
                    # 1. Check if built in module
                    if callee.startswith("<builtin>"):
                        continue

                    # Normalize path = tanpa "/" dan "\\"
                    normalized_callee = self._normalize_path(callee)

                    # 2. Check if plainly exist in components
                    if callee not in self.components:
                        
                        # --- special part start ---

                        id_to_check = normalized_callee
                        module_parts = normalized_callee.split('.')

                        # Check PATH MODULE adalah ROOT NAMESPACE PROYEK.
                        if self.root_module_name and module_parts and module_parts[0] == self.root_module_name:
                            # id_to_check = path TANPA root namespace
                            id_to_check = ".".join(module_parts[1:])

                        # Check apakah ID absolut yang sudah dibersihkan dengan benar ini ada di komponen kita.
                        if id_to_check in self.components:
                            normalized_callee = id_to_check
                        else:
                            # --- Langkah 2: Coba Resolusi Relatif (jika absolut gagal) ---
                            # -> Get caller module parts
                            # -> Normalize callee REMAINED THE SAME
                            original_caller_module_parts = component_id.split('.')
                            if component.component_type == 'method':
                                caller_module_parts = original_caller_module_parts[:-2]
                            else: # Function & Class
                                caller_module_parts = original_caller_module_parts[:-1]
                            
                            found_relative_match = False
                            # Trace Relative : back loop module parts ..
                            for i in range(len(caller_module_parts), -1, -1):
                                # PARENT -> caller prefix
                                parent_module_path = ".".join(caller_module_parts[:i])
                                
                                # CONCATED path
                                potential_id = f"{parent_module_path}.{normalized_callee}" if parent_module_path else normalized_callee
                                
                                # IF potential was found in components
                                if potential_id in self.components:
                                    normalized_callee = potential_id
                                    found_relative_match = True
                                    break

                            
                            # Jika setelah semua upaya tidak ditemukan kecocokan, abaikan.
                            if not found_relative_match:

                                # === SPECIAL CHECK RE_IMPORT ===
                                candidate_component_ids = []
                                component_name_length = 0
                                original_calle_module_parts = normalized_callee.split('.')
                                
                                # 1. Get CANDIDATE COMPONENT ID
                                if len(original_calle_module_parts) > 2:
                                    
                                    for i in range(2, 0, -1):
                                        
                                        name_index_search_key = ".".join(original_calle_module_parts[-i:])
                                        candidate_component_id = name_index[name_index_search_key]
                                        
                                        # ReI 1. Check apakah ditemukan
                                        if candidate_component_id:
                                            
                                            # ReI 2. Check kalau C1 --> i = 2, C2 --> Path[-3] sama Path[-2], C3 --> Path[-1] terdapat di name index
                                            if i == 2 and original_calle_module_parts[-2] == original_calle_module_parts[-3] and len(name_index[original_calle_module_parts[-1]]) == 1:
                                                continue
                                            
                                            candidate_component_ids.append(candidate_component_id)
                                            component_name_length = i
                                            break

                                elif len(original_calle_module_parts) == 2:
                                    # Pasti FUNCTION atau CLASS
                                    candidate_component_id = name_index[original_calle_module_parts[-1]]
                                    # Kalau ditemukan di name index
                                    if candidate_component_id:
                                        component_name_length = 1
                                        candidate_component_ids.append(candidate_component_id)
                                
                                if candidate_component_ids == []:
                                    continue

                                
                                for candidate_id in candidate_component_ids:
                                    # Check apakah part callee bagian depan terdapat pada candidate 
                                    # Jika benar maka BERHASIL
                                    if ".".join(original_calle_module_parts[:-component_name_length]) in candidate_id:
                                        normalized_callee = candidate_id
                                        found_relative_match = True
                                        normalized_callee = candidate_id
                                        break
                                # === SPECIAL CHECK RE_IMPORT ===

                                if not found_relative_match:
                                    continue    
                        # === special steps end ===
                    

                    component.depends_on.add(normalized_callee)

        logger.info("Finished mapping PyCG results.")