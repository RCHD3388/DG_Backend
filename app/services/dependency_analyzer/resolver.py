# app/services/dependency_analyzer/resolvers.py

from abc import ABC, abstractmethod
from typing import Dict, Set
from pathlib import Path
import ast
import logging
import subprocess
import json
import os

from .collector import ImportCollector, DependencyCollector
from .models import CodeComponent, ResolverStrategy
from .utils import file_to_module_path, add_parent_to_nodes
from app.core.config import settings
from app.core.config import PYCG_OUTPUT_DIR

logger = logging.getLogger(__name__)

class DependencyResolver(ABC):
    """
    Abstract base class for dependency resolution strategies.
    Defines the contract for all concrete resolver implementations.
    """
    def __init__(self, components: Dict[str, CodeComponent], modules: Set[str], repo_path: Path, task_id: str):
        self.components = components
        self.modules = modules
        self.repo_path = repo_path
        self.task_id = task_id

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
            # with open(output_json_path, 'r', encoding='utf-8') as f:
            #     pycg_data = json.load(f)

            logger.info("PyCG execution successful.")
            logger.debug(f"PyCG stdout: {result.stdout}")

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