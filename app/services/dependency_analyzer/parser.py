from typing import Dict, List, Set, Tuple, Optional, Any, Union
import os
import ast
import json
import logging
from enum import Enum
from pathlib import Path
import networkx as nx
from dataclasses import dataclass, field

from app.services.dependency_analyzer.resolver import DependencyResolver, PrimaryDependencyResolver, AlternativeDependencyResolver
from app.schemas.models.code_component_schema import CodeComponent, ResolverStrategy
from app.utils.dependency_analyzer_utils import file_to_module_path, add_parent_to_nodes
from app.services.dependency_analyzer.collector import DependencyCollector, ImportCollector
from app.core.mongo_client import get_db
from app.utils.CustomLogger import CustomLogger
from app.services.code_component_service import get_hydrated_components_for_record, map_components_by_id

logger = CustomLogger("DepParser")

class DependencyParser:
    def __init__(self, repo_path: Path, project_root_folder: Path, task_id: str, root_module_name: str, resolver_strategy: ResolverStrategy = ResolverStrategy.FIRST):
        self.repo_path = repo_path
        self.project_root_folder = project_root_folder
        self.relevant_files: List[Path] = []
        self.components: Dict[str, CodeComponent] = {}
        self.class_components: Dict[str, CodeComponent] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
        self.modules: Set[str] = set()

        self.task_id = task_id
        self.root_module_name = root_module_name
        self.resolver: DependencyResolver = self._get_resolver(resolver_strategy)

    def _get_resolver(self, strategy: ResolverStrategy) -> DependencyResolver:
        """Factory method to select the dependency resolution strategy."""
        resolver_args = (self.components, self.modules, self.repo_path, self.task_id, self.root_module_name, self.project_root_folder)
        if strategy == ResolverStrategy.FIRST:
            return PrimaryDependencyResolver(*resolver_args)
        elif strategy == ResolverStrategy.SECOND:
            return AlternativeDependencyResolver(*resolver_args)
        else:
            raise ValueError(f"Unknown resolver strategy: {strategy}")

    def parse_repository(self):
        # # SPECIAL
        # self.components = map_components_by_id(get_hydrated_components_for_record(
        #     root_folder_path="D:\\ISTTS\\Semester_7\\TA\\Project_TA\\DG_Backend\\app\\extracted_projects\\d57bbb72-4dd6-4e78-8e6e-7e93e576ca95\\nanochat-master",
        #     record_code="d57bbb72-4dd6-4e78-8e6e-7e93e576ca95"
        # ))
        # return self.components
        
        if not self.relevant_files:
            self.relevant_files = self.get_relevant_files()

        print(f"Repo path (parsing): {self.repo_path}")

        # FIRST PASS: Collect all components
        for file_path in self.relevant_files:
            relative_path = file_path.relative_to(self.repo_path)
            module_path = file_to_module_path(str(relative_path))
            self.modules.add(module_path)

            # Parse the file to collect components
            self._parse_file(str(file_path), str(relative_path), module_path)

        # SECOND PASS: build dependencies
        self.resolver.resolve(self.relevant_files)

        # THIRD PASS: class and method dependencies
        self._add_class_method_dependencies()
        # FOURTH PASS: parent class dependencies
        self._add_parent_class_dependencies()
        # FIFTH PASS: decorators dependencies
        self._add_decorator_dependencies()

        # logger.info_print(f"Total components collected: {len(self.components)}")
        return self.components

    def get_relevant_files(self):
        logger.info_print(f"Parsing repository at {self.repo_path}")

        all_py_files = self.repo_path.rglob('*.py')
        current_relevant_files = []

        exclude_dirs = {"venv", ".venv", "pycg-venv", "__pycache__", "tests", "test", "__MACOSX", "__macosx"}

        for file_path in all_py_files:
            path_parts = {part.lower() for part in file_path.parts}
        
            # Kondisi untuk mengecualikan file
            is_test_file = file_path.name.startswith("test_") or file_path.name.endswith("_test.py")
            is_excluded_dir = any(part in exclude_dirs for part in path_parts)

            # Jika tidak ada kondisi pengecualian yang terpenuhi, tambahkan file ke list
            if not (is_test_file or is_excluded_dir):
                current_relevant_files.append(file_path)
                # logging.info(f"{file_path}")

        logger.info_print(f"Total relevant Python files to parse: {len(current_relevant_files)}")
        self.relevant_files = current_relevant_files

        return current_relevant_files
    
    # --- 1 PARSING FILES START ---
    def _parse_file(self, file_path: str, relative_path: str, module_path: str):
        """Parse a single Python file to collect code components."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)

            # Add parent field to AST nodes for easier traversal
            add_parent_to_nodes(tree)
            
            # Collect Project Components
            self._collect_components(tree, file_path, relative_path, module_path, source)

        except (SyntaxError, UnicodeDecodeError) as e:
            logger.warning_print(f"Error parsing {file_path}: {e}")

    def _collect_components(self, tree: ast.AST, file_path: str, relative_path: str, 
                          module_path: str, source: str):
        """Collect all code components (functions, classes, methods) from an AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Class definition
                class_id = f"{module_path}.{node.name}"
                
                # Check if the class has a docstring
                has_docstring = (
                    len(node.body) > 0 
                    and isinstance(node.body[0], ast.Expr) 
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                )
                
                # Extract docstring if it exists
                docstring = self._get_docstring(source, node) if has_docstring else ""
                
                start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
                end_line = getattr(node, "end_lineno", node.lineno)
                
                component = CodeComponent(
                    id=class_id,
                    node=node,
                    component_type="class",
                    file_path=file_path,
                    relative_path=relative_path,
                    source_code=self._get_source_segment(source, start_line, end_line),
                    component_signature=self._get_source_signature(node),
                    start_line=start_line,
                    end_line=end_line,
                    has_docstring=has_docstring,
                    docstring=docstring
                )
                
                self.components[class_id] = component
                self.class_components[class_id] = component
                
                class_header_end_line = end_line
                # Collect methods within the class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_id = f"{class_id}.{item.name}"
                        
                        # Check if the method has a docstring
                        method_has_docstring = (
                            len(item.body) > 0 
                            and isinstance(item.body[0], ast.Expr) 
                            and isinstance(item.body[0].value, ast.Constant)
                            and isinstance(item.body[0].value.value, str)
                        )
                        
                        # Extract docstring if it exists
                        method_docstring = self._get_docstring(source, item) if method_has_docstring else ""
                        
                        method_start_line = item.decorator_list[0].lineno if item.decorator_list else item.lineno
                        method_end_line = getattr(item, "end_lineno", item.lineno)
                        
                        method_component = CodeComponent(
                            id=method_id,
                            node=item,
                            component_type="method",
                            file_path=file_path,
                            relative_path=relative_path,
                            source_code=self._get_source_segment(source, method_start_line, method_end_line),
                            component_signature=self._get_source_signature(item),
                            start_line=method_start_line,
                            end_line=method_end_line,
                            header_end_line=method_end_line,
                            has_docstring=method_has_docstring,
                            docstring=method_docstring
                        )
                        
                        # set header end line of class if method ends later
                        if method_start_line > class_header_end_line:
                            class_header_end_line = method_start_line
                            
                        self.components[method_id] = method_component

                # set class header end line if __init__ not found
                self.components[class_id].header_end_line = class_header_end_line
                
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only collect top-level functions
                if hasattr(node, 'parent') and isinstance(node.parent, ast.Module):
                    func_id = f"{module_path}.{node.name}"
                    
                    # Check if the function has a docstring
                    has_docstring = (
                        len(node.body) > 0 
                        and isinstance(node.body[0], ast.Expr) 
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    )
                    
                    # Extract docstring if it exists
                    docstring = self._get_docstring(source, node) if has_docstring else ""
                    
                    function_start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
                    function_end_line = getattr(node, "end_lineno", node.lineno)
                    
                    component = CodeComponent(
                        id=func_id,
                        node=node,
                        component_type="function",
                        file_path=file_path,
                        relative_path=relative_path,
                        source_code=self._get_source_segment(source, function_start_line, function_end_line),
                        component_signature=self._get_source_signature(node),
                        start_line=function_start_line,
                        end_line=function_end_line,
                        header_end_line=function_end_line,
                        has_docstring=has_docstring,
                        docstring=docstring
                    )
                    
                    self.components[func_id] = component

    def _get_source_segment(self, source: str, start_line: int, end_line: int) -> str:
        """Get source code segment for an AST node."""
        try:
            # Fallback to manual extraction
            lines = source.splitlines()
            segment_lines = lines[start_line - 1:end_line]
            return "\n".join(segment_lines)
        
        except Exception as e:
            logger.warning_print(f"Error getting source segment: {e}")
            return ""
        
    def _get_source_signature(self, node: ast.AST) -> str:
        """
        Membangun ulang string signature dari node AST untuk fungsi atau kelas.

        Fungsi ini secara akurat merekonstruksi header definisi untuk
        FunctionDef, AsyncFunctionDef, dan ClassDef, termasuk generic type
        parameters (PEP 695).

        Args:
            node: Node AST yang akan dianalisis. Harus berupa salah satu dari
                  ast.FunctionDef, ast.AsyncFunctionDef, atau ast.ClassDef.

        Returns:
            String signature yang lengkap dan valid secara sintaksis,
            diakhiri dengan titik dua (':'). Mengembalikan string kosong
            jika node tidak didukung.
        """
        
        # --- Handle Fungsi dan Method (Sync & Async) ---
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            
            # 1. Tentukan keyword: 'def' atau 'async def'
            keyword = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            
            # 2. Ambil nama fungsi
            name = node.name
            
            # 3. Handle Generic Type Parameters (PEP 695), jika ada
            type_params_str = ""
            if hasattr(node, 'type_params') and node.type_params:
                # ast.unparse akan mengubah daftar type param menjadi "[T, K, ...]"
                type_params_str = ast.unparse(node.type_params)

            # 4. Handle parameter (args). ast.unparse() adalah cara terbaik
            #    karena menangani semua kasus: default, *args, **kwargs, dll.
            params_str = f"({ast.unparse(node.args)})"
            
            # 5. Handle return annotation, jika ada
            return_annotation_str = ""
            if node.returns:
                return_annotation_str = f" -> {ast.unparse(node.returns)}"
            
            # 6. Gabungkan semua bagian menjadi signature lengkap
            if type_params_str:
                return f"{keyword} {name}[{type_params_str}]{params_str}{return_annotation_str}:"
            else:
                return f"{keyword} {name}{params_str}{return_annotation_str}:"

        # --- Handle Kelas ---
        elif isinstance(node, ast.ClassDef):
            
            # 1. Ambil nama kelas
            name = node.name

            # 2. Handle Generic Type Parameters (PEP 695), jika ada
            type_params_str = ""
            if hasattr(node, 'type_params') and node.type_params:
                type_params_str = ast.unparse(node.type_params)

            # 3. Handle base classes (pewarisan) dan keyword arguments (metaclass)
            parent_part_str = ""
            # Menggabungkan base classes dan keyword arguments
            all_args = [ast.unparse(b) for b in node.bases] + \
                       [ast.unparse(k) for k in node.keywords]
            
            if all_args:
                parent_part_str = f"({', '.join(all_args)})"
            
            # 4. Gabungkan semua 
            if type_params_str:
                return f"class {name}[{type_params_str}]{parent_part_str}:"
            else:
                return f"class {name}{parent_part_str}:"
            
        # Jika node bukan tipe yang didukung, kembalikan string kosong
        return ""
    
    def _get_docstring(self, source: str, node: ast.AST) -> str:
        """Get the docstring for a given AST node."""
        try:
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                for item in node.body:
                    if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
                        if isinstance(item.value.value, str):
                            return item.value.value
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
                        if isinstance(item.value.value, str):
                            return item.value.value
            return ""
        except Exception as e:
            logger.warning_print(f"Error getting docstring: {e}")
            return 
    
    def build_dependency_graph_from_components(self) -> Dict[str, Set[str]]:
        graph = {}

        for comp_id, component in self.components.items():
            # Initialize the node's adjacency list
            if comp_id not in graph:
                graph[comp_id] = set()
            
            # Add dependencies
            for dep_id in component.depends_on:
                # Only include dependencies that are actual components in our repository
                if dep_id in self.components:
                    graph[comp_id].add(dep_id)
                    self.components[dep_id].used_by.add(comp_id)
        
        for component_id, deps in graph.items():
            self.dependency_graph[component_id] = list(deps)
        
        return self.dependency_graph
    # --- 1 PARSING FILES END ---

    # --- 2 ADD CLASS METHOD DEPENDENCIES START ---
    def _add_class_method_dependencies(self):
        """
        Third pass to make classes dependent on their methods (except __init__).
        """
        # Group components by class
        class_methods = {}
        
        # Collect all methods for each class
        for component_id, component in self.components.items():
            if component.component_type == "method":
                parts = component_id.split(".")
                if len(parts) >= 2:
                    method_name = parts[-1]
                    class_id = ".".join(parts[:-1])
                    
                    if class_id not in class_methods:
                        class_methods[class_id] = []
                    
                    # Don't include __init__ methods as dependencies of the class
                    if method_name != "__init__":
                        class_methods[class_id].append(component_id)
        
        # Add method dependencies to their classes
        for class_id, method_ids in class_methods.items():
            if class_id in self.components:
                class_component = self.components[class_id]
                for method_id in method_ids:
                    class_component.depends_on.add(method_id)
    # --- 2 ADD CLASS METHOD DEPENDENCIES END ---

    # --- 2B ADD PARENT CLASS DEPENDENCIES
    def _add_parent_class_dependencies(self):
                    
        # get inheritance, or interface 
        for component_id, component in self.class_components.items():
            node = component.node
            file_path = component.file_path
            parent_list = self.resolver.get_parent_class_names(node)
            component_parent_ids = []
            
            # loop daftar parent dari node ClassDef
            for parent in parent_list:
                # Trace dapatkan semua parent path asli
                origin_result = self.resolver.trace_symbol_origin(parent, current_filepath=file_path, root_folder=self.project_root_folder)
                
                if origin_result:
                    # mendapatkan format yang tepat
                    dot_path = self.resolver.format_origin_to_dot_path(origin_info=origin_result, project_root=self.repo_path)
                    # Check apakah terdapat di components yang di scan, mencegah ABC, dan class bawaan
                    if dot_path in self.components:
                        # Simpan ke component parent Set
                        component.component_parents.add(dot_path)
                        component.depends_on.add(dot_path)
            
    # --- 2B ADD PARENT CLASS DEPENDENCIES END

    # --- 2C ADD DECORATOR DEPENDENCIES
    def get_decorator_name(decorator_node: ast.AST) -> str:
        # Membutuhkan Python 3.9+ untuk ast.unparse
        try:
            if isinstance(decorator_node, ast.Call):
                #  @decorator(arg) @module.decorator(arg)
                return ast.unparse(decorator_node.func)
            else:
                # @decorator atau @module.decorator
                return ast.unparse(decorator_node)
                
        except AttributeError:
            if isinstance(decorator_node, ast.Name):
                return decorator_node.id
            if isinstance(decorator_node, ast.Attribute):
                return f"{decorator_node.value.id}.{decorator_node.attr}" # Versi sederhana
            if isinstance(decorator_node, ast.Call):
                if isinstance(decorator_node.func, ast.Name):
                    return decorator_node.func.id
                if isinstance(decorator_node.func, ast.Attribute):
                    return f"{decorator_node.func.value.id}.{decorator_node.func.attr}" # Versi sederhana
            return "Unknown"
    def _add_decorator_dependencies(self):
        for component_id, component in self.components.items():
            node = component.node
            
            # check masing maing component
            list_of_decorators: List[str] = []
            # 1. Jika tidak ada decorator
            if not hasattr(node, 'decorator_list'):
                continue
            
            # 2 Mendapatkan decorator semuanya
            for decorator_node in node.decorator_list:
                if isinstance(decorator_node, ast.Call):
                    name_node = decorator_node.func # Kasus: @decorator(arg) atau @module.decorator(arg)
                else:
                    name_node = decorator_node # Kasus: @decorator atau @module.decorator
                
                try:
                    decorator_name = ast.unparse(name_node)
                    # mendapatkan symbol origin decorator
                    origin_information = self.resolver.trace_symbol_origin(
                            symbol_name = decorator_name, 
                            current_filepath=component.file_path, 
                            root_folder=self.project_root_folder
                        )
                    # create origin dot path & insert
                    origin_dot_path = self.resolver.format_origin_to_dot_path(origin_info=origin_information, project_root=self.repo_path)
                    if origin_dot_path in self.components:
                        list_of_decorators.append(origin_dot_path)
                except Exception:
                    pass
            
            # 3. Jika ada decorator
            if list_of_decorators:
                for decorator_name in list_of_decorators:
                    component.depends_on.add(decorator_name)
                
                
    # --- 3 Add Component Generated Documentation START ---
    def add_component_generated_doc(self, component_id: str, docgen_final_state: Dict[str, Any], time_used: Dict[str, Any]):
        """Add or update the generated documentation for a specific component."""
        if component_id in self.components:
            # get final state
            final_state = docgen_final_state.get("final_state", {})
            doc_json_object = final_state.get("documentation_json")
            
            docstring_context_string = None # Ini akan menjadi JSON string TANPA 'examples'
            documentation_json_dict = None
            
            if doc_json_object:
                # Untuk docstring
                doc_dict_no_examples = doc_json_object.model_dump(exclude={'examples'})
                docstring_context_string = json.dumps(doc_dict_no_examples)
                # Untuk documentation_json
                documentation_json_dict = doc_json_object.model_dump()
            
            self.components[component_id].docgen_final_state = {
                "final_state": {
                    "docstring": docstring_context_string or "",
                    "reader_search_attempts": final_state.get("reader_search_attempts", 0),
                    "verifier_rejection_count": final_state.get("verifier_rejection_count", 0),
                    "documentation_json": documentation_json_dict or {},
                },
                "usage_stats": docgen_final_state.get("usage_stats", {}),
                "time_used": time_used or {},
            }
        else:
            logger.warning_print(f"Component {component_id} not found to add generated documentation.")
    # --- 3 Add Component Generated Documentation END ---
 
    # --- 4 Save Data dependency START ---
    def save_components(self, output_path: str):
        """Save the dependency graph to a JSON file."""
        # Convert to serializable format
        serializable_components = {
            comp_id: component.to_dict()
            for comp_id, component in self.components.items()
        }
        
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable_components, f, indent=2)
    
    def add_component_dependency_graph_urls(self, component_ids: List[str], record_code: str):
        for component_id in component_ids:
            if component_id in self.components:
                component_id_with_underscore = component_id.replace('.', '_')
                self.components[component_id].dependency_graph_url = f"{record_code}/{component_id_with_underscore}.png"
    
    def save_record_to_database(self, record_code: str, metadata = {}, collection: str = "documentation_results", name: Optional[str] = None):
        
        # 1. Penyusunan documents_to_insert (List of Dictionaries)
        documents_to_insert: List[Dict[str, Any]] = []
        
        for comp_id, component_object in self.components.items():
            try:
                # Panggil method to_dict() untuk mendapatkan representasi data
                doc_dict = component_object.to_dict() 
                
                if 'id' not in doc_dict:
                    doc_dict['id'] = comp_id # Tambahkan ID komponen jika belum ada
                    
                documents_to_insert.append(doc_dict)
                
            except AttributeError:
                print(f"[DB] Error: Komponen ID '{comp_id}' tidak memiliki method .to_dict(). Dokumen dilewati.")
                
        if not documents_to_insert:
            # Pengecekan kedua setelah pemrosesan
            print(f"[DB] Operasi dibatalkan: Tidak ada dokumen komponen yang valid untuk disimpan.")
            return

        # 2. Penyusunan Dokumen Induk (Record Document)
        record_document = {
            "_id": record_code, # Menggunakan record_code sebagai ID unik
            "name": name if name is not None else record_code,
            "components": documents_to_insert,
            "meta_information": metadata
        }
        
        # 3. Operasi Database (replace_one dengan upsert)
        try:
            db = get_db()
            collection = db[collection]

            result = collection.replace_one(
                {"_id": record_code},
                record_document,
                upsert=True
            )
            
            # Laporan Hasil
            if result.upserted_id:
                print(f"[DB SUCCESS] Record '{record_code}' - Name '{name}' berhasil DIBUAT (Insert). Jumlah komponen: {len(documents_to_insert)}.")
            elif result.modified_count > 0:
                print(f"[DB SUCCESS] Record '{record_code}' berhasil DIPERBARUI (Update). Jumlah komponen: {len(documents_to_insert)}.")
            else:
                print(f"[DB INFO] Record '{record_code}' sudah ada dan tidak ada perubahan data.")

        except Exception as e:
            print(f"[DB ERROR] Gagal menyimpan atau memperbarui record '{record_code}': {e}")
    # --- 4 Save Data dependency END ---
        
    # --- 5 DiGraph Processing START ---
    def get_Nx_DiGraph(self) -> nx.DiGraph:
        edges = []
        all_nodes = set(self.dependency_graph.keys())

        for source_node, target_nodes in self.dependency_graph.items():
            if not target_nodes:
                continue
            for target_node in target_nodes:
                # Di networkx, edge (A, B) berarti A -> B (A menunjuk ke B).
                # Dalam konteks dependensi, "A bergantung pada B" berarti kita perlu
                # memproses B SEBELUM A. Jadi, edge harus dari B ke A (B -> A).
                edges.append((target_node, source_node))
                all_nodes.add(target_node)

        # Buat grafik berarah (DiGraph)
        DG = nx.DiGraph()
        DG.add_nodes_from(all_nodes) # Tambahkan semua node, termasuk yang terisolasi
        DG.add_edges_from(edges)
        
        return DG
        
    # --- 5 DiGraph Processing END ---