# agents/searcher.py

from typing import Optional, Dict, List, Any
import re
import json

from app.services.docgen.base import BaseAgent
from app.services.docgen.state import AgentState
from app.services.docgen.tools.InternalCodeParser import InternalCodeParser
from app.core.config import DUMMY_TESTING_DIRECTORY


class Searcher(BaseAgent):
    """
    Agen Searcher yang bertanggung jawab untuk mengumpulkan konteks.
    Ia bisa melakukan pencarian internal (analisa statis) dan eksternal (via LLM).
    """
    def __init__(self, config_path: Optional[str] = None, internalCodeParser: InternalCodeParser = None, max_used_by_samples: int = 2, max_context_token: int = 6000):
        # Inisialisasi sebagai agen 'Searcher' untuk mendapatkan LLM yang sesuai dari config
        super().__init__("searcher", config_path)
        self.internalCodeParser = internalCodeParser
        self.all_dependencies = {}
        self.all_used_by = {}
        self.max_used_by_samples = max_used_by_samples
        self.max_context_token = max_context_token
        self.gathered_data = {}

    def _run_internal_search(self, state: AgentState) -> str:
        """Menjalankan semua pencarian internal dan memformat hasilnya."""
        focal_component = state["focal_component"]
        dependencies = self._find_dependencies(focal_component)
        used_by = self._find_used_by(focal_component)
        
        context_parts = []
        if dependencies:
            dep_str = "\n".join([f"<FUNCTION NAME='{name}'>\n{doc}\n</FUNCTION>" for name, doc in dependencies.items()])
            context_parts.append(f"<DEPENDENCIES>\n{dep_str}\n</DEPENDENCIES>")
            
        if used_by:
            cb_str = "\n".join([f"<USAGE>\n{code}\n</USAGE>" for code in used_by])
            context_parts.append(f"<used_by>\n{cb_str}\n</used_by>")
            
        return "\n" + "\n".join(context_parts) if context_parts else ""


    # --- Metode Proses Utama ---
    def find_initial_context(self, state: AgentState) -> AgentState:
        
        current_all_dependencies = self.internalCodeParser.find_dependencies(state["component"].id)
        all_used_by = self.internalCodeParser.find_called_by(state["component"].id)
        pagerank_scores = self.internalCodeParser.find_pagerank_scores()
        
        # print("[Searcher] Original name: ", state["component"].id)
        # print("[Searcher] All dependencies:", current_all_dependencies)
        # print("[Searcher] All called by:", self.all_used_by)
        
        gathered_data = {
            "internal": {
                "class_context": None,
                "dependencies": {},
                "used_by": []
            },
            "external": {
                # "question query": "query result"
            }
        }
        
        # Sort dependencies by pagerank
        
        sorted_dependencies = sorted(
            current_all_dependencies, 
            key=lambda dep: pagerank_scores.get(dep, 0), 
            reverse=True
        )
        
        # 1. Gathering dependencies information
        for dep_id in sorted_dependencies:
            context_content = self.internalCodeParser.get_component_docstring(dep_id)
            context_type = "documentation"

            # Heuristik #1: Fallback ke kode sumber jika docstring tidak memadai
            if not context_content or len(context_content) < 15:
                print(f"    -> [Searcher] Docstring untuk '{dep_id}' tidak ada/pendek, mengambil kode sumber.")
                context_content = self.internalCodeParser.get_component_source_code(dep_id)
                context_type = "source_code"
            
            # Masukkan hasil ke dalam dictionary 'dependencies'
            gathered_data["internal"]["dependencies"][dep_id] = {
                "id": dep_id,
                "type": context_type,
                "content": context_content,
                "pagerank_score": pagerank_scores.get(dep_id, 0)
            }
            
        # 2. Gathering called by information
        # 2a. Gathering class context
        if state['component'].component_type == "method":
            class_skeleton = self.internalCodeParser.get_class_skeleton(state["component"].id)
            gathered_data["internal"]["class_context"] = {
                "is_method": True,
                "content": class_skeleton
            }
        # 2b. Gathering called by information
        if all_used_by:
            used_by_resources = self.internalCodeParser.find_called_by_snippet(state["component"].id, self.max_used_by_samples) 
            if used_by_resources and len(used_by_resources) > 0:
                gathered_data["internal"]["used_by"].extend(used_by_resources)
        
        with open(DUMMY_TESTING_DIRECTORY / "searcher_gathered_data.json", "w", encoding="utf-8") as f:
            json.dump(gathered_data, f, indent=4, ensure_ascii=False)
        
        return state
    
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
    
    def format_search_context():
        return