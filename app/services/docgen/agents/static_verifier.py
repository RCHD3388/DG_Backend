from typing import Optional, Dict, Any, List, Set, Literal, Tuple
from pydantic import BaseModel, Field
import ast
import re
from app.schemas.models.code_component_schema import CodeComponent
from app.services.docgen.agents.agent_output_schema import NumpyDocstring, SingleCallVerificationReport

class StaticVerifier:
    """
    Melakukan verifikasi faktual yang cepat dan gratis menggunakan AST.
    """
    
    def __init__(self, writer_verifier_version):
        self.writer_verifier_version = writer_verifier_version
    
    def _normalize_type_str(self, s: Optional[str]) -> str:
        """Menormalkan string tipe data untuk perbandingan yang konsisten."""
        if not s:
            return ""
        # Menghapus spasi dan tanda kurung ekstra dari 'Dict[(str, Any)]'
        s_normalized = s.replace('"', "'").replace(r'\"', "'")
        return re.sub(r'[\s\(\)]', '', s_normalized)

    def verify(self, component: CodeComponent, doc: NumpyDocstring) -> List[str]:
        # if self.writer_verifier_version == "v2":
        #     return self.verify_v2(component, doc)
        # else:
        #     return self.verify_vbase(component, doc)
        return self.verify_v2(component, doc)
        
    def verify_v2(self, component: CodeComponent, doc: NumpyDocstring) -> List[str]:
        """
        Menjalankan semua pemeriksaan statis dan mengembalikan daftar temuan (string kesalahan).
        """
        findings = []
        node = component.node
        
        # Normalisasi nama parameter dengan menghapus awalan '*'
        # '**kwargs' -> 'kwargs'
        # '*args'    -> 'args'
        doc_params = {p.name.lstrip('*') for p in (doc.parameters or [])}
        doc_raises = {r.error for r in (doc.raises or [])}
        
        ast_params, ast_return_type = self._get_signature_truth(node)
        ast_raises = self._get_raises_truth(node)
        ast_has_yield = self._get_yield_truth(node)
        
        # Normalisasi nama parameter AST juga
        ast_params_set = {name.lstrip('*') for name in ast_params.keys()}

        # --- Pemeriksaan 1: Parameter (Sekarang menggunakan set yang sudah dinormalisasi) ---
        missing_in_doc = ast_params_set - doc_params
        hallucinated_in_doc = doc_params - ast_params_set
        
        for param in missing_in_doc:
            if param != 'self': 
                findings.append(f"[Static] Parameter '{param}' ada di kode tapi HILANG atau TIDAK DIBERIKAN pada dokumentasi.")
        
        for param in hallucinated_in_doc:
            # Kita tampilkan nama asli dari docstring (dengan '**') agar jelas
            original_doc_name = next((p.name for p in (doc.parameters or []) if p.name.lstrip('*') == param), param)
            findings.append(f"[Static] Parameter '{original_doc_name}' ada di dokumentasi tapi TIDAK ADA di kode (halusinasi).")

        # --- Pemeriksaan 2: Tipe Data ---
        if doc.parameters:
            for param in doc.parameters:
                # Normalisasi nama param dari docstring sebelum mengecek di dict ast_params
                normalized_param_name = param.name.lstrip('*') 
                
                # memastikan hanya yang terdapat type hint saja yang akan diperiksa
                if normalized_param_name in ast_params and ast_params[normalized_param_name]:
                    ast_type = self._normalize_type_str(ast_params[normalized_param_name]) 
                    doc_type = self._normalize_type_str(param.type)
                    
                    if ast_type and doc_type and ast_type != doc_type:
                         findings.append(f"[Static] Parameter '{param.name}' memiliki type hint '{ast_params[normalized_param_name]}' di kode, tapi didokumentasikan sebagai '{param.type}'.")

        # --- Pemeriksaan 3: Tipe Return ---
        if doc.returns:
            doc_return_type = self._normalize_type_str(doc.returns[0].type)
            ast_return_type_norm = self._normalize_type_str(ast_return_type)
            
            if ast_return_type_norm and doc_return_type and ast_return_type_norm != doc_return_type:
                findings.append(f"[Static] Fungsi memiliki return hint '{ast_return_type}' di kode, tapi didokumentasikan sebagai '{doc.returns[0].type}'.")

        # if class return
        if component.component_type == "class":
            return findings

        # --- Pemeriksaan 4: Raises ---
        missing_raises_in_doc = ast_raises - doc_raises
        for err in missing_raises_in_doc:
            findings.append(f"[Static] Kode terlihat me-raise '{err}', tapi ini HILANG / TIDAK DIBERIKAN pada bagian 'raises' di dokumentasi.")
            
        hallucinated_raise_in_doc =  doc_raises - ast_raises
        for err in hallucinated_raise_in_doc:
            findings.append(f"[Static] Dokumentasi mencantumkan raises {err}, tapi *error* ini tidak ditemukan di-*raise* secara eksplisit di dalam kode (Halusinasi).")
        
        # --- Pemeriksaan 5: Yield ---
        doc_has_yield = bool(doc.yields)
        if ast_has_yield and not doc_has_yield:
            findings.append("[Static] Kode ini adalah generator (menggunakan 'yield'), tapi HILANG / TIDAK DIBERIKAN pada bagian 'yields' di dokumentasi.")
        
        if not ast_has_yield and doc_has_yield:
            findings.append("[Static] Dokumentasi mencantumkan 'yields', tapi kode tersebut bukan generator, tidak ditemukan 'yield' statement secara eksplisit (Halusinasi).")
                    
        return findings
    
    def verify_vbase(self, component: CodeComponent, doc: NumpyDocstring) -> List[str]:
        """
        Menjalankan semua pemeriksaan statis dan mengembalikan daftar temuan (string kesalahan).
        """
        findings = []
        node = component.node
        
        # Normalisasi nama parameter dengan menghapus awalan '*'
        # '**kwargs' -> 'kwargs'
        # '*args'    -> 'args'
        doc_params = {p.name.lstrip('*') for p in (doc.parameters or [])}
        doc_raises = {r.error for r in (doc.raises or [])}
        
        ast_params, ast_return_type = self._get_signature_truth(node)
        ast_raises = self._get_raises_truth(node)
        ast_has_yield = self._get_yield_truth(node)
        
        # Normalisasi nama parameter AST juga
        ast_params_set = {name.lstrip('*') for name in ast_params.keys()}

        # --- Pemeriksaan 1: Parameter (Sekarang menggunakan set yang sudah dinormalisasi) ---
        missing_in_doc = ast_params_set - doc_params
        hallucinated_in_doc = doc_params - ast_params_set
        
        for param in missing_in_doc:
            if param != 'self': 
                findings.append(f"[Static] Parameter '{param}' ada di kode tapi HILANG atau TIDAK DIBERIKAN pada dokumentasi.")
        
        for param in hallucinated_in_doc:
            # Kita tampilkan nama asli dari docstring (dengan '**') agar jelas
            original_doc_name = next((p.name for p in (doc.parameters or []) if p.name.lstrip('*') == param), param)
            findings.append(f"[Static] Parameter '{original_doc_name}' ada di dokumentasi tapi TIDAK ADA di kode (halusinasi).")

        # --- Pemeriksaan 2: Tipe Data ---
        if doc.parameters:
            for param in doc.parameters:
                # Normalisasi nama param dari docstring sebelum mengecek di dict ast_params
                normalized_param_name = param.name.lstrip('*') 
                
                if normalized_param_name in ast_params and ast_params[normalized_param_name]:
                    ast_type = self._normalize_type_str(ast_params[normalized_param_name]) 
                    doc_type = self._normalize_type_str(param.type)
                    
                    if ast_type and doc_type and ast_type != doc_type:
                         findings.append(f"[Static] Parameter '{param.name}' memiliki type hint '{ast_params[normalized_param_name]}' di kode, tapi didokumentasikan sebagai '{param.type}'.")

        # --- Pemeriksaan 3: Tipe Return ---
        if doc.returns:
            doc_return_type = self._normalize_type_str(doc.returns[0].type)
            ast_return_type_norm = self._normalize_type_str(ast_return_type)
            
            if ast_return_type_norm and doc_return_type and ast_return_type_norm != doc_return_type:
                findings.append(f"[Static] Fungsi memiliki return hint '{ast_return_type}' di kode, tapi didokumentasikan sebagai '{doc.returns[0].type}'.")

        # --- Pemeriksaan 4: Raises ---
        missing_raises_in_doc = ast_raises - doc_raises
        for err in missing_raises_in_doc:
            findings.append(f"[Static] Kode terlihat me-raise '{err}', tapi ini HILANG / TIDAK DIBERIKAN pada bagian 'raises' di dokumentasi.")
            
        hallucinated_raise_in_doc =  doc_raises - ast_raises
        for err in hallucinated_raise_in_doc:
            findings.append(f"[Static] Dokumentasi mencantumkan raises {err}, tapi *error* ini tidak ditemukan di-*raise* secara eksplisit di dalam kode (Halusinasi).")
        
        # --- Pemeriksaan 5: Yield ---
        doc_has_yield = bool(doc.yields)
        if ast_has_yield and not doc_has_yield:
            findings.append("[Static] Kode ini adalah generator (menggunakan 'yield'), tapi HILANG / TIDAK DIBERIKAN pada bagian 'yields' di dokumentasi.")
        
        if not ast_has_yield and doc_has_yield:
            findings.append("[Static] Dokumentasi mencantumkan 'yields', tapi kode tersebut bukan generator, tidak ditemukan 'yield' statement secara eksplisit (Halusinasi).")
        
        if len(findings) > 0:
            findings.append(f"[Static] (Info Penting) Pastikan penulisan WAJIB IDENTIK dan NYATA TERDAPAT PADA KODE yang sedang didokumentasikan.")
                    
        return findings

    def _get_signature_truth(self, node: ast.AST) -> Tuple[Dict[str, Optional[str]], Optional[str]]:
        """Mengekstrak nama parameter (dan tipenya) serta tipe return dari node."""
        params: Dict[str, Optional[str]] = {}
        return_type: Optional[str] = None

        def get_type_str(annotation: Optional[ast.expr]) -> Optional[str]:
            if not annotation:
                return None
            return ast.unparse(annotation) if hasattr(ast, 'unparse') else "complex_type"

        def extract_from_func(func_node: ast.FunctionDef | ast.AsyncFunctionDef):
            nonlocal return_type
            arg_map: Dict[str, Optional[str]] = {}
            
            all_args = func_node.args.args + func_node.args.kwonlyargs + func_node.args.posonlyargs
            for arg in all_args:
                arg_map[arg.arg] = get_type_str(arg.annotation)
            
            if func_node.args.vararg:
                arg_map[func_node.args.vararg.arg] = get_type_str(func_node.args.vararg.annotation)
            
            if func_node.args.kwarg:
                arg_map[func_node.args.kwarg.arg] = get_type_str(func_node.args.kwarg.annotation)
                
            return_type = get_type_str(func_node.returns)
            return arg_map, return_type

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params, return_type = extract_from_func(node)
            
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    params, _ = extract_from_func(item)
                    break
        
        return params, return_type

    def _get_raises_truth(self, node: ast.AST) -> Set[str]:
        """Mengekstrak 'raise' statement dari tubuh node."""
        raises = set()
        for sub_node in ast.walk(node):
            if isinstance(sub_node, ast.Raise):
                if isinstance(sub_node.exc, ast.Name):
                    raises.add(sub_node.exc.id)
                elif isinstance(sub_node.exc, ast.Call) and isinstance(sub_node.exc.func, ast.Name):
                    raises.add(sub_node.exc.func.id)
        return raises
    
    def _get_yield_truth(self, node: ast.AST) -> bool:
        """Mengecek apakah ada 'yield' atau 'yield from' di dalam tubuh node."""
        for sub_node in ast.walk(node):
            if isinstance(sub_node, (ast.Yield, ast.YieldFrom)):
                return True
        return False