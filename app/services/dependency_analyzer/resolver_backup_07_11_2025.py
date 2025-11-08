# app/services/dependency_analyzer/resolvers.py

from abc import ABC, abstractmethod
from typing import Dict, Set, List, Optional, Tuple, Union
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
from app.utils.CustomLogger import CustomLogger

logger = CustomLogger("Resolver")

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
    def resolve(self, relevant_files: List[Path]) -> None:
        """
        The main method to perform dependency resolution.
        This method should iterate through the components and update their
        'depends_on' attribute.
        """
        pass
    
    def get_parent_class_names(self, class_node: ast.ClassDef) -> list[str]:
        """
        Mengambil node ast.ClassDef dan mengembalikan list string
        nama parent class-nya secara lengkap (fully qualified).
        """
        
        def _get_full_qualified_name(node: ast.AST) -> str:
            """Helper rekursif untuk mengubah node basis menjadi string nama lengkap."""
            
            if isinstance(node, ast.Name):
                # Kasus dasar: class Babi(Binatang)
                return node.id
            elif isinstance(node, ast.Attribute):
                # Kasus rekursif: class Babi(packa.modula.Binatang)
                # Dapatkan 'packa.modula' lalu tambahkan '.Binatang'
                value_str = _get_full_qualified_name(node.value)
                return f"{value_str}.{node.attr}"
            else:
                # Menangani tipe basis yang tidak didukung, misal: class Babi(create_class())
                return f"<unsupported_base_type: {type(node).__name__}>"

        # --- Badan utama fungsi ---
        
        if not isinstance(class_node, ast.ClassDef):
            raise TypeError(f"Input harus berupa node ast.ClassDef, bukan {type(class_node).__name__}")
        
        parent_names = []
        # Iterasi melalui semua parent class di 'bases'
        for base_node in class_node.bases:
            parent_names.append(_get_full_qualified_name(base_node))
        
        return parent_names
    
class PrimaryDependencyResolver(DependencyResolver):
    """
    Resolves dependencies using an alternative, perhaps faster or simpler, method.
    """
    def resolve(self, relevant_files: List[Path]) -> None:
        print("\nResolving dependencies using an primary method...")

        entry_points = [
            str(p) for p in relevant_files
        ]

        if not entry_points:
            print(f"[DependencyResolver] No Python files found to analyze in {self.repo_path} after filtering.")
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

            print("[DependencyResolver] PyCG execution successful.")

        except FileNotFoundError:
            logger.error_print(
                f"PyCG executable not found at '{settings.PYCG_PYTHON_EXECUTABLE}'. "
                "Please check the PYCG_PYTHON_EXECUTABLE path in your .env file."
            )
            # Anda bisa melempar exception custom di sini jika perlu
            raise
        except subprocess.CalledProcessError as e:
            # Ini akan terjadi jika PyCG gagal (misal, error parsing)
            logger.error_print(f"PyCG execution failed with return code {e.returncode}")
            logger.error_print(f"PyCG stderr: {e.stderr}")
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
            # karena format nya adalah : menggunaakn "//" untuk sampai ke file tersebut dan menggunakan "." untuk nama komponennya
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
                    if normalized_callee not in self.components:
                        
                        # 2.1. CHECK & HILANGKAN ROOT NAMESPACE
                        id_to_check = normalized_callee
                        module_parts = normalized_callee.split('.')
                        if self.root_module_name and module_parts and module_parts[0] == self.root_module_name:
                            # id_to_check = path TANPA root namespace
                            id_to_check = ".".join(module_parts[1:])

                        # Check apakah ID absolut yang sudah dibersihkan dengan benar ini ada di komponen kita.
                        if id_to_check in self.components:
                            normalized_callee = id_to_check
                        else:
                            # --- 2.2 TRACE RELATIVE ---
                            # -> Get caller module parts
                            # -> Normalize callee REMAINED THE SAME
                            original_caller_module_parts = component_id.split('.')
                            if component.component_type == 'method':
                                caller_module_parts = original_caller_module_parts[:-2]
                            else: # Function & Class
                                caller_module_parts = original_caller_module_parts[:-1]
                            
                            found_relative_match = False
                            # 2.2.1 TRACE RELATIVE FULL-DECRESE
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
                                
                                # 2.2.2 TRACE RE-IMPORT ---
                                candidate_component_ids = []
                                component_name_length = 0
                                original_calle_module_parts = normalized_callee.split('.')
                                
                                # 1. Get CANDIDATE COMPONENT ID
                                if len(original_calle_module_parts) >= 2:
                                    
                                    # for i in range(2, 0, -1):
                                    for i in range(1, 3):
                                        
                                        name_index_search_key = ".".join(original_calle_module_parts[-i:])
                                        
                                        
                                        # print(f"-> CC : {component.id} -> {name_index_search_key}")
                                        # print(f"--> File Path: {component.file_path}")
                                        # print(f"--> Repo Path: {self.repo_path}")
                                        # print(f"--> Name Index Search Key: {name_index_search_key}")
                                        origin_info_wild = self.find_true_origin(
                                            entry_file_path=component.file_path,
                                            component_name=name_index_search_key,
                                            project_root=self.repo_path
                                        )
                                        if origin_info_wild:
                                            candidate_norm_calle = self.format_origin_to_dot_path(origin_info_wild, self.repo_path)
                                            # print("=== HASIL WILDCARD DITEMUKAN ===")
                                            # print(f"  Path Asli   : {candidate_norm_calle}")
                                            normalized_callee = candidate_norm_calle
                                            found_relative_match = True
                                            break
                                        else:
                                            # print("=== HASIL WILDCARD TIDAK DITEMUKAN ===")
                                            pass
                                        # print("")
                                
                                # === SPECIAL CHECK RE_IMPORT ===

                                if not found_relative_match:
                                    continue    
                        # === special steps end ===
                    
                    if normalized_callee != component.id:
                        component.depends_on.add(normalized_callee)

        logger.info_print("Finished mapping PyCG results.")
        
    # -----------------------
    def format_origin_to_dot_path(
        self,
        origin_info: Tuple[str, str, str],
        project_root: Union[str, Path]
    ) -> str:
        
        file_path, original_name, _ = origin_info
        
        # 1. Pastikan semua path adalah string absolut untuk perbandingan
        abs_file_path = os.path.abspath(str(file_path))
        abs_root_path = os.path.abspath(str(project_root))
        
        # 2. Dapatkan path relatif dari file ke root
        #    e.g., "packa\packb\packc\packc.py"
        try:
            relative_path = os.path.relpath(abs_file_path, abs_root_path)
        except ValueError:
            # Ini bisa terjadi jika path tidak di bawah root
            return f"[Error: Path {abs_file_path} tidak di bawah root {abs_root_path}]"

        # 3. Hapus ekstensi .py
        #    e.g., "packa\packb\packc\packc"
        module_path, _ = os.path.splitext(relative_path)
        
        # 4. Tangani kasus __init__.py
        #    Jika path-nya "packa\packb\__init__", kita ingin "packa\packb"
        if os.path.basename(module_path) == "__init__":
            module_path = os.path.dirname(module_path)

        # 5. Ganti separator path ( \ atau / ) dengan titik .
        #    e.g., "packa.packb.packc.packc"
        dot_path_base = module_path.replace(os.path.sep, ".")
        
        # 6. Gabungkan dengan nama asli
        #    e.g., "packa.packb.packc.packc.packc"
        
        # Jika module_path adalah root (misalnya __init__.py di root),
        # dot_path_base akan kosong.
        if not dot_path_base:
            return original_name
        else:
            return f"{dot_path_base}.{original_name}"
    
    def static_resolve_module_path(
        self,
        module_name: Optional[str],
        current_filepath: str,
        root_folder: str,
        level: int = 0
    ) -> Optional[str]:
        """
        (Ini adalah fungsi ORIGINAL Anda, tidak diubah, 
        sesuai permintaan untuk kembali ke awal)
        """
        
        base_path = ""

        if level == 0:
            if not module_name:
                return None
            module_parts = module_name.split('.')
            # Dapatkan nama folder terakhir dari root, e.g., 'anus'
            root_folder_name = os.path.basename(root_folder)

            # print(f"{module_parts[0]} --- {root_folder_name}")
            # --- INI ADALAH PERBAIKANNYA ---
            
            # Cek jika path modul (e.g., 'anus.core') sudah mengandung
            # nama root folder (e.g., 'anus')
            if module_parts[0] == root_folder_name:
                # Jika ya, gabungkan root_folder + sisa parts
                # root_folder = '.../anus'
                # parts = ['core', 'agent']
                # hasil = '.../anus/core/agent'
                base_path = os.path.join(root_folder, *module_parts[1:])
            else:
                # Perilaku lama: gabungkan root_folder + semua parts
                # root_folder = '.../project_root' (parent of 'anus')
                # parts = ['anus', 'core', 'agent']
                # hasil = '.../project_root/anus/core/agent'
                base_path = os.path.join(root_folder, *module_parts)
            # print("base_path: ", base_path)
        else:
            current_dir = os.path.dirname(current_filepath)
            pkg_dir = current_dir
            for _ in range(level - 1):
                pkg_dir = os.path.dirname(pkg_dir)
                
            if module_name:
                base_path = os.path.join(pkg_dir, *module_name.split('.'))
            else:
                base_path = pkg_dir

        candidate_file = base_path + ".py"
        if os.path.isfile(candidate_file):
            return os.path.abspath(candidate_file)

        candidate_pkg = os.path.join(base_path, "__init__.py")
        if os.path.isfile(candidate_pkg):
            return os.path.abspath(candidate_pkg)

        return None

    # --- [HELPER BARU] ---
    def _get_node_name_str(self, node: ast.AST) -> Optional[str]:
        """
        Helper untuk mengubah node AST (seperti BaseAgent atau parents.BaseAgent)
        menjadi string.
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._get_node_name_str(node.value)
            if base:
                return f"{base}.{node.attr}"
        # Mengabaikan hal lain seperti ast.Call, dll.
        return None

    # --- Bagian 2: Inti Pelacakan Simbol (DIPERBARUI) ---

    def trace_symbol_origin(
        self,
        symbol_name: str,
        current_filepath: str,
        root_folder: str,
        visited: Optional[Set[Tuple[str, str]]] = None
    ) -> Optional[Tuple[str, str, str]]:
        """
        (DIPERBARUI TOTAL - "Navigator Jalur")
        Melacak 'jalur' simbol (e.g., "A.B.Class.method") secara rekursif.
        Menangani: Definisi, Re-export, Navigasi Sub-Modul, Pewarisan, dan Wildcard.
        """
        # print(f"trace_symbol_origin({symbol_name}, {current_filepath}, {root_folder})")
        
        if visited is None:
            visited = set()

        current_filepath = os.path.abspath(current_filepath)
        # Kunci visited harus (path, symbol_name) untuk mencegah rekursi tak terbatas
        visited_key = (current_filepath, symbol_name)
        if visited_key in visited:
            return None
        visited.add(visited_key)

        if not os.path.isfile(current_filepath):
            return None

        try:
            with open(current_filepath, "r", encoding="utf-8") as f:
                source = f.read()
            mod_tree = ast.parse(source, filename=current_filepath)
        except Exception as e:
            return None

        # Pisahkan misi:
        # e.g., "packageb.ClassName.method"
        parts = symbol_name.split('.')
        # e.g., "packageb"
        base_name_to_find = parts[0]
        # e.g., "ClassName.method"
        remaining_path = ".".join(parts[1:]) if len(parts) > 1 else None

        # --- PASS 1: Bangun Peta Impor Lokal ---
        # (Sama seperti sebelumnya, penting untuk pewarisan)
        local_imports = {}
        
        # --- REVISI DIMULAI: Tambahkan list untuk file wildcard ---
        wildcard_import_files = [] # List of (filepath)
        # --- REVISI SELESAI ---
        
        for node in mod_tree.body:
            if isinstance(node, ast.ImportFrom):
                source_module = node.module
                import_level = node.level
                
                # --- REVISI DIMULAI: Cek apakah ini wildcard ---
                is_wildcard = (len(node.names) == 1 and node.names[0].name == "*")
                
                if is_wildcard:
                    # Jika ya, kumpulkan path filenya
                    wildcard_path = self.static_resolve_module_path(
                        source_module, current_filepath, root_folder, import_level
                    )
                    if wildcard_path:
                        wildcard_import_files.append(wildcard_path)
                else:
                # --- REVISI SELESAI ---
                    
                    for alias in node.names:
                        alias_name = alias.asname or alias.name
                        local_imports[alias_name] = (source_module, alias.name, import_level)
            
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    alias_name = alias.asname or alias.name
                    # karena pasti absolute path kalau menggunakan Import 
                    local_imports[alias_name] = (alias.name, alias.name, 0)

        # --- PASS 2: Temukan Jalur (Definisi, Re-export, Navigasi) ---
        for node in mod_tree.body:
            
            # --- Kasus 1: Definisi Ditemukan (Base Case) ---
            
            # A. Kita mencari bagian terakhir dari jalur (e.g., 'funcb')
            if not remaining_path:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == base_name_to_find:
                    return (current_filepath, symbol_name, "function")
                if isinstance(node, ast.ClassDef) and node.name == base_name_to_find:
                    return (current_filepath, symbol_name, "class")
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                        if isinstance(target, ast.Name) and target.id == base_name_to_find:
                            return (current_filepath, symbol_name, "variable")

            # B. Kita menemukan Class, dan masih ada sisa path (e.g., 'ClassName.method')
            elif isinstance(node, ast.ClassDef) and node.name == base_name_to_find:
                # Ditemukan Class! e.g., 'ClassName'
                # Kita sekarang harus mencari sisa path: 'method'
                
                # Ini adalah logika pewarisan kita yang lama, yang sudah benar:
                method_name_to_find = remaining_path.split('.')[0]
                
                # Langkah A: Cek Self (check method untuk class saat ini)
                for inner_node in node.body:
                    if isinstance(inner_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if inner_node.name == method_name_to_find:
                            return (current_filepath, symbol_name, "method")
                
                # Langkah B: Cek Parent
                for parent_node in node.bases:
                    # e.g "ParentClass", "parent.ParentClass2"
                    parent_name_str = self._get_node_name_str(parent_node)
                    if not parent_name_str: continue
                    
                    parent_parts = parent_name_str.split('.')
                    
                    # untuk IF (CHECK LOCAL IMPORTS)
                    found_import = False
                    # Coba cocokan dari yang terpanjang: "packa.packb.Binatang" -> "packa.packb" -> "packa"
                    for i in range(len(parent_parts), 0, -1):
                        prefix = '.'.join(parent_parts[:i])
                        if prefix in local_imports:
                            # Ditemukan! (misal prefix="packa.packb")
                            source_module, original_name, level = local_imports[prefix]
                            
                            # Sisa atribut setelah prefix (misal ["Binatang"])
                            remaining_attrs = parent_parts[i:]
                            
                            next_filepath = self.static_resolve_module_path(
                                source_module, current_filepath, root_folder, level
                            )
                            
                            # Misi baru: "packa.packb" + ["Binatang"] + ["execute"]
                            new_symbol_to_trace = ".".join([original_name] + remaining_attrs + [method_name_to_find])
                            
                            if next_filepath and new_symbol_to_trace:
                                result = self.trace_symbol_origin(
                                    new_symbol_to_trace, next_filepath, root_folder, visited
                                )
                                if result:
                                    return result
                            
                            found_import = True # Tandai sudah ketemu impor eksplisit
                            break
                    
                    # untuk ELSE
                    if found_import:
                        continue
                    
                    # --- ELSE
                    
                    # Jika tidak ketemu di impor eksplisit, coba Wildcard & Lokal
                    # (Misi lokal menggunakan nama lengkap parent, misal "packa.packb.Binatang.execute")
                    parent_method_to_find = ".".join(parent_parts + [method_name_to_find])
                    
                    # (Cek 'wildcard_import_files' yang kita kumpulkan di Pass 1)
                    for wildcard_file_path in wildcard_import_files:
                        # Misi: "Cari 'Kedua.execute' di file 'A/__init__.py'"
                        result = self.trace_symbol_origin(
                            parent_method_to_find, # e.g., "Kedua.execute"
                            wildcard_file_path, 
                            root_folder, 
                            visited
                        )
                        if result:
                            return result # Ditemukan!
                    
                    # Prioritas 3: Lokal
                    result = self.trace_symbol_origin(
                        parent_method_to_find, current_filepath, root_folder, visited
                    )
                    if result: 
                        return result
                    
                    # --- END ELSE
                    
                # Jika sudah cek self dan semua parent tapi tidak ketemu
                return None 

            # --- Kasus 2: Re-export / Navigasi / Wildcard (ast.ImportFrom) ---
            if isinstance(node, ast.ImportFrom):
                source_module = node.module
                import_level = node.level
                
                # A. Cek Re-export Simbol (e.g., from .B import ClassName)
                for alias in node.names:
                    if (alias.asname or alias.name) == base_name_to_find:
                        if alias.name == "*": continue # Abaikan 'from . import * as X'
                        
                        original_base_name = alias.name
                        module_to_resolve = source_module
                        level_to_resolve = import_level
                        
                        # Bangun simbol baru untuk dilacak di file berikutnya
                        symbol_to_trace_in_next_file = ".".join([original_base_name] + parts[1:])
                        
                        # *** PERBAIKAN BUG LOOPING (Kasus 'from . import module_b') ***
                        if module_to_resolve is None:
                            module_to_resolve = original_base_name
                            symbol_to_trace_in_next_file = remaining_path # Lacak sisa path
                            
                            # if symbol_to_trace_in_next_file is None:
                            #     # Ini adalah base case, kita menemukan modul/paket itu sendiri
                            #     next_filepath = self.static_resolve_module_path(
                            #         module_to_resolve, current_filepath, root_folder, level_to_resolve
                            #     )
                            #     if next_filepath:
                            #         # Mengembalikan path file, nama asli, dan tipe 'module'
                            #         return (next_filepath, symbol_name, original_base_name, "module")
                            #     else:
                            #         continue # Gagal resolve
                        # *** AKHIR PERBAIKAN BUG ***

                        next_filepath = self.static_resolve_module_path(
                            module_to_resolve, current_filepath, root_folder, level_to_resolve
                        )
                        if next_filepath:
                            return self.trace_symbol_origin(
                                symbol_to_trace_in_next_file, next_filepath, root_folder, visited
                            )

                # B. Cek Navigasi Sub-Modul (e.g., from . import packageb)
                # (Logika ini sekarang sudah ditangani oleh "PERBAIKAN BUG LOOPING" di atas
                #  ketika 'source_module' adalah 'None')
                
                # C. Cek Wildcard (e.g., from .B import *)
                if len(node.names) == 1 and node.names[0].name == "*":
                    next_filepath = self.static_resolve_module_path(
                        source_module, current_filepath, root_folder, import_level
                    )
                    if next_filepath:
                        # Lacak NAMA YANG SAMA (e.g., "ClassName.method")
                        # di file berikutnya
                        result = self.trace_symbol_origin(
                            symbol_name, next_filepath, root_folder, visited
                        )
                        if result:
                            return result # Ditemukan via wildcard

            # --- Kasus 3: Navigasi via 'import A.B as C' ---
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    # e.g., import A.B as B
                    visible_name = alias.asname or alias.name # e.g., "B"
                    original_name = alias.name # e.g., "A.B"

                    # Cek jika nama yang terlihat ('B') cocok dengan target kita ('B')
                    if visible_name == base_name_to_find:
                        # Cocok! Kita perlu melanjutkan pelacakan.
                        
                        # 1. Temukan file untuk impor ASLI ('A.B')
                        next_filepath = self.static_resolve_module_path(
                            original_name, # 'A.B'
                            current_filepath, 
                            root_folder, 
                            level=0 # ast.Import selalu absolut
                        )
                        
                        if next_filepath:
                            # 2. Tentukan misi baru (apa yang harus dilacak di file baru)
                            new_symbol_to_trace = None
                            if remaining_path:
                                # Misi: "B.C.D" -> lacak "C.D" di file 'A.B'
                                new_symbol_to_trace = remaining_path
                            else:
                                # Misi: "B" -> lacak bagian terakhir dari
                                # impor asli di file 'A.B'
                                # e.g., import A.B as B -> lacak "B"
                                new_symbol_to_trace = original_name.split('.')[-1]
                                
                            return self.trace_symbol_origin(
                                new_symbol_to_trace,
                                next_filepath,
                                root_folder,
                                visited
                            )
        # Jika tidak ada yang ditemukan di file ini
        return None

    # --- Bagian 2: Fungsi Utama (Entrypoint) (VERSI ROMBAKAN FINAL) ---
    def find_true_origin(
        self,
        entry_file_path: str,
        component_name: str,
        project_root: str
    ) -> Optional[Tuple[str, str, str]]:
        """
        (ROMBAKAN TOTAL - "Sistem Penawaran")
        Menemukan 'kecocokan impor' terbaik (paling spesifik) di file entri
        untuk memulai pelacakan. Menangani semua jenis impor.
        """
        
        try:
            with open(entry_file_path, "r", encoding="utf-8") as f:
                source = f.read()
            entry_tree = ast.parse(source, filename=entry_file_path)
        except Exception as e:
            print(f"Error parsing entry file {entry_file_path}: {e}")
            return None

        # (match_length, start_file, symbol_to_trace)
        best_match = (-1, None, None)
        
        # --- REVISI DIMULAI: Tambahkan list untuk kandidat wildcard ---
        wildcard_candidates = [] # Ini adalah list baru
        # --- REVISI SELESAI ---

        for node in entry_tree.body:
            
            current_match_len = -1
            current_start_file = None
            current_symbol_to_trace = None

            # --- Kasus 1: 'from A.B import C as D' ---
            if isinstance(node, ast.ImportFrom):
                source_module = node.module
                import_level = node.level
                
                for alias in node.names:
                    visible_name = alias.asname or alias.name
                    original_name = alias.name
                    
                    match_len = -1
                    symbol_to_trace = None

                    # Cek 1: Cocok dengan ALIAS (e.g., component="mb.greet_b")
                    if component_name == visible_name or component_name.startswith(visible_name + "."):
                        match_len = len(visible_name.split('.'))
                        
                        if original_name == "*":
                            symbol_to_trace = component_name # Lacak nama asli
                        else:
                            parts = component_name.split('.')
                            parts[0] = original_name # Ganti 'mb' dengan 'module_b'
                            symbol_to_trace = ".".join(parts)
                    
                    # Cek 2: Cocok dengan NAMA ASLI (e.g., component="module_b.greet_b")
                    elif component_name == original_name or component_name.startswith(original_name + "."):
                        match_len = len(original_name.split('.'))
                        symbol_to_trace = component_name # Nama sudah benar
                    
                    # Perbarui kecocokan untuk alias ini
                    if match_len > current_match_len:
                        current_match_len = match_len
                        current_start_file = self.static_resolve_module_path(
                            source_module, entry_file_path, project_root, import_level
                        )
                        current_symbol_to_trace = symbol_to_trace

                # Cek Wildcard (prioritas terendah)
                if len(node.names) == 1 and node.names[0].name == "*":
                    wildcard_start_file = self.static_resolve_module_path(
                        source_module, entry_file_path, project_root, import_level
                    )
                    if wildcard_start_file:
                        # Kumpulkan semua kandidat, jangan hanya satu
                        wildcard_candidates.append(
                            (wildcard_start_file, component_name)
                        )

            # --- Kasus 2: 'import A.B as C' ---
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    visible_name = alias.asname or alias.name
                    original_name = alias.name # e.g., "A.B"

                    # Cek jika component_name cocok dengan nama yang terlihat
                    if component_name == visible_name or component_name.startswith(visible_name + "."):
                        
                        match_len = len(visible_name.split('.'))
                        
                        if match_len > current_match_len:
                            current_match_len = match_len
                            current_start_file = self.static_resolve_module_path(
                                original_name, entry_file_path, project_root, level=0
                            )
                            
                            # Hitung sisa path
                            parts = component_name.split('.')
                            visible_parts_len = len(visible_name.split('.'))
                            
                            if len(parts) == visible_parts_len:
                                # Kita mencari 'A.B' dan mengimpor 'A.B'
                                # Lacak bagian terakhir di file target
                                # e.g., lacak 'B' di 'A/B/__init__.py'
                                current_symbol_to_trace = original_name.split('.')[-1]
                            else:
                                # Kita mencari 'A.B.C' dan mengimpor 'A.B'
                                # Lacak 'C' di 'A/B/__init__.py'
                                current_symbol_to_trace = ".".join(parts[visible_parts_len:])

            # Perbarui kecocokan terbaik (best match) dari node ini
            if current_start_file and current_match_len > best_match[0]:
                best_match = (current_match_len, current_start_file, current_symbol_to_trace)

        # --- Setelah Loop: Lakukan Pelacakan ---
        
        final_match_len, final_start_file, final_symbol_to_trace = best_match

        # Prioritas 1: Coba kecocokan eksplisit terbaik (jika ada)
        # (Skor > 0 berarti ini BUKAN wildcard)
        if final_match_len > 0: 
            if final_start_file:
                return self.trace_symbol_origin(
                    final_symbol_to_trace,
                    final_start_file,
                    project_root
                )

        # Prioritas 2: Coba semua kandidat wildcard satu per satu
        # (Hanya dijalankan jika tidak ada kecocokan eksplisit yang ditemukan)
        if wildcard_candidates:
            for start_file, symbol_to_trace in wildcard_candidates:
                result = self.trace_symbol_origin(
                    symbol_to_trace,
                    start_file,
                    project_root
                )
                # Jika ditemukan, segera kembalikan
                if result:
                    return result 

        # Jika Prioritas 1 dan 2 gagal
        # print(f"Tidak dapat menemukan pernyataan import untuk basis '{component_name}' di {entry_file_path}")
        return None


class AlternativeDependencyResolver(DependencyResolver):
    """
    Resolves dependencies using an alternative, perhaps faster or simpler, method.
    """
    def resolve(self, relevant_files: List[Path]) -> None:
        print("\nResolving dependencies using an alternative method...")

        entry_points = [
            str(p) for p in relevant_files
        ]

        if not entry_points:
            print(f"[DependencyResolver] No Python files found to analyze in {self.repo_path} after filtering.")
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

            print("[DependencyResolver] PyCG execution successful.")

        except FileNotFoundError:
            logger.error_print(
                f"PyCG executable not found at '{settings.PYCG_PYTHON_EXECUTABLE}'. "
                "Please check the PYCG_PYTHON_EXECUTABLE path in your .env file."
            )
            # Anda bisa melempar exception custom di sini jika perlu
            raise
        except subprocess.CalledProcessError as e:
            # Ini akan terjadi jika PyCG gagal (misal, error parsing)
            logger.error_print(f"PyCG execution failed with return code {e.returncode}")
            logger.error_print(f"PyCG stderr: {e.stderr}")
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
                    
                    if normalized_callee != component.id:
                        component.depends_on.add(normalized_callee)

        logger.info_print("Finished mapping PyCG results.")
        
class V1PrimaryDependencyResolver(DependencyResolver):
    """
    Resolves dependencies using the primary, detailed analysis method.
    (Ini adalah logika dari kode Anda saat ini)
    """
    def resolve(self, relevant_files: List[Path]) -> None:
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
                logger.warning_print(f"Error analyzing dependencies in {file_path}: {e}")