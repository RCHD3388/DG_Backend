# agents/verifier.py

from typing import Optional, Dict, Any, List, Set, Literal, Tuple
from pydantic import BaseModel, Field
import ast
import re

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable

from app.services.docgen.base import BaseAgent
from app.services.docgen.state import AgentState
from app.services.docgen.agents.documentation_output import NumpyDocstring
from app.schemas.models.code_component_schema import CodeComponent

class SectionCritique(BaseModel):
    """Kritik spesifik untuk satu bagian dari docstring."""
    section: str = Field(..., description="Bagian yang dievaluasi, misal: 'parameters', 'examples', 'short_summary'.")
    is_accurate: bool = Field(..., description="Apakah bagian ini akurat secara semantik berdasarkan kode?")
    critique: str = Field(..., description="Kritik spesifik. Tulis 'Akurat.' jika lolos, atau jelaskan kesalahannya jika gagal.")

class SingleCallVerificationReport(BaseModel):
    """Laporan verifikasi lengkap dari satu panggilan LLM."""
    critiques: List[SectionCritique] = Field(..., description="Daftar kritik untuk setiap bagian utama docstring.")
    
class StaticVerifier:
    """
    Melakukan verifikasi faktual yang cepat dan gratis menggunakan AST.
    """
    
    def _normalize_type_str(self, s: Optional[str]) -> str:
        """Menormalkan string tipe data untuk perbandingan yang konsisten."""
        if not s:
            return ""
        # Menghapus spasi dan tanda kurung ekstra dari 'Dict[(str, Any)]'
        return re.sub(r'[\s\(\)]', '', s)

    def verify(self, component: CodeComponent, doc: NumpyDocstring) -> List[str]:
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
        
        # Normalisasi nama parameter AST juga
        ast_params_set = {name.lstrip('*') for name in ast_params.keys()}

        # --- Pemeriksaan 1: Parameter (Sekarang menggunakan set yang sudah dinormalisasi) ---
        missing_in_doc = ast_params_set - doc_params
        hallucinated_in_doc = doc_params - ast_params_set
        
        for param in missing_in_doc:
            if param != 'self': 
                findings.append(f"[Static] Parameter '{param}' ada di kode tapi HILANG dari dokumentasi.")
        
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
            findings.append(f"[Static] Kode terlihat me-raise '{err}', tapi ini HILANG dari bagian 'Raises' di dokumentasi.")
            
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
    
class Verifier(BaseAgent):
    """
    Agen Verifier yang mengevaluasi kualitas docstring yang dihasilkan.
    """
    def __init__(self, config_path: Optional[str] = None):
        """Inisialisasi Verifier dengan prompt sistemnya."""
        super().__init__("verifier", config_path=config_path)
        
        # 3.1. Inisialisasi Verifikator Statis (Gratis)
        self.static_verifier = StaticVerifier()
        
        # 3.2. Definisi Prompt untuk Verifikator LLM (Berbayar)
        self.verifier_parser = PydanticOutputParser(pydantic_object=SingleCallVerificationReport)
        
        self.verifier_system_prompt: str = """
Anda adalah 'Verifier Dokumentasi' AI yang sangat teliti, kritis, dan jujur.
Tugas Anda adalah membandingkan KODE ASLI dengan DOKUMENTASI YANG DIHASILKAN.
Anda HARUS mengevaluasi setiap bagian satu per satu dan memberikan kritik (critique) yang jujur.
Jangan malas. Fokus utama Anda adalah menemukan HALUSINASI atau KETIDAKAKURATAN.

Output Anda HARUS berupa JSON yang valid sesuai skema yang diberikan.
"""

        self.verifier_human_template: str = """
KONTEKS YANG DIGUNAKAN WRITER:
---
{konteks_writer}
---        

KODE ASLI:
---
{kode_komponen}
---

DOKUMENTASI YANG DIHASILKAN (dari Writer):
---
{docstring_output} 
---

CEKLIS EVALUASI (Wajib Diikuti):
Sekarang, evaluasi DOKUMENTASI berdasarkan KODE. Berikan kritik Anda untuk setiap poin berikut:

1.  **short_summary**: Apakah summary ini secara akurat dan ringkas (tanpa halusinasi) mendeskripsikan FUNGSI UTAMA kode?
2.  **extended_summary**: Apakah deskripsi ini faktual berdasarkan kode? Apakah menjelaskan 'mengapa' dan 'bagaimana' dengan benar?
3.  **parameters**: (PENTING) Apakah *deskripsi* untuk setiap parameter cocok dengan PENGGUNAANNYA di dalam kode? (Contoh kesalahan: deskripsi bilang 'integer' padahal kode menggunakannya sebagai 'path file').
4.  **returns**: Apakah *deskripsi* nilai kembali secara akurat mewakili apa yang dihasilkan oleh kode?
5.  **examples**: (SANGAT PENTING) Apakah contoh kode ini *halusinasi*? Apakah tipe data di contoh cocok dengan signatur fungsi di kode? Apakah pemanggilannya logis?

Hasilkan objek JSON `SingleCallVerificationReport` yang berisi `critiques` Anda.
Untuk 'critique':
- Jika AKURAT: Tulis "Akurat."
- Jika SALAH: Jelaskan KESALAHANNYA. (misal: "SALAH: Contoh menggunakan string 'hello' padahal parameter 'a' adalah integer.")
"""
        
        # 3.3. Inisialisasi Chain LLM (LCEL)
        self.llm_chain: Runnable = self._setup_llm_chain()
    def _setup_llm_chain(self) -> Runnable:
        """Membangun chain LCEL untuk verifikasi LLM."""
        
        # Gabungkan instruksi format ke dalam system prompt
        system_prompt_with_format = self.verifier_system_prompt + \
            "\n\nSKEMA OUTPUT JSON (WAJIB DIPATUHI):\n{format_instructions}"
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_with_format),
            ("human", self.verifier_human_template),
        ])
        
        # Asumsi self.llm ada dari BaseAgent
        chain = prompt | self.llm | self.verifier_parser
        return chain

    def _parse_llm_report(self, report: SingleCallVerificationReport) -> Tuple[List[str], bool]:
        """Mengurai laporan LLM menjadi daftar temuan dan mendeteksi kebutuhan konteks."""
        findings = []
        needs_more_context = False
        
        for critique in report.critiques:
            if not critique.is_accurate:
                finding_text = f"[LLM - {critique.section}]: {critique.critique}"
                findings.append(finding_text)
                
                # Heuristik untuk mendeteksi jika Reader perlu dijalankan ulang
                if "kurang konteks" in critique.critique.lower() or \
                   "tidak cukup informasi" in critique.critique.lower():
                    needs_more_context = True
                    
        return findings, needs_more_context

    def process(self, state: AgentState) -> AgentState:
        """
        Menjalankan proses verifikasi hibrida (Statis + LLM).
        """
        print("[Verifier]: Run - Verifying generated docstring ...")

        # 1. Ambil data yang relevan dari state
        component: CodeComponent = state["component"]
        doc_json: Optional[NumpyDocstring] = state.get("documentation_json")
        focal_code: str = state["focal_component"]

        if not doc_json:
            print("[Verifier]: WARNING: Tidak ada documentation_json untuk diverifikasi. Melewatkan.")
            state["verification_result"] = {
                'needs_revision': True, 
                'feedback': ["Docstring JSON tidak berhasil dibuat oleh Writer."],
                'suggested_next_step': 'writer' # Kirim kembali ke writer
            }
            return state

        # --- LANGKAH 1: VERIFIKASI STATIS (GRATIS) ---
        print("[Verifier]: Running Static AST Verification...")
        static_findings = self.static_verifier.verify(component, doc_json)
        
        # --- LANGKAH 2: VERIFIKASI LLM (BERBAYAR) ---
        print("[Verifier]: Running LLM Semantic Verification...")
        config = {"tags": [self.name], "callbacks": state.get("callbacks", [])}
        llm_input = {
            "format_instructions": self.verifier_parser.get_format_instructions(),
            "konteks_writer": state.get("context", "No context was used."),
            "kode_komponen": focal_code,
            "docstring_output": state["docstring"] # Kirim sebagai string JSON
        }
        
        try:
            llm_report: SingleCallVerificationReport = self.llm_chain.invoke(llm_input, config=config)
            llm_findings, needs_more_context = self._parse_llm_report(llm_report)
            
        except Exception as e:
            print(f"[Verifier]: CRITICAL: LLM Verifier chain failed! Error: {e}")
            llm_findings = [f"[LLM - ERROR]: Panggilan Verifier LLM gagal: {e}"]
            needs_more_context = False # Default ke writer jika verifier gagal

        # --- LANGKAH 3: GABUNGKAN HASIL & BUAT KEPUTUSAN ---
        print("[Verifier]: Consolidating feedback...")
        all_findings = static_findings + llm_findings
        needs_revision = bool(all_findings)

        if needs_revision:
            # Tentukan langkah selanjutnya berdasarkan temuan
            if needs_more_context:
                suggested_next_step = "reader" # Minta konteks baru
            else:
                suggested_next_step = "writer" # Perbaiki konten
        else:
            suggested_next_step = "finished" # Lolos verifikasi

        # 4. Perbarui state global dengan hasil yang terstruktur
        state["verification_result"] = {
            'needs_revision': needs_revision,
            'feedback': all_findings, # Daftar lengkap semua kesalahan
            'suggested_next_step': suggested_next_step 
        }
        
        if needs_revision:
            print(f"[Verifier]: FAILED. {len(all_findings)} issues found. Suggesting: {suggested_next_step}")
        else:
            print("[Verifier]: PASSED. No issues found.")

        return state


# class Verifier(BaseAgent):
#     """
#     Agen Verifier yang mengevaluasi kualitas docstring yang dihasilkan.
#     """
#     def __init__(self, config_path: Optional[str] = None):
#         """Inisialisasi Verifier dengan prompt sistemnya."""
#         super().__init__("verifier", config_path=config_path)
        
#         self.system_prompt = """You are a Verifier agent responsible for ensuring the quality of generated docstrings. 
#         Your role is to evaluate docstrings from the perspective of a first-time user encountering the code component.
        
#         Analysis Process:
#         1. First read the code component as if you're seeing it for the first time
#         2. Read the docstring and analyze how well it helps you understand the code
#         3. Evaluate if the docstring provides the right level of abstraction and information
        
#         Verification Criteria:
#         1. Information Value:
#            - Identify parts that merely repeat the code without adding value
#            - Flag docstrings that state the obvious without providing insights
#            - Check if explanations actually help understand the purpose and usage
        
#         2. Appropriate Detail Level:
#            - Flag overly detailed technical explanations of implementation
#            - Ensure focus is on usage and purpose, not line-by-line explanation
#            - Check if internal implementation details are unnecessarily exposed
        
#         3. Completeness Check:
#            - Verify all required sections are present (summary, args, returns, etc.)
#            - Check if each section provides meaningful information
#            - Ensure critical usage information is not missing
        
#         Output Format:
#         Your analysis must include:
#         1. <NEED_REVISION>true/false</NEED_REVISION>
#            - Indicates if docstring needs improvement
        
#         2. If revision needed:
#            <MORE_CONTEXT>true/false</MORE_CONTEXT>
#            - Indicates if additional context is required for improvement
#            - Keep in mind that collecting context is very expensive and may fail, so only use it when absolutely necessary
        
#         3. Based on MORE_CONTEXT, provide suggestions at the end of your response:
#            If true:
#            <SUGGESTION_CONTEXT>explain why and what specific context is needed</SUGGESTION_CONTEXT>
           
#            If false:
#            <SUGGESTION>specific improvement suggestions</SUGGESTION>
        
#         Do not generate other things after </SUGGESTION> or </SUGGESTION_CONTEXT>."""
        
#         self.add_to_memory("system", self.system_prompt)

#     def _parse_response(self, response: str) -> Dict[str, Any]:
#         """
#         Mem-parsing respons XML dari LLM menjadi dictionary yang terstruktur.
#         Ini adalah implementasi dari _parse_verifier_response dari contoh asli.
#         """
#         result = {
#             'needs_revision': False,
#             'needs_context': False,
#             'suggestion': '',
#             'context_suggestion': ''
#         }
        
#         # Ekstrak nilai dari setiap tag menggunakan regex
#         needs_revision_match = re.search(r'<NEED_REVISION>(.*?)</NEED_REVISION>', response, re.DOTALL)
#         if needs_revision_match:
#             result['needs_revision'] = needs_revision_match.group(1).strip().lower() == 'true'
        
#         more_context_match = re.search(r'<MORE_CONTEXT>(.*?)</MORE_CONTEXT>', response, re.DOTALL)
#         if more_context_match:
#             result['needs_context'] = more_context_match.group(1).strip().lower() == 'true'
            
#         suggestion_match = re.search(r'<SUGGESTION>(.*?)</SUGGESTION>', response, re.DOTALL)
#         if suggestion_match:
#             result['suggestion'] = suggestion_match.group(1).strip()
            
#         context_suggestion_match = re.search(r'<SUGGESTION_CONTEXT>(.*?)</SUGGESTION_CONTEXT>', response, re.DOTALL)
#         if context_suggestion_match:
#             result['context_suggestion'] = context_suggestion_match.group(1).strip()

#         return result

#     def process(self, state: AgentState) -> AgentState:
#         """
#         Menjalankan proses verifikasi dan memperbarui state.
#         """
#         print("[verifier]: Run - Verifying generated docstring ...")
        
#         # 1. Ambil data yang relevan dari state
#         focal_component = state["focal_component"]
#         docstring = state["docstring"]
#         context = state["context"]
        
#         if not docstring:
#             print("PERINGATAN: Tidak ada docstring untuk diverifikasi. Melewatkan Verifier.")
#             # Set hasil default jika tidak ada docstring
#             state["verification_result"] = {'needs_revision': True, 'suggestion': 'Docstring tidak berhasil dibuat.'}
#             return state

#         # 2. Susun pesan user untuk LLM
#         task_description = f"""
#         Context Used:
#         {context if context else 'No context was used.'}

#         Verify the quality of the following docstring for the following Code Component:
        
#         Code Component:
#         {focal_component}
        
#         Generated Docstring:
#         {docstring}
#         """
        
#         # 3. Kelola memori: selalu mulai dari awal untuk verifikasi yang objektif
#         self.clear_memory()
#         self.add_to_memory("system", self.system_prompt)
#         self.add_to_memory("user", task_description)
        
#         # 4. Hasilkan respons mentah dari LLM LangChain
#         config = {"tags": [self.name], "callbacks": state["callbacks"]}
#         full_response = self.llm.invoke(self.memory, config=config)
        
#         # 5. Parsing respons mentah menjadi dictionary yang bersih
#         parsed_result = self._parse_response(full_response.content)
        
#         # 6. Perbarui state global dengan hasil yang sudah di-parsing
#         state["verification_result"] = parsed_result
        
#         return state