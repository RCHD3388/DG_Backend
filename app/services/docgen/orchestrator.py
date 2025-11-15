# orchestrator.py

import yaml
import re
from typing import Dict, Any, List
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
from app.utils.file_utils import save_docgen_component_process
from app.services.docgen.agents.agent_output_schema import ReaderOutput

logger = CustomLogger("Orchestrator")

class Orchestrator(OrchestratorBase):
    def __init__(self, repo_path: str = "", config_path: str = YAML_CONFIG_PATH, internalCodeParser: InternalCodeParser = None, task_id: str = "default"):
        logger.info_print("Initiate Manual Orchestrator ...")
        
        self.config = {}
        with open(str(config_path), 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.repo_path = repo_path 
        self.task_id = task_id

        flow_config = self.config.get('flow_control', {})
        self.max_reader_search_attempts = flow_config.get('max_reader_search_attempts', 3)
        self.max_verifier_rejections = flow_config.get('max_verifier_rejections', 2)
        self.max_used_by_samples = flow_config.get('max_used_by_samples', 2)
        self.max_context_token = flow_config.get('max_context_token', 10000)

        # setup Reader, Searcher, Writer, Verifier
        agent_llm_configs = self.config.get('agent_llms', {})
        # -- Ambil config default jika pool agen kosong
        default_llm_config = self.config.get("llm")

        self.writer_pool: List[Writer] = [
            Writer(llm_config=cfg) 
            for cfg in agent_llm_configs.get('writer', [default_llm_config])
        ]
        self.reader_pool: List[Reader] = [
            Reader(llm_config=cfg) 
            for cfg in agent_llm_configs.get('reader', [default_llm_config])
        ]
        self.searcher_pool: List[Searcher] = [
            Searcher(llm_config=cfg,
                    internalCodeParser=internalCodeParser, 
                    max_used_by_samples=self.max_used_by_samples, 
                    max_context_token=self.max_context_token)
            for cfg in agent_llm_configs.get('searcher', [default_llm_config])
        ]
        self.verifier_pool: List[Verifier] = [
            Verifier(llm_config=cfg) 
            for cfg in agent_llm_configs.get('verifier', [default_llm_config])
        ]

        self._pool_index_counter = 0
        self._searcher_pool_index_counter = 0
        
        # self.reader = Reader(config_path=config_path)
        # self.searcher = Searcher(config_path=config_path, 
        #                          internalCodeParser=internalCodeParser, 
        #                          max_used_by_samples=self.max_used_by_samples, 
        #                          max_context_token=self.max_context_token)
        # self.writer = Writer(config_path=config_path)
        # self.verifier = Verifier(config_path=config_path)

    def setup_current_agents(self):
        
        reader_num_sets = len(self.reader_pool)
        searcher_num_sets = len(self.searcher_pool)
        writer_num_sets = len(self.writer_pool)
        verifier_num_sets = len(self.verifier_pool)

         
        if writer_num_sets == 0 or reader_num_sets == 0 or verifier_num_sets == 0 or searcher_num_sets == 0:
            raise Exception("Terdapat module RSWV yang belum diinisialisasi di pool.")
            
        # mendapatkan indeks saat ini
        reader_index = self._pool_index_counter % reader_num_sets
        searcher_index = self._pool_index_counter % searcher_num_sets
        writer_index = self._pool_index_counter % writer_num_sets
        verifier_index = self._pool_index_counter % verifier_num_sets
        
        logger.info_print(f"Menggunakan set agen R [{reader_index}], W [{writer_index}], V [{verifier_index}], S [{searcher_index}] untuk komponen ini.")
        
        self.reader = self.reader_pool[reader_index]
        self.searcher = self.searcher_pool[searcher_index]
        self.writer = self.writer_pool[writer_index]
        self.verifier = self.verifier_pool[verifier_index]
    
    def process(self, component: CodeComponent) -> Dict[str, Any]:
        """Menjalankan seluruh alur kerja dan mengembalikan hasil + statistik."""
        
        # Setup and Clear Memory
        self.setup_current_agents()
        self._pool_index_counter += 1
        
        self.reader.clear_memory()
        self.searcher.clear_memory()
        self.writer.clear_memory()
        self.verifier.clear_memory()
        
        # SETUP PROCESS FOLDER untuk simpan hasil 
        self.current_component_raw_results_path = DUMMY_TESTING_DIRECTORY / f"component_{component.id}"
        self.current_component_raw_results_path.mkdir(parents=True, exist_ok=True)
        
        # Setiap proses mendapatkan callback handler baru
        usage_callback = TokenUsageCallback()
        
        # Check if current source code is too long 
        encoding = tiktoken.get_encoding("cl100k_base")  # Default OpenAI encoding
        token_consume_focal = len(encoding.encode(
            component.source_code,
            disallowed_special=()
            ))
        
        truncated_source_code = component.source_code
        if token_consume_focal > self.max_context_token:
            truncated_source_code = encoding.decode(encoding.encode(component.source_code, disallowed_special=())[:self.max_context_token])
        
        state: AgentState = {
            "component": component,
            "focal_component": truncated_source_code,
            "documentation_json": None,
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
        # SAVE PROCESS SEARCHER INITIAL
        save_docgen_component_process(
                file_path = self.current_component_raw_results_path / f"Searcher_Initial.json",
                content = self.searcher.gathered_data,
                type = "json"
            )

        # --- Loop Reader-Searcher (Sama seperti kode asli Anda) ---
        while True:
            
            # 1. READER PROCESS.
            state = self.reader.process(state)
            
            # SAVE PROCESS READER
            save_docgen_component_process(
                file_path = self.current_component_raw_results_path / f"Reader_{state["reader_search_attempts"]}.json",
                content = state["reader_response"].model_dump() if state["reader_response"] else {},
                type = "json"
                )
            
            # Periksa apakah Reader membutuhkan lebih banyak info
            reader_output = state.get("reader_response", ReaderOutput(info_need=False))
            if reader_output.info_need and state["reader_search_attempts"] < self.max_reader_search_attempts:
                state["reader_search_attempts"] += 1
                
                # 2.1 SEARCHER PROCESS
                self.searcher.process(state)
                # 2.2 Check External retrieval
                if reader_output.external_retrieval and len(reader_output.external_retrieval) > 0:
                    external_searcher_results = {}
                    # Proses semua pencarian eksternal 
                    for reader_query in reader_output.external_retrieval:
                        
                        # Mendapatkan searcher instance
                        current_searcher_index = self._searcher_pool_index_counter % len(self.searcher_pool)
                        searcher_instance = self.searcher_pool[current_searcher_index] 
                        logger.info_print(f"Menggunakan set agen S [{current_searcher_index}] untuk pencarian eksternal.")
                        self._searcher_pool_index_counter += 1
                        
                        # Proses pencarian
                        searcher_query_response = searcher_instance.search_single_external_query(state, reader_query)
                        external_searcher_results[reader_query] = searcher_query_response
                    
                    # Simpan hasil pencarian eksternal
                    if external_searcher_results:
                        if "external" not in self.searcher.gathered_data:
                            self.searcher.gathered_data["external"] = {}
                            
                        # Tambahkan hasil baru ke data eksternal yang sudah ada (jika ada)
                        self.searcher.gathered_data["external"].update(external_searcher_results)
                
                
                # SAVE PROCESS SEARCHER
                save_docgen_component_process(
                        file_path = self.current_component_raw_results_path / f"Searcher_{state["reader_search_attempts"]}.json",
                        content = self.searcher.gathered_data if self.searcher.gathered_data else {},
                        type = "json"
                    )
                
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

            logger.info_print("[-----]")

            # WRITER-VERIFIER CYCLE
            while True:
                
                # 3. WRITER PROCESS
                state = self.writer.process(state)
                # SAVE PROCESS WRITER
                save_docgen_component_process(
                        file_path = self.current_component_raw_results_path / f"Writer_{state['verifier_rejection_count']}.json",
                        content = state["documentation_json"].model_dump() if state["documentation_json"] else {},
                        type = "json"
                    )
                
                # 4. VERIFIER PROCESS 
                if state["verifier_rejection_count"] < self.max_verifier_rejections:
                    state = self.verifier.process(state)
                    # SAVE PROCESS VERIFIER
                    save_docgen_component_process(
                            file_path = self.current_component_raw_results_path / f"Verifier_{state["verifier_rejection_count"]}.txt",
                            content = state["verification_result"] if state["verification_result"] else {},
                            type = "json"
                        )
            
                # Gunakan .get() secara aman untuk menghindari KeyErrors jika 'formatted' tidak ada (misal: exception)
                verification_output = state.get("verification_result", {}).get("formatted", {})
                needs_revision = verification_output.get("needs_revision", True) # Default 'True' jika error
                suggested_next_step = verification_output.get("suggested_next_step", "writer") # Default 'writer' jika error
                
                
                # 1. Kondisi Selesai (Lolos verifikasi ATAU sudah maks percobaan)
                if not needs_revision or state['verifier_rejection_count'] >= self.max_verifier_rejections:
                    if not needs_revision:
                        logger.error_print(f"Verifikasi Lolos untuk {state['component'].id}.")
                    else:
                        logger.error_print(f"Verifikasi sudah mencapai batas maksimum ({state['verifier_rejection_count']}). Berhenti.")
                    
                    return self.return_documentation_result(state, usage_callback)
                
                # 2. Else (Perlu Revisi dan masih ada sisa percobaan)
                else:
                    logger.info_print(f"Verifikasi GAGAL (Percobaan {state['verifier_rejection_count'] + 1}/{self.max_verifier_rejections}). Memulai siklus revisi...")
                    
                    # Tambah counter penolakan
                    state["verifier_rejection_count"] = state['verifier_rejection_count'] + 1
                    self.verifier.clear_memory()
                    verifier_prompt = self.verifier.format_suggested_prompt(state)
                    
                    # 2.1 Reader Cycle
                    if suggested_next_step == "reader":
                        logger.info_print(f"Saran Verifier: Kembali ke 'Reader' untuk konteks tambahan.")
                        
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
                            logger.info_print(f"Saran Verifier: Kembali ke 'Writer' untuk perbaikan konten.")
                        else:
                            logger.info_print(f"Saran Verifier ('{suggested_next_step}') tidak dikenali. Default kembali ke 'Writer'.")
                        
                        self.writer.add_to_memory("user", f"Please improve the documentation based on this suggestion: \n{verifier_prompt}")

    
    def return_documentation_result(self, state: AgentState, usage_callback: TokenUsageCallback) -> Dict[str, Any]:
        """Mengembalikan hasil dokumentasi akhir dan statistik penggunaan token."""
        logger.info_print(usage_callback.get_stats())
        return {
            "final_state": state,
            "usage_stats": usage_callback.get_stats()
        }
        


            #     if not state["verification_result"]["needs_revision"] or state['verifier_rejection_count'] >= self.max_reader_search_attempts:
            #         # -> IF DONE (docstring accepted or max rejections reached, exit loop)
            #         if state['verifier_rejection_count'] >= self.max_reader_search_attempts:
            #             logger.info_print("[Orchestrator]: Verifier max rejections reached.")
            #         else:
            #             logger.info_print("[Orchestrator]: Docstring generated successfully!.. No more revision needed.")

            #         return self.return_documentation_result(state, usage_callback)
            #     else:
            #         # -> ELSE NEED REVISION, increment rejection count and regenerate
            #         state['verifier_rejection_count'] += 1
            #         logger.info_print(f"[Orchestrator] Docstring rejected {state['verifier_rejection_count']} times, regenerating ...")

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