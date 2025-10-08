# agents/searcher.py

from typing import Optional, Dict, List, Any
import re

from app.services.docgen.base import BaseAgent
from app.services.docgen.state import AgentState

class Searcher(BaseAgent):
    """
    Agen Searcher yang bertanggung jawab untuk mengumpulkan konteks.
    Ia bisa melakukan pencarian internal (analisa statis) dan eksternal (via LLM).
    """
    def __init__(self, config_path: Optional[str] = None):
        # Inisialisasi sebagai agen 'Searcher' untuk mendapatkan LLM yang sesuai dari config
        super().__init__("searcher", config_path)

    # --- Bagian Pencarian Internal (Analisa Statis) ---
    def _find_dependencies(self, focal_component: str) -> Dict[str, str]:
        """
        (IMPLEMENTASI DUMMY) Mencari docstring dari dependensi.
        Ini akan menggunakan analisa AST di implementasi nyata.
        """
        print("    -> [Searcher] (Dummy) Mencari docstring dependensi...")
        # TODO: Ganti dengan logika pencarian AST.
        return {
            "another_module.utility_function": "'''Ini adalah docstring untuk utility_function.'''",
            "self.helper_method": "'''Docstring untuk helper_method di dalam kelas yang sama.'''"
        }

    def _find_called_by(self, focal_component: str) -> List[str]:
        """
        (IMPLEMENTASI DUMMY) Mencari contoh penggunaan komponen.
        Ini akan menggunakan analisa AST di implementasi nyata.
        """
        print("    -> [Searcher] (Dummy) Mencari contoh penggunaan (called by)...")
        # TODO: Ganti dengan logika pencarian referensi.
        return [
            "result = calculate_fibonacci(n=10)",
            "if config.get('use_fib'):\n    fib_val = calculate_fibonacci(user_input)"
        ]

    def _run_internal_search(self, state: AgentState) -> str:
        """Menjalankan semua pencarian internal dan memformat hasilnya."""
        focal_component = state["focal_component"]
        dependencies = self._find_dependencies(focal_component)
        called_by = self._find_called_by(focal_component)
        
        context_parts = []
        if dependencies:
            dep_str = "\n".join([f"<FUNCTION NAME='{name}'>\n{doc}\n</FUNCTION>" for name, doc in dependencies.items()])
            context_parts.append(f"<DEPENDENCIES>\n{dep_str}\n</DEPENDENCIES>")
            
        if called_by:
            cb_str = "\n".join([f"<USAGE>\n{code}\n</USAGE>" for code in called_by])
            context_parts.append(f"<CALLED_BY>\n{cb_str}\n</CALLED_BY>")
            
        return "\n" + "\n".join(context_parts) if context_parts else ""

    # --- Bagian Pencarian Eksternal (Menggunakan LLM) ---

    def _parse_reader_request(self, reader_response: str, config: Dict) -> Dict[str, Any]:
        """
        Menggunakan LLM untuk mem-parsing permintaan XML dari Reader.
        Ini adalah contoh bagaimana Searcher dapat menggunakan kemampuannya sebagai agen.
        """
        print("    -> [Searcher] Mem-parsing permintaan Reader menggunakan LLM...")
        
        # Di implementasi nyata, prompt ini akan lebih kuat.
        prompt = (
            f"Ekstrak semua item dari tag <QUERY> di dalam teks XML berikut. "
            f"Kembalikan sebagai daftar JSON. Jika tidak ada, kembalikan daftar kosong.\n\n"
            f"{reader_response}"
        )
        
        # Gunakan 'invoke' dari LLM yang diwarisi dari BaseAgent
        # Kita tidak perlu mengelola memori di sini, ini adalah tugas sekali jalan.
        response = self.llm.invoke(prompt, config=config)
        
        # TODO: Parsing JSON yang lebih kuat dari respons LLM.
        try:
            # Misalkan LLM mengembalikan string seperti '["query1", "query2"]'
            return {"external_queries": eval(response.content)}
        except:
            return {"external_queries": []}

    def _run_external_search(self, queries: List[str]) -> str:
        """
        (IMPLEMENTASI DUMMY) Menjalankan pencarian eksternal.
        Ini akan terhubung ke API pencarian seperti Tavily, SerpAPI, dll.
        """
        if not queries:
            return ""
        
        print(f"    -> [Searcher] (Dummy) Menjalankan pencarian eksternal untuk: {queries}")
        # TODO: Ganti dengan logika API pencarian nyata.
        results = [f"<EXTERNAL_RESULT QUERY='{q}'>Hasil pencarian untuk {q}...</EXTERNAL_RESULT>" for q in queries]
        return "\n" + "\n".join(results)

    # --- Metode Proses Utama ---

    def process(self, state: AgentState) -> AgentState:
        """
        Titik masuk utama untuk Searcher. Ia memutuskan pencarian mana yang akan dijalankan.
        """
        print("[Searcher]: Run - Gathering context ...")

        # Alur default: Selalu jalankan pencarian internal
        internal_context = self._run_internal_search(state)
        state["context"] += internal_context

        # Alur kondisional: Jalankan pencarian eksternal HANYA JIKA diminta oleh Reader
        reader_response = state.get("reader_response")
        if reader_response and "<RETRIEVAL>" in reader_response:
            config = {"tags": [self.name], "callbacks": state["callbacks"]}
            parsed_request = self._parse_reader_request(reader_response, config)
            
            external_queries = parsed_request.get("external_queries", [])
            if external_queries:
                external_context = self._run_external_search(external_queries)
                state["context"] += external_context
        
        return state