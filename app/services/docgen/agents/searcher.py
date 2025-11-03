# agents/searcher.py

from typing import Optional, Dict, List, Any, Tuple
import re
import json
import tiktoken
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET
import random

from app.services.docgen.base import BaseAgent
from app.services.docgen.state import AgentState
from app.services.docgen.tools.InternalCodeParser import InternalCodeParser
from app.core.config import DUMMY_TESTING_DIRECTORY
from app.utils.CustomLogger import CustomLogger
from app.services.docgen.agents.agent_output_schema import ReaderOutput
from langchain_core.messages import SystemMessage, HumanMessage

logger = CustomLogger("Searcher")

@dataclass
class ParsedInfoRequest:
    """Structured format for parsed information requests.
    
    Attributes:
        internal_requests: Dictionary containing:
            - expand: requested to expand the code
        external_requests: List of query strings for external information search
    """
    internal_requests: Dict[str, Any] = field(default_factory=lambda: {
        'expand': []
    })
    external_requests: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert this component to a dictionary representation for JSON serialization."""
        return {
            'internal_requests': {
                'expand': list(self.internal_requests['expand'])
            },
            "external_requests": list(self.external_requests)
        }

class Searcher(BaseAgent):
    """
    Agen Searcher yang bertanggung jawab untuk mengumpulkan konteks.
    Ia bisa melakukan pencarian internal (analisa statis) dan eksternal (via LLM).
    """
    def __init__(self, config_path: Optional[str] = None, internalCodeParser: InternalCodeParser = None, max_used_by_samples: int = 2, max_context_token: int = 10000):
        # Inisialisasi sebagai agen 'Searcher' untuk mendapatkan LLM yang sesuai dari config
        super().__init__("searcher", config_path)
        self.internalCodeParser = internalCodeParser
        self.all_dependencies = {}
        self.all_used_by = {}
        self.max_used_by_samples = max_used_by_samples
        self.max_context_token = max_context_token
        self.pagerank_scores = {}
        self.gathered_data = {
            "internal": {
                "class_context": None,
                "dependencies": {},
                "used_by": []
            },
            "external": {
                # "question query": "query result"
            }
        }
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.external_search_system_prompt = """You are a highly-specialized, factual Q&A engine for an expert software developer.
        Your Task: Provide a direct, concise, and technically accurate answer to the user's query.
        
        Critical Rules:
        1.  NO CONVERSATIONAL FILLER: Do not use greetings, apologies, introductory phrases, or concluding remarks.
        2.  BE CONCISE: Provide only the essential information required to answer the query. Omit any historical background, related trivia, or tangential details.
        3.  ASSUME EXPERT KNOWLEDGE: Do not explain basic programming concepts. Focus strictly on the specific subject of the query.
        """

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
        self.pagerank_scores = self.internalCodeParser.find_pagerank_scores()
        
        
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
            key=lambda dep: self.pagerank_scores.get(dep, 0), 
            reverse=True
        )
        
        # 1. Gathering dependencies information
        for dep_id in sorted_dependencies:
            target_component = self.internalCodeParser.get_component_by_id(dep_id)
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
                "signature": target_component.component_signature,
                "component_type": target_component.component_type,
                "content": context_content, # target_component.component_signature
                "pagerank": self.pagerank_scores.get(dep_id, 0)
            }
            
        # 2. Gathering called by information
        # 2a. Gathering class context
        if state['component'].component_type == "method":
            component_class_id = self.internalCodeParser.find_class_prefix_for_method(state["component"].id)
            target_component = self.internalCodeParser.get_component_by_id(component_class_id)
            class_skeleton = self.internalCodeParser.get_class_skeleton(target_component)
            
            gathered_data["internal"]["class_context"] = {
                "id": component_class_id,
                "type": "class_skeleton",
                "signature": target_component.component_signature,
                "content": class_skeleton
            }
        # 2b. Gathering called by information
        if all_used_by:
            used_by_resources = self.internalCodeParser.find_called_by_snippet(state["component"].id, self.max_used_by_samples) 
            if used_by_resources and len(used_by_resources) > 0:
                gathered_data["internal"]["used_by"].extend(used_by_resources)
        
        # Save gathered data information
        self.gathered_data = gathered_data
        with open(DUMMY_TESTING_DIRECTORY / f"Raw_res_{state["component"].id}.json", "w", encoding="utf-8") as f:
            json.dump(gathered_data, f, indent=4, ensure_ascii=False)
        
        return gathered_data
  
    def update_context(self, state: AgentState) -> AgentState:
        logger.info_print("Update Context")
        
        if not self.gathered_data:
            logger.warning_print("Gathered data is empty. Skipping context update.")
            state["context"] = ""
            return state
        
        # Loop untuk memformat dan memvalidasi
        iteration_limit = 20
        for _ in range(iteration_limit):
            # Search and Apply Policy
            context_string = self.format_search_context(self.gathered_data, state["component"].id)
            is_safe, overage_tokens = self.apply_context_policy(context_string, state["focal_component"])
            
            if is_safe:
                break # Keluar dari loop jika konteks sudah valid
            
            # Jika tidak aman, potong data
            self.gathered_data, omissions_update = self.truncate_context(self.gathered_data, overage_tokens)

            # Pengaman agar tidak terjadi infinite loop
            internal_data = self.gathered_data.get("internal", {})
            external_data = self.gathered_data.get("external", {})
            if not internal_data.get("dependencies") and not internal_data.get("used_by") and not internal_data.get("class_context") and not external_data:
                logger.warning_print("Semua konteks telah dipotong. Berhenti.")
                break

        final_context_string = self.format_search_context(self.gathered_data, state["component"].id)
        state["context"] = final_context_string
        return state
    
    def format_search_context(self, context: Dict[str, Any] = None, key: str = "") -> str:
        current_context = context or self.gathered_data
        
        context_parts = []
        
        internal_data = current_context.get("internal", {})
        if internal_data:
            # Bagian 1: Konteks Kelas
            class_context = internal_data.get("class_context")
            if class_context and class_context.get("content"):
                content = class_context["content"]
                # Get class name
                class_name = class_context['id'].split('.')[-1] if class_context['id'] else ""
                
                # Format result
                header = f"### CLASS CONTEXT\n\nThe component is a method within the `{class_name}` class:"
                formatted_block = f"{header}\n\n```python\n{content}\n```"
                context_parts.append(formatted_block)

            internal_context_blocks = []
            # Bagian 2: Dependensi
            dependencies = internal_data.get("dependencies", {})
            if dependencies:
                header = "#### Dependencies\n\nThe component to be documented depends on the following internal components:"
                dep_blocks = []
                for dep_id, info in dependencies.items():
                    block_header = f"**Component:** `{dep_id}`\n**Context Type:** {info['type']}"
                    formatted_block = f"{block_header}\n```python\n{info["content"]}\n```"
                    dep_blocks.append(formatted_block)
                internal_context_blocks.append(f"{header}\n\n" + "\n---\n".join(dep_blocks))
            
            # Bagian 3: Used By (called_by)
            used_by = internal_data.get("used_by", [])
            if used_by:
                header = "#### Usage Examples (`used_by`)\n\nHere are examples of how the component is used:"
                cb_blocks = []
                for usage in used_by:
                    block_header = f"**Source Component:** `{usage['id']}`"
                    formatted_block = f"{block_header}\n```python\n{usage["snippet"]}\n```"
                    cb_blocks.append(formatted_block)
                internal_context_blocks.append(f"{header}\n\n" + "\n---\n".join(cb_blocks))

            if internal_context_blocks:
                context_parts.append("### INTERNAL CONTEXT\n\n" + "\n\n".join(internal_context_blocks))

        # --- B. FORMAT KONTEKS EKSTERNAL ---
        external_data = current_context.get("external", {})
        if external_data:
            header = "### EXTERNAL CONTEXT\n\nInformation retrieved from external sources:"
            ext_blocks = []
            for query, result in external_data.items():
                block_header = f"**Query:** `{query}`"
                formatted_block = f"{block_header}\n**Result:**\n{result}"
                ext_blocks.append(formatted_block)
            context_parts.append(f"{header}\n\n" + "\n---\n".join(ext_blocks))

        formatted_result = "\n\n".join(filter(None, context_parts))
        # with open(DUMMY_TESTING_DIRECTORY / f"FinalContx_{key}{random.randint(0, 1000)}.md", "w", encoding="utf-8") as f:
        #     json.dump(formatted_result, f, indent=4, ensure_ascii=False)
            
        return formatted_result
    
    def apply_context_policy(self, context_string: str, focal_component_code: str) -> Tuple[bool, int]:
        """
        Memvalidasi konteks terhadap batasan token.

        Returns:
            Tuple[bool, int]: 
                - True jika valid, False jika tidak.
                - Jumlah token yang melebihi budget (0 jika valid).
        """
        print("[Policy] Menerapkan kebijakan konteks...")
        
        total_tokens = len(self.tokenizer.encode(context_string, disallowed_special=())) + len(self.tokenizer.encode(focal_component_code))
        
        print(f"[Policy] Total token terhitung: {total_tokens}. Budget: {self.max_context_token}.")
        
        if total_tokens <= self.max_context_token:
            print("[Policy] Konteks valid.")
            return True, 0
        else:
            overage = total_tokens - self.max_context_token
            print(f"[Policy] Konteks melebihi budget. Perlu pemotongan ~{overage} token.")
            return False, overage
        
    def truncate_context(self, gathered_data: Dict[str, Any], tokens_to_remove: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Memotong data yang terkumpul (gathered_data) untuk mengurangi jumlah token.

        Returns:
            Tuple[Dict[str, Any], Dict[str, Any]]: 
                - Data yang sudah dipotong.
                - Dictionary berisi informasi apa yang dihilangkan pada iterasi ini.
        """
        print(f"[Truncate] Memulai proses pemotongan untuk mengurangi ~{tokens_to_remove} token.")
        
        truncated_data = gathered_data.copy()
        omissions_this_round = {"dependencies": [], "used_by": 0, "external": 0}
        
        # TODO: Implementasikan logika pemotongan yang lebih presisi dengan menghitung token.
        # Untuk sekarang, kita gunakan logika sederhana berbasis jumlah item.
        
        # 1. Hapus hasil pencarian eksternal ---
        #    Alasan: Ini seringkali informasi pendukung yang bisa diminta lagi.
        external_data = truncated_data.get("external")
        if external_data:
            removed_query = list(external_data.keys())[-1]
            print(f"    -> [Truncate] Menghapus hasil pencarian eksternal untuk query: '{removed_query}'")
            del external_data[removed_query]
            omissions_this_round["external"] = 1
            return truncated_data, omissions_this_round
        
        # 2. Hapus 'used_by' (contoh penggunaan) terlebih dahulu, karena seringkali
        #    kurang krusial dibandingkan struktur dependensi.
        if truncated_data.get("internal", {}).get("used_by"):
            print("[Truncate] (Template) Menghapus satu contoh 'used_by' terakhir.")
            truncated_data["internal"]["used_by"].pop()
            omissions_this_round["used_by"] = 1
            return truncated_data, omissions_this_round

        # 3. Jika 'used_by' sudah habis, mulai hapus 'dependencies' dari yang
        #    paling tidak penting (skor PageRank terendah).
        dependencies = truncated_data.get("internal", {}).get("dependencies")
        if dependencies:
            # dependensi sudah diurutkan berdasarkan pagerank, jadi yang terakhir adalah yang terendah
            lowest_rank_dep_id = list(dependencies.keys())[-1]
            print(f"[Truncate] (Template) Menghapus dependensi dengan rank terendah: {lowest_rank_dep_id}")
            del dependencies[lowest_rank_dep_id]
            omissions_this_round["dependencies"].append(lowest_rank_dep_id)
            return truncated_data, omissions_this_round

        # 3. Jika semua sudah habis, tidak ada lagi yang bisa dipotong.
        print("[Truncate] Tidak ada lagi yang bisa dipotong.")
        return truncated_data,
    
    def process(self, state: AgentState) -> AgentState:
        """
        Titik masuk utama untuk Searcher. Ia memutuskan pencarian mana yang akan dijalankan.
        """
        print("[Searcher]: Run - Gathering More context ...")

        parsed_request = state.get("reader_response", ReaderOutput(info_need=False))
        
        state = self.gather_internal_information(state, parsed_request)
        state = self.gather_external_information(state, parsed_request)
        
        with open(DUMMY_TESTING_DIRECTORY / f"RS_res_{state["component"].id}.json", "w", encoding="utf-8") as f:
            json.dump(self.gathered_data, f, indent=4, ensure_ascii=False)
        
        return state
    
    def gather_internal_information(self, state: AgentState, parsed_request: ReaderOutput) -> AgentState:
        
        if parsed_request.internal_expand:
            
            for comp_id in parsed_request.internal_expand:
                target_component = self.internalCodeParser.get_component_by_id(comp_id)
                if not target_component:
                    continue
                source_code = self.internalCodeParser.get_component_source_code(comp_id)
                if not source_code:
                    continue
                
                if "dependencies" not in self.gathered_data["internal"]:
                    self.gathered_data["internal"]["dependencies"] = {}
                
                self.gathered_data["internal"]["dependencies"][comp_id] = {
                    "id": comp_id,
                    "type": "source_code (Expanded by request)",
                    "signature": target_component.component_signature,
                    "component_type": target_component.component_type,
                    "content": source_code,
                    "pagerank": self.pagerank_scores.get(comp_id, 0)
                }
                
        return state
    
    def gather_external_information(self, state: AgentState, parsed_request: ReaderOutput) -> AgentState:
        
        # 1. Check apakah terdapat external request
        if not parsed_request.external_retrieval or len(parsed_request.external_retrieval) == 0:
            return state
        
        # 2. Gather external information
        external_results = {}
        for query in parsed_request.external_retrieval:
            if not query: continue
            
            messages = [
                SystemMessage(content=self.external_search_system_prompt),
                HumanMessage(content=query)
            ]
            
            config = {"tags": [self.name], "callbacks": state["callbacks"]}
            response = self.llm.invoke(messages, config=config)
            
            external_results[query] = response.content.strip()

        if external_results:
            
            if "external" not in self.gathered_data:
                self.gathered_data["external"] = {}

            # Tambahkan hasil baru ke data eksternal yang sudah ada (jika ada)
            self.gathered_data["external"].update(external_results)
            
        return state
    
    
    
    
    
# # agents/searcher.py

# import tiktoken
# import re
# from typing import Dict, Any, List

# class Searcher:
#     def __init__(self, internal_code_parser: Any, config: Dict):
#         # ... (inisialisasi yang sama)
#         self.context_budget = config.get('max_context_token', 6000)
#         try:
#             self.tokenizer = tiktoken.get_encoding("cl100k_base")
#         except:
#             self.tokenizer = tiktoken.get_encoding("gpt2")

#     def _count_tokens(self, text: str) -> int:
#         """Menghitung jumlah token dalam sebuah string."""
#         return len(self.tokenizer.encode(text, disallowed_special=()))

#     # ==========================================================================
#     # 1. FUNGSI FORMATTING (Implementasi Lengkap)
#     # ==========================================================================
#     def _format_context(self, gathered_data: Dict[str, Any], omissions: Dict[str, Any] = None) -> str:
#         """
#         Mengubah data terstruktur menjadi string Markdown format ideal.
#         Sekarang juga menerima 'omissions' untuk ditambahkan di akhir.
#         """
#         context_parts = []
#         omissions = omissions or {}

#         # --- A. FORMAT KONTEKS INTERNAL ---
#         internal_data = gathered_data.get("internal", {})
#         if internal_data:
#             # Bagian 1: Konteks Kelas
#             class_context = internal_data.get("class_context")
#             if class_context and class_context.get("content"):
#                 content = class_context["content"]
#                 class_name_match = re.search(r'class (\w+)', content.split('\n')[0])
#                 class_name = class_name_match.group(1) if class_name_match else "the class"
#                 header = f"### CLASS CONTEXT\n\nThe component is a method within the `{class_name}` class:"
#                 context_parts.append(f"{header}\n\n```python\n{content}\n```")

#             internal_context_blocks = []
#             # Bagian 2: Dependensi
#             dependencies = internal_data.get("dependencies", {})
#             if dependencies:
#                 header = "#### Dependencies\n\nThe component to be documented depends on the following internal components:"
#                 dep_blocks = []
#                 for dep_id, info in dependencies.items():
#                     block_header = f"**Component:** `{dep_id}`\n**Context Type:** {info['type']}"
#                     formatted_block = f"{block_header}\n```python\n{info['content']}\n```"
#                     dep_blocks.append(formatted_block)
#                 internal_context_blocks.append(f"{header}\n\n" + "\n---\n".join(dep_blocks))
            
#             # Bagian 3: Used By (called_by)
#             used_by = internal_data.get("used_by", [])
#             if used_by:
#                 header = "#### Usage Examples (`used_by`)\n\nHere are examples of how the component is used:"
#                 cb_blocks = []
#                 for usage in used_by:
#                     block_header = f"**Source Component:** `{usage['source_file']}`"
#                     formatted_block = f"{block_header}\n```python\n{usage['snippet']}\n```"
#                     cb_blocks.append(formatted_block)
#                 internal_context_blocks.append(f"{header}\n\n" + "\n---\n".join(cb_blocks))
            
#             if internal_context_blocks:
#                 context_parts.append("### INTERNAL CONTEXT\n\n" + "\n\n".join(internal_context_blocks))

#         # --- B. FORMAT KONTEKS EKSTERNAL ---
#         external_data = gathered_data.get("external", {})
#         if external_data:
#             header = "### EXTERNAL CONTEXT\n\nInformation retrieved from external sources:"
#             ext_blocks = []
#             for query, result in external_data.items():
#                 block_header = f"**Query:** `{query}`"
#                 formatted_block = f"{block_header}\n\n**Result:**\n{result}"
#                 ext_blocks.append(formatted_block)
#             context_parts.append(f"{header}\n\n" + "\n---\n".join(ext_blocks))

#         # --- C. FORMAT OMISSIONS ---
#         if omissions:
#             omission_notes = []
#             if omissions.get("dependencies"):
#                 note = f"- {len(omissions['dependencies'])} dependencies were omitted, including: `{omissions['dependencies'][0]}`."
#                 omission_notes.append(note)
#             if omissions.get("used_by", 0) > 0:
#                 note = f"- {omissions['used_by']} usage examples were omitted."
#                 omission_notes.append(note)
            
#             if omission_notes:
#                 context_parts.append("---\n**[INFO] Omissions due to context length limits:**\n" + "\n".join(omission_notes))
        
#         return "\n\n".join(filter(None, context_parts))

#     # ==========================================================================
#     # 2. FUNGSI VALIDASI KEBIJAKAN (Implementasi Lengkap)
#     # ==========================================================================
#     def _apply_context_policy(self, context_string: str, focal_component_code: str) -> (bool, int):
#         """
#         Memvalidasi konteks terhadap batasan token.

#         Returns:
#             Tuple[bool, int]: 
#                 - True jika valid, False jika tidak.
#                 - Jumlah token yang melebihi budget (0 jika valid).
#         """
#         print("    -> [Policy] Menerapkan kebijakan konteks...")
        
#         total_tokens = self._count_tokens(context_string) + self._count_tokens(focal_component_code)
        
#         print(f"    -> [Policy] Total token terhitung: {total_tokens}. Budget: {self.context_budget}.")
        
#         if total_tokens <= self.context_budget:
#             print("    -> [Policy] Konteks valid.")
#             return True, 0
#         else:
#             overage = total_tokens - self.context_budget
#             print(f"    -> [Policy] Konteks melebihi budget. Perlu pemotongan ~{overage} token.")
#             return False, overage

#     # ==========================================================================
#     # 3. FUNGSI PEMOTONGAN (Template Detail)
#     # ==========================================================================
#     def _truncate_context(self, gathered_data: Dict[str, Any], tokens_to_remove: int) -> (Dict[str, Any], Dict[str, Any]):
#         """
#         Memotong data yang terkumpul (gathered_data) untuk mengurangi jumlah token.

#         Returns:
#             Tuple[Dict[str, Any], Dict[str, Any]]: 
#                 - Data yang sudah dipotong.
#                 - Dictionary berisi informasi apa yang dihilangkan pada iterasi ini.
#         """
#         print(f"    -> [Truncate] Memulai proses pemotongan untuk mengurangi ~{tokens_to_remove} token.")
        
#         truncated_data = gathered_data.copy()
#         omissions_this_round = {"dependencies": [], "used_by": 0}
        
#         # TODO: Implementasikan logika pemotongan yang lebih presisi dengan menghitung token.
#         # Untuk sekarang, kita gunakan logika sederhana berbasis jumlah item.
        
#         # Strategi Prioritas Pemotongan:
#         # 1. Hapus 'used_by' (contoh penggunaan) terlebih dahulu, karena seringkali
#         #    kurang krusial dibandingkan struktur dependensi.
#         if truncated_data.get("internal", {}).get("used_by"):
#             print("    -> [Truncate] (Template) Menghapus satu contoh 'used_by' terakhir.")
#             truncated_data["internal"]["used_by"].pop()
#             omissions_this_round["used_by"] = 1
#             return truncated_data, omissions_this_round

#         # 2. Jika 'used_by' sudah habis, mulai hapus 'dependencies' dari yang
#         #    paling tidak penting (skor PageRank terendah).
#         dependencies = truncated_data.get("internal", {}).get("dependencies")
#         if dependencies:
#             # dependensi sudah diurutkan berdasarkan pagerank, jadi yang terakhir adalah yang terendah
#             lowest_rank_dep_id = list(dependencies.keys())[-1]
#             print(f"    -> [Truncate] (Template) Menghapus dependensi dengan rank terendah: {lowest_rank_dep_id}")
#             del dependencies[lowest_rank_dep_id]
#             omissions_this_round["dependencies"].append(lowest_rank_dep_id)
#             return truncated_data, omissions_this_round

#         # 3. Jika semua sudah habis, tidak ada lagi yang bisa dipotong.
#         print("    -> [Truncate] Tidak ada lagi yang bisa dipotong.")
#         return truncated_data, omissions_this_round

#     # ==========================================================================
#     # Metode Proses Utama yang Mengintegrasikan Semuanya
#     # ==========================================================================
#     def process(self, state: AgentState) -> AgentState:
#         """
#         Orchestrates the context gathering, formatting, and policy application.
#         """
#         print("--- SEARCHER: Mempersiapkan konteks awal ---")
        
#         gathered_data = self._gather_context_data(state)
#         omissions = {}
        
#         # Loop untuk memformat dan memvalidasi
#         while True:
#             context_string = self._format_context(gathered_data)
#             is_safe, overage_tokens = self._apply_context_policy(context_string, state["focal_component"])
            
#             if is_safe:
#                 # Tambahkan catatan omissions final sebelum keluar dari loop
#                 final_context_string = self._format_context(gathered_data, omissions)
#                 break # Keluar dari loop jika konteks sudah valid
            
#             # Jika tidak aman, potong data
#             gathered_data, omissions_update = self._truncate_context(gathered_data, overage_tokens)
            
#             # Akumulasi catatan omissions
#             for key, value in omissions_update.items():
#                 if isinstance(value, list):
#                     omissions.setdefault(key, []).extend(value)
#                 else:
#                     omissions[key] = omissions.get(key, 0) + value

#             # Pengaman agar tidak terjadi infinite loop
#             internal_data = gathered_data.get("internal", {})
#             if not internal_data.get("dependencies") and not internal_data.get("used_by"):
#                 print("PERINGATAN: Semua konteks dipotong. Konteks mungkin terlalu besar.")
#                 final_context_string = self._format_context(gathered_data, omissions)
#                 break

#         state["context"] = final_context_string
#         return state