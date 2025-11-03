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
from app.services.docgen.agents.agent_output_schema import NumpyDocstring, SingleCallVerificationReport
from app.schemas.models.code_component_schema import CodeComponent


    
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
        self.static_verifier_feedback_keyword = "[Static]"
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

--- TUGAS 1: CEKLIS EVALUASI ---
PERHATIAN: Anda HARUS mengevaluasi HANYA bagian-bagian yang tercantum dalam ceklis di bawah ini. JANGAN mengevaluasi atau memberi kritik pada bagian lain (seperti 'keywords', 'see_also', 'methods', dll.) yang tidak tercantum secara eksplisit.

Evaluasi DOKUMENTASI berdasarkan KODE dan KONTEKS. Berikan kritik Anda untuk setiap poin berikut:
{dynamic_checklist}

--- TUGAS 2: KEPUTUSAN AKHIR ---
Sekarang, berdasarkan 'critiques' Anda di TUGAS 1, buat keputusan akhir:

1.  **suggested_next_step**:
    -   Jika SEMUA `critiques` `is_accurate = true`, pilih "finished".
    -   Jika ada `critiques` `is_accurate = false` DAN kesalahannya bisa diperbaiki HANYA dengan melihat kode/konteks yang ada (misal: contoh salah, deskripsi parameter salah), pilih "writer".
    -   Jika ada `critiques` `is_accurate = false` DAN kesalahannya adalah kurangnya informasi konteks external yang diberikan kepada LLM (misal: "Apa itu algoritma X"), pilih "reader".

2.  **suggestion_feedback**:
    -   Jika "finished", tulis "Verifikasi lolos."
    -   Jika "writer", jelaskan secara ringkas apa yang harus DIPERBAIKI oleh Writer.
    -   Jika "reader", jelaskan secara spesifik KONTEKS APA yang harus DICARI oleh Reader.

Hasilkan objek JSON `SingleCallVerificationReport` yang berisi 'critiques' (dari TUGAS 1) dan 'suggested_next_step' serta 'suggestion_feedback' (dari TUGAS 2).
"""
        # 2. Tambahkan string ceklis dinamis
        self._verifier_checklist_function: str = """
1.  **short_summary**: Apakah summary ini secara akurat (berdasarkan kode dan konteks) mendeskripsikan FUNGSI UTAMA kode?
2.  **extended_summary**: Apakah deskripsi ini faktual berdasarkan kode dan konteks? Apakah menjelaskan 'mengapa' dan 'bagaimana' dengan benar?
3.  **parameters**: (PENTING) Evaluasi deskripsi parameter: Apakah sudah mencakup **Signifikansi**, **Batasan** (constraints), dan **Interdependensi**? Apakah deskripsinya cocok dengan PENGGUNAANNYA di kode?
4.  **returns**: (PENTING) Evaluasi deskripsi nilai kembali: Apakah sudah mencakup **Representasi** (artinya), **Kemungkinan Nilai**, dan **Kondisi**?
5.  **yields / receives**: (Jika ini generator) Apakah `yields` dan `receives` didokumentasikan dengan benar (menggantikan/melengkapi `returns`)?
6.  **raises**: (PENTING) Evaluasi deskripsi error: Apakah sudah mencakup **Kondisi Spesifik** dan saran **Pencegahan/Penanganan**?
7.  **examples**: (SANGAT PENTING) Apakah contoh kode ini *halusinasi*? Apakah tipe data di contoh cocok dengan signatur fungsi di kode?
"""
        self._verifier_checklist_class: str = """
1.  **short_summary**: Apakah summary ini secara akurat (berdasarkan kode dan konteks) mendeskripsikan FUNGSI UTAMA kode?
2.  **extended_summary**: Apakah deskripsi ini faktual berdasarkan kode dan konteks? Apakah menjelaskan 'mengapa' dan 'bagaimana' dengan benar?
3.  **parameters** (dari `__init__`): (PENTING) Evaluasi deskripsi parameter constructor: Apakah sudah mencakup **Signifikansi** (pengaruhnya pada instance), **Batasan** (nilai valid), dan **Relasi** antar parameter?
4.  **attributes**: (PENTING) Evaluasi deskripsi atribut: Apakah sudah mencakup **Tujuan/Signifikansi**, **Tipe/Nilai** yang valid, dan **Dependensi** antar atribut?
5.  **examples**: (SANGAT PENTING) Apakah contoh kode ini *halusinasi*? Apakah inisialisasi dan pemanggilan metodenya logis berdasarkan kode?
"""

        # 3.3. Inisialisasi Chain LLM (LCEL)
        self.llm_chain: Runnable = self._setup_llm_chain()
    def _setup_llm_chain(self) -> Runnable:
        """Membangun chain LCEL untuk verifikasi LLM."""
        
        format_instructions = self.verifier_parser.get_format_instructions()
        # Gabungkan instruksi format ke dalam system prompt
        system_prompt_with_format = self.verifier_system_prompt + \
            "\n\nSKEMA OUTPUT JSON (WAJIB DIPATUHI):\n{format_instructions}"
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_with_format),
            ("human", self.verifier_human_template),
        ]).partial(format_instructions=format_instructions)
        
        # Asumsi self.llm ada dari BaseAgent
        chain = prompt | self.llm | self.verifier_parser
        return chain

    def _parse_llm_report(self, report: SingleCallVerificationReport) -> Tuple[List[str], str]:
        """Mengurai laporan LLM menjadi daftar temuan dan mendeteksi kebutuhan konteks."""
        findings = []
        
        for critique in report.critiques:
            if not critique.is_accurate:
                finding_text = f"[LLM - {critique.section}]: {critique.critique}"
                findings.append(finding_text)
                
        suggested_next_step = report.suggested_next_step
        
        if suggested_next_step != "finished":
            findings.append(f"[LLM - SARAN]: {report.suggestion_feedback}")
        
        return findings, suggested_next_step

    def format_suggested_prompt(self, state: AgentState) -> str:
        """
        Membuat prompt saran yang ringkas untuk Reader atau Writer 
        berdasarkan hasil verifikasi.
        """
        
        # 1. Ambil data hasil verifikasi dengan aman
        verification_result = state.get("verification_result", {})
        formatted_result = verification_result.get("formatted", {})
        raw_result = verification_result.get("raw", {})

        suggested_next_step = formatted_result.get("suggested_next_step", "writer")
        all_feedback_list = formatted_result.get("feedback", [])
        llm_suggestion_feedback = formatted_result.get("suggestion_feedback", "")

        # --- Aturan 1: Finished ---
        if suggested_next_step == "finished":
            return ""

        # --- Aturan 2: Perlu Revisi ---
        
        # Pisahkan feedback statis
        static_findings = [f for f in all_feedback_list if f.startswith(self.static_verifier_feedback_keyword)]
        
        # --- Aturan 2.1: Kasus Error LLM (Tidak ada 'raw' & tidak ada 'static') ---
        # Ini adalah kasus di mana LLM Verifier gagal (try-except)
        # DAN Static Verifier juga lolos.
        if not raw_result and not static_findings:
            # --- PERBAIKAN DI SINI ---
            # Skenario ini HANYA terjadi jika Verifier LLM gagal (try-except).
            # Dalam kasus itu, suggested_next_step akan selalu 'writer'.
            target_agent = "Writer"
            prompt_lines = []
                        
            prompt_lines.append(f"**Saran Perbaikan dari Verifier :**")
            prompt_lines.append("-" * (40 + len(target_agent)))
            prompt_lines.append("Saran Perbaikan (dari Sistem):")
            prompt_lines.append("Terjadi kesalahan internal saat Verifier AI mencoba mengevaluasi output JSON sebelumnya.")
            prompt_lines.append("Harap proses ulang permintaan tugas Anda. Perhatikan SEMUA aturan, konteks, dan kode komponend yang ingin didokumentasikan dengan saksama dan pastikan output JSON yang dihasilkan 100% akurat dan valid.")
            
            return "\n".join(prompt_lines).strip()
            
        # --- Aturan 2.2: Ada Feedback (Statis atau LLM) ---
        
        prompt_lines = []
        target_agent = "Reader" if suggested_next_step == "reader" else "Writer"
        
        prompt_lines.append(f"**Saran Perbaikan dari Verifier (untuk {target_agent}):**")
        prompt_lines.append("-" * (40 + len(target_agent))) # Garis pemisah dinamis
        
        # 1. Tambahkan Feedback Statis (jika ada)
        if static_findings:
            prompt_lines.append("Kesalahan Faktual (Statis):")
            for finding in static_findings:
                # Format ulang agar lebih bersih (menghapus tag [Static])
                clean_finding = finding.replace("[Static] ", "").strip()
                prompt_lines.append(f"- {clean_finding}")
            
            # Beri spasi jika ada feedback LLM juga
            if llm_suggestion_feedback and raw_result:
                prompt_lines.append("") 

        # 2. Tambahkan Feedback LLM (hanya 'suggestion_feedback')
        # Kita cek 'raw_result' untuk memastikan LLM-nya jalan (bukan cuma error statis)
        if llm_suggestion_feedback and raw_result:
            if suggested_next_step == "reader":
                prompt_lines.append("Saran Pencarian Konteks (dari AI):")
            else: # (suggested_next_step == "writer")
                prompt_lines.append("Saran Perbaikan Konten (dari AI):")
            
            prompt_lines.append(llm_suggestion_feedback)

        final_prompt = "\n".join(prompt_lines)
        
        return final_prompt.strip()

    def process(self, state: AgentState) -> AgentState:
        """
        Menjalankan proses verifikasi hibrida (Statis + LLM).
        """
        print("[Verifier]: Run - Verifying generated docstring ...")

        component: CodeComponent = state["component"]
        doc_json: Optional[NumpyDocstring] = state.get("documentation_json")
        focal_code: str = state["focal_component"]
        context: str = state.get("context", "Tidak ada konteks yang diberikan.")

        if not doc_json:
            print("[Verifier]: WARNING: Tidak ada documentation_json untuk diverifikasi. Melewatkan.")
            state["verification_result"] = {
                'needs_revision': True, 
                'feedback': ["Docstring JSON tidak berhasil dibuat oleh Writer."],
                'suggested_next_step': 'writer'
            }
            return state

        # --- LANGKAH 1: VERIFIKASI STATIS (GRATIS) ---
        print("[Verifier]: Running Static AST Verification...")
        static_findings = self.static_verifier.verify(component, doc_json)
        
        # --- LANGKAH 2: VERIFIKASI LLM (BERBAYAR) ---
        print("[Verifier]: Running LLM Semantic Verification...")
        if component.component_type.lower() == "class":
            dynamic_checklist = self._verifier_checklist_class
        else:
            # Default ke function/method
            dynamic_checklist = self._verifier_checklist_function
        config = {"tags": [self.name], "callbacks": state.get("callbacks", [])}
        
        llm_input = {
            "konteks_writer": context,
            "kode_komponen": focal_code,
            "docstring_output": state["docstring"],
            "dynamic_checklist": dynamic_checklist
        }
        
        llm_report: SingleCallVerificationReport = None
        try:
            llm_report: SingleCallVerificationReport = self.llm_chain.invoke(llm_input, config=config)
            llm_findings, llm_step_suggestion = self._parse_llm_report(llm_report)
            
        except Exception as e:
            print(f"[Verifier]: CRITICAL: LLM Verifier chain failed! Error: {e}")
            llm_findings = [f"[LLM - ERROR]: Panggilan Verifier LLM gagal: {e}"]
            llm_report = None
            llm_step_suggestion = "writer" # Default ke writer jika verifier gagal

        # --- LANGKAH 3: GABUNGKAN HASIL & BUAT KEPUTUSAN ---
        print("[Verifier]: Consolidating feedback...")
        
        # --- LOGIKA KEPUTUSAN BARU ---
        all_findings = static_findings + llm_findings
        needs_revision = bool(all_findings)
        
        if not needs_revision:
            # Lolos statis DAN lolos LLM
            suggested_next_step = "finished"
        else:
            # Jika ada kesalahan STATIS (faktual), itu PASTI 'writer'.
            # Kesalahan statis tidak bisa diperbaiki oleh 'reader'.
            if static_findings:
                suggested_next_step = "writer"
            else:
                # Jika tidak ada kesalahan statis, kita PERCAYA pada keputusan LLM
                suggested_next_step = llm_step_suggestion
        # --- AKHIR LOGIKA KEPUTUSAN ---

        state["verification_result"] = {
            "formatted": {
                'needs_revision': needs_revision,
                'feedback': all_findings,
                'suggested_next_step': suggested_next_step,
                'suggestion_feedback': llm_report.suggestion_feedback if llm_report else ""
            },
            "raw": llm_report.model_dump() if llm_report else {}
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