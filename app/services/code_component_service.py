from typing import List, Dict, Any, Optional, Union, Tuple
import ast
from app.schemas.models.code_component_schema import CodeComponent
from app.services.documentation_service import get_record_from_database, convert_dicts_to_code_components
import os

import ast
from typing import Optional, List, Dict, Any


class NodeFinder(ast.NodeVisitor):
    """
    Visitor ini mencari satu node spesifik (fungsi, kelas, method)
    berdasarkan rentang baris yang *tepat* (termasuk logika decorator Anda).
    """
    def __init__(self, target_start: int, target_end: int):
        self.target_start = target_start
        self.target_end = target_end
        self.found_node: Optional[ast.AST] = None

    def _check_node(self, node: ast.AST):
        # Jika kita sudah menemukan node, hentikan pencarian lebih dalam
        if self.found_node:
            return

        # ---- LOGIKA KUNCI (Sesuai instruksi Anda) ----
        node_start_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
        node_end_line = getattr(node, "end_lineno", node.lineno)
        # ----------------------------------------------

        if (node_start_line == self.target_start and
            node_end_line == self.target_end):
            
            self.found_node = node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_node(node)
        self.generic_visit(node) # Tetap kunjungi nested function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_node(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._check_node(node)
        self.generic_visit(node) # Kunjungi method/class di dalam class ini

    def find(self, tree: ast.Module) -> Optional[ast.AST]:
        """Metode helper untuk menjalankan visitor dan mengembalikan hasil."""
        self.visit(tree)
        return self.found_node


# --- 3. Logika Inti: Hidrasi AST ---
def source_code_getter(source: str, start_line: int, end_line: int) -> str:
    """Get source code segment for an AST node."""
    try:
        # Fallback to manual extraction
        lines = source.splitlines()
        # Koreksi: pastikan kita mengambil baris *termasuk* end_line
        segment_lines = lines[start_line - 1:end_line] 
        return "\n".join(segment_lines)
    
    except Exception as e:
        print(f"[SOURCE GETTER] Error getting source segment: {e}")
        return ""

def _get_ast_tree_from_cache(
    file_path: str, 
    # REVISI 1: Tipe cache diubah untuk menyimpan (Tree, Source String)
    ast_cache: Dict[str, Optional[Tuple[ast.Module, str]]]
) -> Optional[Tuple[ast.Module, str]]:
    """
    Membaca, mem-parse, dan menyimpan AST *dan* source string file dalam cache.
    Mengembalikan tuple (ast.Module, str) atau None jika gagal.
    """
    # 1. Cek apakah sudah ada di cache
    if file_path not in ast_cache:
        try:
            if not os.path.exists(file_path):
                print(f"[AST ERROR] File tidak ditemukan: {file_path}")
                ast_cache[file_path] = None
                return None

            # Baca dan parse file
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read() # <-- Simpan source string
            
            parsed_tree = ast.parse(source_code, filename=file_path)
            
            # REVISI 2: Simpan tuple (Tree, Source) ke cache
            ast_cache[file_path] = (parsed_tree, source_code)
        
        except Exception as e:
            print(f"[AST ERROR] Gagal mem-parse {file_path}: {e}")
            ast_cache[file_path] = None
            return None
    
    # 2. Kembalikan dari cache
    return ast_cache[file_path]

def hydrate_components_with_ast(
    components: List[CodeComponent],
    root_folder_path: str
) -> List[CodeComponent]:
    
    # REVISI 1: Tipe cache diubah
    ast_cache: Dict[str, Optional[Tuple[ast.Module, str]]] = {}
    hydrated_list: List[CodeComponent] = []

    for comp in components:
        if not comp.relative_path or comp.start_line == 0:
            print(f"[HYDRATE SKIP] Komponen {comp.id} tidak memiliki relative_path atau start_line.")
            continue

        absolute_file_path = os.path.join(root_folder_path, comp.relative_path)
        
        # REVISI 2: Ambil hasil cache (sekarang berupa tuple atau None)
        cache_result = _get_ast_tree_from_cache(absolute_file_path, ast_cache)

        # Jika file gagal di-parse, lewati komponen ini
        if cache_result is None:
            # Pesan error sudah dicetak oleh _get_ast_tree_from_cache
            print(f"[HYDRATE SKIP] Melewati {comp.id} karena file gagal di-parse.")
            continue
        
        # REVISI 3: Bongkar tuple hasil cache
        full_ast_tree, source_code_string = cache_result
        
        # 2. Cari node spesifik di dalam pohon AST tersebut
        finder = NodeFinder(target_start=comp.start_line, target_end=comp.end_line)
        found_node = finder.find(full_ast_tree)

        # 3. "Hidrasi" objek komponen
        if found_node:
            # --- REVISI 4: Panggil source_code_getter ---
            comp.source_code = source_code_getter(
                source=source_code_string,
                start_line=comp.start_line,
                end_line=comp.end_line
            )
            # --------------------------------------------
            
            comp.node = found_node  # <-- ATRIBUT NODE DIISI DI SINI
            hydrated_list.append(comp)
        else:
            print(f"[HYDRATE WARN] Tidak dapat menemukan node AST untuk {comp.id} "
                  f"di {comp.relative_path} (L:{comp.start_line}-L:{comp.end_line})")
            
    print(f"Hidrasi selesai. {len(hydrated_list)} dari {len(components)} komponen berhasil dihidrasi.")
    return hydrated_list


def get_hydrated_components_for_record(
    root_folder_path: str,
    record_code: str, 
    collection: str = "documentation_results"
) -> List[CodeComponent]:
    
    record_doc = get_record_from_database(
        record_code=record_code, 
        collection=collection,
        sidebar_mode=False 
    )
    
    if not record_doc or 'components' not in record_doc:
        print(f"[MAIN] Tidak ada komponen ditemukan untuk record {record_code}")
        return []
        
    # 2. Konversi kamus (dict) menjadi objek CodeComponent (node=None)
    component_dicts = record_doc['components']
    initial_components = convert_dicts_to_code_components(component_dicts)
    
    if not initial_components:
        print(f"[MAIN] Gagal mengonversi dicts komponen untuk {record_code}")
        return []
    
    # 3. "Hidrasi" daftar ini dengan mengisi atribut .node
    hydrated_list = hydrate_components_with_ast(initial_components, root_folder_path)
    
    return hydrated_list

def map_components_by_id(
    components: List[CodeComponent]
) -> Dict[str, CodeComponent]:
    
    return {comp.id: comp for comp in components}