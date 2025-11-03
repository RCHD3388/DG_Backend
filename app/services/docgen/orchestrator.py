# orchestrator.py

import yaml
import re
from typing import Dict, Any
import tiktoken
import json

from app.services.docgen.agents.reader import Reader
from app.services.docgen.state import AgentState
from app.services.docgen.callbacks import TokenUsageCallback
from app.services.docgen.base import OrchestratorBase
from app.core.config import YAML_CONFIG_PATH, DUMMY_TESTING_DIRECTORY
from app.services.docgen.agents.searcher import Searcher
from app.services.docgen.agents.writer import Writer
from app.services.docgen.agents.verifier import Verifier
from app.services.docgen.tools.InternalCodeParser import InternalCodeParser
from app.schemas.models.code_component_schema import CodeComponent
from app.utils.CustomLogger import CustomLogger
from app.services.docgen.agents.agent_output_schema import ReaderOutput

logger = CustomLogger("Orchestrator")

class Orchestrator(OrchestratorBase):
    def __init__(self, repo_path: str = "", config_path: str = YAML_CONFIG_PATH, internalCodeParser: InternalCodeParser = None):
        print("[Orchestrator] Initiate Manual Orchestrator ...")
        
        self.config = {}
        with open(str(config_path), 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.repo_path = repo_path 

        flow_config = self.config.get('flow_control', {})
        self.max_reader_search_attempts = flow_config.get('max_reader_search_attempts', 3)
        self.max_verifier_rejections = flow_config.get('max_verifier_rejections', 2)
        self.max_used_by_samples = flow_config.get('max_used_by_samples', 2)
        self.max_context_token = flow_config.get('max_context_token', 10000)

        self.reader = Reader(config_path=config_path)
        self.searcher = Searcher(config_path=config_path, 
                                 internalCodeParser=internalCodeParser, 
                                 max_used_by_samples=self.max_used_by_samples, 
                                 max_context_token=self.max_context_token)
        self.writer = Writer(config_path=config_path)
        self.verifier = Verifier(config_path=config_path)

    def process(self, component: CodeComponent) -> Dict[str, Any]:
        """Menjalankan seluruh alur kerja dan mengembalikan hasil + statistik."""
        
        self.reader.clear_memory()
        self.searcher.clear_memory()
        self.writer.clear_memory()
        self.verifier.clear_memory()
        
        # Setiap proses mendapatkan callback handler baru
        usage_callback = TokenUsageCallback()
        
        # Check if current source code is too long 
        encoding = tiktoken.get_encoding("cl100k_base")  # Default OpenAI encoding
        token_consume_focal = len(encoding.encode(component.source_code))
        
        truncated_source_code = component.source_code
        if token_consume_focal > self.max_context_token:
            truncated_source_code = encoding.decode(encoding.encode(component.source_code)[:self.max_context_token])
        
        state: AgentState = {
            "component": component,
            "focal_component": truncated_source_code,
            "documentation_json": None,
            "docstring": "",
            "context": "",
            "reader_response": None,
            "reader_search_attempts": 0,
            "verifier_rejection_count": 0,
            "verification_result": {},
            "callbacks": [usage_callback]
        }

        # PRE. Search initial context
        self.searcher.find_initial_context(state)
        state = self.searcher.update_context(state)
        # -- set to reader memory
        self.reader.add_to_memory("user", state["context"])
        

        # --- Loop Reader-Searcher (Sama seperti kode asli Anda) ---
        while True:
            
            # 1. READER PROCESS.
            state = self.reader.process(state)
            
            with open(DUMMY_TESTING_DIRECTORY / f"ReRes{state["reader_search_attempts"]}_{state["component"].id}.json", "w", encoding="utf-8") as f:
                json.dump(state["reader_response"].model_dump(), f, indent=4, ensure_ascii=False)   
            
            # Periksa apakah Reader membutuhkan lebih banyak info
            reader_output = state.get("reader_response", ReaderOutput(info_need=False))
            if reader_output.info_need and state["reader_search_attempts"] < self.max_reader_search_attempts:
                state["reader_search_attempts"] += 1
                
                # 2. SEARCHER PROCESS
                self.searcher.process(state)
                state = self.searcher.update_context(state)
                self.reader.refresh_memory([
                    {"role": "system", "content": self.reader.system_prompt},
                    {"role": "user", "content": state["context"]},
                ])
                
                # Continue -> back to reader
                if state["reader_search_attempts"] < self.max_reader_search_attempts:
                    continue
                
            elif reader_output.info_need:
                logger.error_print("Reader max attempts reached.")

            print("[-----]")

            # WRITER-VERIFIER CYCLE
            while True:
                
                # 3. WRITER PROCESS
                state = self.writer.process(state)
                with open(DUMMY_TESTING_DIRECTORY / f"DocRWR_{state["component"].id}.txt", "w", encoding="utf-8") as f:
                    json.dump(state["docstring"], f, indent=4, ensure_ascii=False)
                
                
                # 4. VERIFIER PROCESS 
                if state["verifier_rejection_count"] < self.max_verifier_rejections:
                    state = self.verifier.process(state)
                    with open(DUMMY_TESTING_DIRECTORY / f"VerifierState_{state["component"].id}_{state['verifier_rejection_count']}.txt", "w", encoding="utf-8") as f:
                        json.dump(state["verification_result"], f, indent=4, ensure_ascii=False)

            
                # Gunakan .get() secara aman untuk menghindari KeyErrors jika 'formatted' tidak ada (misal: exception)
                verification_output = state.get("verification_result", {}).get("formatted", {})
                needs_revision = verification_output.get("needs_revision", True) # Default 'True' jika error
                suggested_next_step = verification_output.get("suggested_next_step", "writer") # Default 'writer' jika error
                
                
                # 1. Kondisi Selesai (Lolos verifikasi ATAU sudah maks percobaan)
                if not needs_revision or state['verifier_rejection_count'] >= self.max_verifier_rejections:
                    if not needs_revision:
                        print(f"[Orchestrator]: Verifikasi Lolos untuk {state['component'].id}.")
                    else:
                        print(f"[Orchestrator]: Verifikasi sudah mencapai batas maksimum ({state['verifier_rejection_count']}). Berhenti.")
                    
                    return self.return_documentation_result(state, usage_callback)
                
                # 2. Else (Perlu Revisi dan masih ada sisa percobaan)
                else:
                    print(f"[Orchestrator]: Verifikasi GAGAL (Percobaan {state['verifier_rejection_count'] + 1}/{self.max_verifier_rejections}). Memulai siklus revisi...")
                    
                    # Tambah counter penolakan
                    state["verifier_rejection_count"] = state['verifier_rejection_count'] + 1
                    self.verifier.clear_memory()
                    verifier_prompt = self.verifier.format_suggested_prompt(state)
                    
                    # 2.1 Reader Cycle
                    if suggested_next_step == "reader":
                        print(f"[Orchestrator]: Saran Verifier: Kembali ke 'Reader' untuk konteks tambahan.")
                        
                        # 1. Add context suggestion to reader memory
                        self.reader.add_to_memory("user", f"Additional context needed: \n{verifier_prompt}")
                        # 2. Clear Writer and Verifier memory to start fresh 
                        self.writer.clear_memory()
                        
                        # 3. Cycle rules
                        if state["reader_search_attempts"] < self.max_reader_search_attempts:
                            # 3.1 Kalau reader seacher masih ada kesempatan, break ke reader-searcher loop
                            break
                        else:
                            # 3.2 Kalau sudah habis, langsung return dengan state sekarang
                            return self.return_documentation_result(state, usage_callback)

                    # 2.2 Writer Cycle
                    else:
                        if suggested_next_step == "writer":
                            print(f"[Orchestrator]: Saran Verifier: Kembali ke 'Writer' untuk perbaikan konten.")
                        else:
                            print(f"[Orchestrator]: Saran Verifier ('{suggested_next_step}') tidak dikenali. Default kembali ke 'Writer'.")
                        
                        self.writer.add_to_memory("user", f"Please improve the documentation based on this suggestion: \n{verifier_prompt}")

    
    def return_documentation_result(self, state: AgentState, usage_callback: TokenUsageCallback) -> Dict[str, Any]:
        """Mengembalikan hasil dokumentasi akhir dan statistik penggunaan token."""
        return {
            "final_state": state,
            "usage_stats": usage_callback.get_stats()
        }
        


            #     if not state["verification_result"]["needs_revision"] or state['verifier_rejection_count'] >= self.max_reader_search_attempts:
            #         # -> IF DONE (docstring accepted or max rejections reached, exit loop)
            #         if state['verifier_rejection_count'] >= self.max_reader_search_attempts:
            #             print("[Orchestrator]: Verifier max rejections reached.")
            #         else:
            #             print("[Orchestrator]: Docstring generated successfully!.. No more revision needed.")

            #         return self.return_documentation_result(state, usage_callback)
            #     else:
            #         # -> ELSE NEED REVISION, increment rejection count and regenerate
            #         state['verifier_rejection_count'] += 1
            #         print(f"[Orchestrator] Docstring rejected {state['verifier_rejection_count']} times, regenerating ...")

            #         self.writer.clear_memory()

            #         if state['verification_result']['needs_context']:
            #             # -> IF NEED CONTEXT, break to Reader-Searcher loop
                        
            #             # 1. Add context suggestion to reader memory
            #             self.reader.add_to_memory("user", 
            #                 f"Additional context needed: {state['verification_result']['context_suggestion']}"
            #             )
            #             # 2. Clear Writer and Verifier memory to start fresh 
            #             self.writer.clear_memory()
            #             # 3. Use Break
            #             break
                    
            #         else:
            #             # -> ELSE JUST REGENERATE, continue inner loop
                        
            #             # 1. Add suggestion to writer memory
            #             self.writer.add_to_memory("user", 
            #                 f"Please improve the docstring based on this suggestion: {state['verification_result']['context_suggestion']}"
            #             )
            #             # Done