import ast
import re
from typing import Dict, List, Optional, Set, Any
import os
from dataclasses import dataclass, field

from app.evaluator.base import BaseEvaluator
from app.schemas.models.code_component_schema import CodeComponent

def _is_not_empty(value: Any) -> bool:
    """
    Memeriksa apakah nilai dari JSON dianggap "ada" (tidak None,
    string tidak kosong, list/dict tidak kosong).
    """
    if value is None:
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0
    if isinstance(value, (list, dict)):
        return len(value) > 0
    # Jika tipe lain (misal angka 0, boolean False), anggap "ada"
    return True

class InitVisitor(ast.NodeVisitor):
    """Mendeteksi penetapan atribut (self.x = ...) di dalam __init__."""
    def __init__(self):
        self.has_attributes: bool = False

    def visit_Assign(self, node: ast.Assign):
        """Mendeteksi: self.foo = ..."""
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                if isinstance(target.value, ast.Name) and target.value.id == 'self':
                    self.has_attributes = True
                    break # Kita hanya perlu tahu ada satu
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        """Mendeteksi: self.foo: int = ..."""
        target = node.target
        if isinstance(target, ast.Attribute):
            if isinstance(target.value, ast.Name) and target.value.id == 'self':
                self.has_attributes = True
        self.generic_visit(node)

class ClassBodyVisitor(ast.NodeVisitor):
    """
    Menganalisis isi (body) dari sebuah class untuk menemukan node __init__
    dan mendeteksi keberadaan atribut.
    """
    def __init__(self):
        self.init_node: Optional[ast.FunctionDef] = None
        self.has_class_attributes: bool = False
        self.has_init_attributes: bool = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Mencari node __init__."""
        if node.name == '__init__':
            self.init_node = node
            
            # Sekarang, periksa *di dalam* __init__ untuk self.foo = ...
            init_visitor = InitVisitor()
            for body_item in node.body:
                init_visitor.visit(body_item)
            
            if init_visitor.has_attributes:
                self.has_init_attributes = True
        
        # Jangan kunjungi fungsi lain di dalam class
        # self.generic_visit(node) # <-- SENGAKA DI-NONAKTIFKAN

    def visit_Assign(self, node: ast.Assign):
        """Mendeteksi atribut level kelas: CLS_VAR = ..."""
        # (Ini deteksi sederhana, bisa jadi targetnya bukan nama
        # tapi cukup baik untuk saat ini)
        self.has_class_attributes = True
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        """Mendeteksi atribut level kelas: CLS_VAR: int = ..."""
        # (terutama untuk dataclass atau type hinting)
        if not isinstance(node.target, ast.Name):
            # Ini mungkin `self.foo: int` di dalam method, abaikan
            pass
        else:
            self.has_class_attributes = True
        self.generic_visit(node)
        
    def visit_ClassDef(self, node: ast.ClassDef):
        """Abaikan nested class."""
        pass

class ClassCompletenessEvaluator(BaseEvaluator):
    def __init__(self):
        super().__init__(
            name="Class Completeness Evaluator",
            description="Evaluates the completeness of class docstrings",
        )

        # 1. Definisikan Elemen dan Pemetaan JSON
        elements = ["summary", "description", "parameters", "attributes", "examples"]

        self.element_key_map = {
            "summary": "short_summary",
            "description": "extended_summary",
            "parameters": "parameters",
            "attributes": "attributes",
            "examples": "examples"
        }

        # 2. Inisialisasi State
        self.element_scores = {el: False for el in elements}
        self.element_required = {el: False for el in elements}
        self.weights = [1 / len(elements)] * len(elements) # Bobot sama rata
        self.required_sections: Set[str] = set()


    def evaluate(self, component: CodeComponent) -> float:
        """
        Mengevaluasi kelengkapan docstring sebuah class.
        """
        
        if not isinstance(component.node, ast.ClassDef):
             print(f"[EVALUATOR ERROR] Komponen {component.id} bukan class.")
             return 0.0
             
        node = component.node
        
        # 1. Tentukan seksi WAJIB berdasarkan AST
        self.required_sections = self._get_required_sections(node)

        # 2. Reset skor dan perbarui status 'wajib'
        self.element_scores = {key: False for key in self.element_scores}
        self.element_required = {
            key: key in self.required_sections for key in self.element_scores
        }

        # 3. Periksa Dokumentasi JSON
        doc_json = component.docgen_final_state.get("final_state", {}).get("documentation_json")
        
        if not doc_json or not isinstance(doc_json, dict):
            print(f"[EVALUATOR WARN] Tidak ada 'documentation_json' ditemukan untuk {component.id}")
        else:
            # Isi self.element_scores berdasarkan pengecekan JSON
            for element_name, json_key in self.element_key_map.items():
                json_value = doc_json.get(json_key)
                if _is_not_empty(json_value): # Asumsi _is_not_empty ada
                    self.element_scores[element_name] = True
        
        # 4. Hitung skor akhir
        total_weight = 0.0
        weighted_score = 0.0

        for element_name, score in self.element_scores.items():
            weight = self.weights[list(self.element_scores.keys()).index(element_name)]
            required = self.element_required.get(element_name, False)

            if required:
                total_weight += weight
                if score: # Jika True
                    weighted_score += weight
        
        if total_weight == 0.0 and not self.required_sections:
             return 1.0 # Sempurna jika tidak ada yang di-require
        
        self.score = weighted_score / total_weight if total_weight > 0 else 0.0
        
        return self.score


    def _get_required_sections(self, node: ast.ClassDef) -> Set[str]:
        """
        Menentukan seksi apa yang wajib ada di docstring class
        berdasarkan analisis AST.
        """
        required: Set[str] = set()

        # 1. Summary & Description (Wajib jika class tidak kosong)
        required.add("summary")
        if node.end_lineno and (node.end_lineno - node.lineno > 0):
             required.add("description")
             
        # 2. Examples (jika bukan private)
        if not node.name.startswith('_'):
            required.add("examples")
            
        # 3. Jalankan Visitor untuk memeriksa isi (body) class
        visitor = ClassBodyVisitor()
        for body_item in node.body:
            visitor.visit(body_item)
            
        # 4. Cek Parameters (berdasarkan __init__ yang ditemukan)
        if visitor.init_node:
            args = visitor.init_node.args
            all_arg_names = [a.arg for a in args.posonlyargs] + \
                            [a.arg for a in args.args] + \
                            [a.arg for a in args.kwonlyargs]
            if args.vararg:
                all_arg_names.append(args.vararg.arg)
            if args.kwarg:
                all_arg_names.append(args.kwarg.arg)
            
            # Cek jika ada parameter SELAIN 'self'
            if len(all_arg_names) > 1 or \
               (len(all_arg_names) == 1 and all_arg_names[0] != 'self'):
                required.add("parameters")

        # 5. Cek Attributes
        if visitor.has_class_attributes or visitor.has_init_attributes:
            required.add("attributes")

        return required

class FunctionBodyVisitor(ast.NodeVisitor):
    """
    Visitor AST helper untuk memeriksa *di dalam* isi (body) fungsi
    untuk kata kunci spesifik seperti return, yield, raise, dan warn.
    """
    def __init__(self):
        self.has_return_with_value: bool = False
        self.has_yield: bool = False
        self.has_raise: bool = False
        self.has_warn: bool = False
        super().__init__()

    def visit_Return(self, node: ast.Return):
        """Mendeteksi: return some_value"""
        # (b) Kita hanya peduli jika ada *nilai* yang dikembalikan.
        # 'return' saja (None) tidak memerlukan dokumentasi 'returns'.
        if node.value is not None:
            self.has_return_with_value = True
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield):
        """Mendeteksi: yield some_value"""
        # (c) Menemukan 'yield'
        self.has_yield = True
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom):
        """Mendeteksi: yield from some_generator"""
        # (c) 'yield from' juga dihitung sebagai 'yields'
        self.has_yield = True
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        """Mendeteksi: raise Exception"""
        # (d) Menemukan 'raise'
        self.has_raise = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Mendeteksi: warnings.warn(...)"""
        # (e) Ini adalah deteksi heuristik (perkiraan)
        if isinstance(node.func, ast.Attribute):
            # Cek apakah ini 'something.warn'
            if node.func.attr == 'warn':
                # Cek apakah 'something' adalah 'warnings'
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'warnings':
                    self.has_warn = True
        self.generic_visit(node)

class FunctionCompletenessEvaluator(BaseEvaluator):
    """
    Evaluator for function completeness.
    """

    def __init__(self):
        super().__init__(
            name="Function Completeness Evaluator",
            description="Evaluates the completeness of function documentation",
        )

        # Initialize element scores and requirements
        elements = ["summary", "description", "parameters", "returns", "yields", "raises", "warns", "examples"]

        self.element_key_map = {
            "summary": "short_summary",
            "description": "extended_summary",
            "parameters": "parameters",
            "returns": "returns",
            "yields": "yields",
            "raises": "raises",
            "warns": "warns",
            "examples": "examples"
        }

        self.element_scores = {el: False for el in elements}
        self.element_required = {
            el: False for el in elements
        }  # Will be set during evaluation
        self.weights = [1 / len(elements)] * len(elements)

    def evaluate(self, component: CodeComponent) -> float:
        """
        Evaluates the completeness of a function docstring.
        """
        
        node = component.node
        
        # Get required sections for this function first
        self.required_sections = self._get_required_sections(node)

        # Reset scores and update requirements
        self.element_scores = {key: False for key in self.element_scores}
        self.element_required = {
            key: key in self.required_sections for key in self.element_scores
        }

        # Check each element completeness
        doc_json = component.docgen_final_state.get("final_state", {}).get("documentation_json")
        
        if not doc_json or not isinstance(doc_json, dict):
            print(f"[EVALUATOR WARN] Tidak ada 'documentation_json' ditemukan untuk {component.id}")
            # Jika tidak ada JSON, semua skor akan 0 (False)
        else:
            # Isi self.element_scores berdasarkan pengecekan JSON
            for element_name, json_key in self.element_key_map.items():
                
                # Cek apakah nilai di JSON tidak kosong
                json_value = doc_json.get(json_key)
                if _is_not_empty(json_value):
                    self.element_scores[element_name] = True

        # Calculate weighted score considering requirements
        total_weight = 0.0
        weighted_score = 0.0

        for (key, score), weight, required in zip(
            self.element_scores.items(), self.weights, self.element_required.values()
        ):
            if required:
                total_weight += weight
                if score:
                    weighted_score += weight

        self.score = weighted_score / total_weight if total_weight > 0 else 0.0
        return self.score

    def _get_required_sections(
        self, node: (ast.FunctionDef | ast.AsyncFunctionDef)
    ) -> Set[str]:
        """
        Determines which sections are required for the function docstring
        based on its AST.
        """
        # Set agar tidak ada duplikat
        required: Set[str] = {"summary", "description"}
        args = node.args

        # 1. (a) Cek Parameters (abaikan jika hanya 'self')
        all_arg_names = [a.arg for a in args.posonlyargs] + \
                        [a.arg for a in args.args] + \
                        [a.arg for a in args.kwonlyargs]
        if args.vararg:
            all_arg_names.append(args.vararg.arg)
        if args.kwarg:
            all_arg_names.append(args.kwarg.arg)
        
        if len(all_arg_names) > 1 or \
           (len(all_arg_names) == 1 and all_arg_names[0] != 'self'):
            required.add("parameters")

        # 2. (f) Cek Examples (jika bukan private)
        is_abstract = False
        for decorator in node.decorator_list:
            decorator_name = ""
            if isinstance(decorator, ast.Name):
                decorator_name = decorator.id
            elif isinstance(decorator, ast.Attribute):
                decorator_name = decorator.attr
            elif isinstance(decorator, ast.Call):
                # Handle @decorator()
                if isinstance(decorator.func, ast.Name):
                    decorator_name = decorator.func.id
                elif isinstance(decorator.func, ast.Attribute):
                    decorator_name = decorator.func.attr

            if decorator_name == 'abstractmethod':
                is_abstract = True
                break
        
        # 3. (f.2) Cek Examples (jika bukan private DAN BUKAN abstract)
        if not node.name.startswith('_') and not is_abstract:
            required.add("examples")

        # 3. Jalankan Visitor untuk memeriksa isi (body) fungsi
        visitor = FunctionBodyVisitor()
        for body_item in node.body:
            visitor.visit(body_item)

        # 4. (b) Cek Returns
        # Cek apakah anotasi 'returns' ada TAPI BUKAN 'None'
        has_meaningful_return_annotation = False
        if node.returns is not None:
            # Cek apakah ini '-> None'
            is_none_annotation = False
            if isinstance(node.returns, ast.Constant) and node.returns.value is None:
                # Python 3.8+
                is_none_annotation = True
            elif isinstance(node.returns, ast.NameConstant) and node.returns.value is None:
                # Python < 3.8
                is_none_annotation = True
                
            if not is_none_annotation:
                has_meaningful_return_annotation = True

        # Wajib jika ada anotasi (-> str) ATAU ada (return "value")
        if has_meaningful_return_annotation or visitor.has_return_with_value:
            required.add("returns")

        # 5. (c) Cek Yields
        if visitor.has_yield:
            required.add("yields")
            # Jika ada 'yield', 'return' biasanya tidak didokumentasikan
            # (Tergantung style guide, tapi kita bisa hapus 'returns' jika 'yields' ada)
            required.discard("returns") 

        # 6. (d) Cek Raises
        if visitor.has_raise:
            required.add("raises")

        # 7. (e) Cek Warns
        if visitor.has_warn:
            required.add("warns")

        return required


@dataclass
class CompletenessResultRow:
    """Menyimpan data hasil evaluasi terstruktur untuk satu komponen."""
    component_id: str
    component_type: str  # <-- REVISI: Tambahkan tipe komponen
    score: float
    required: Set[str] = field(default_factory=set)
    missing: Set[str] = field(default_factory=set)


# --- LANGKAH 3: Buat Fungsi Formatter dan Penyimpanan ---
def save_completeness_report(
    results: List[CompletenessResultRow], 
    output_dir: str,
    overall_score: float,
    total_components: int  # <-- REVISI 1: Terima argumen baru
):
    """Memformat hasil evaluasi menjadi tabel teks dan menyimpannya."""
    
    headers = ["Component", "Type", "Score", "Required Sections", "Missing Sections"]
    
    # --- Pass 1: Persiapan data dan kalkulasi lebar kolom ---
    
    col_widths = [len(h) for h in headers]
    prepared_rows = []
    
    for res in results:
        # Ambil data dari hasil (termasuk tipe)
        component_name = res.component_id
        type_str = res.component_type  # (Sudah di-capitalize dari fungsi sebelumnya)
        score_str = f"{res.score:.2%}"
        required_str = ", ".join(sorted(res.required)) or "-"
        missing_str = ", ".join(sorted(res.missing)) or "-"
        
        row_data = [component_name, type_str, score_str, required_str, missing_str]
        prepared_rows.append(row_data)
        
        col_widths[0] = max(col_widths[0], len(component_name))
        col_widths[1] = max(col_widths[1], len(type_str))
        col_widths[2] = max(col_widths[2], len(score_str))
        col_widths[3] = max(col_widths[3], len(required_str))
        col_widths[4] = max(col_widths[4], len(missing_str))

    # --- Pass 2: Pembuatan string tabel ---
    report_lines = []
    
    overall_line_1 = f"Overall Completeness Score: {overall_score:.2%}"
    overall_line_2 = f"Total Components Evaluated: {total_components}"
    separator = "=" * max(len(overall_line_1), len(overall_line_2))
    
    report_lines.append(overall_line_1)
    report_lines.append(overall_line_2)
    report_lines.append(separator)
    report_lines.append("\n")  # Tambahkan spasi sebelum tabel
    
    # Buat Header
    header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    report_lines.append(header_line)
    
    # Buat Separator (pemisah)
    separator_line = "-+-".join("-" * w for w in col_widths)
    report_lines.append(separator_line)
    
    # Buat Baris Data
    for row in prepared_rows:
        row_line = " | ".join(item.ljust(w) for item, w in zip(row, col_widths))
        report_lines.append(row_line)
        
    final_report = "\n".join(report_lines)
    
    # --- Tulis ke File (Tidak ada perubahan) ---
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        output_path = os.path.join(output_dir, "completeness_report.txt")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_report)
            
        print(f"\n[EVALUATOR] Laporan kelengkapan berhasil disimpan di:\n{output_path}")
        
    except Exception as e:
        print(f"\n[EVALUATOR ERROR] Gagal menyimpan laporan: {e}")