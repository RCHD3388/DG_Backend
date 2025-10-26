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
            
            with open(DUMMY_TESTING_DIRECTORY / f"ReRes{state["reader_search_attempts"]}_{state["component"].id}.md", "w", encoding="utf-8") as f:
                json.dump(state["reader_response"], f, indent=4, ensure_ascii=False)   
            
            # Periksa apakah Reader membutuhkan lebih banyak info
            match = re.search(r'<INFO_NEED>(.*?)</INFO_NEED>', state['reader_response'], re.DOTALL)
            needs_info = match and match.group(1).strip().lower() == 'true'

            if needs_info and state["reader_search_attempts"] < self.max_reader_search_attempts:
                state["reader_search_attempts"] += 1
                
                # 2. SEARCHER PROCESS
                self.searcher.process(state)
                state = self.searcher.update_context(state)
                self.reader.refresh_memory([
                    {"role": "system", "content": self.reader.system_prompt},
                    {"role": "user", "content": state["context"]},
                ])
                
                # Continue -> back to reader
                continue
            elif needs_info:
                logger.error_print("Reader max attempts reached.")

            print("[-----]")

            # WRITER-VERIFIER CYCLE
            while True:
                
                # 3. WRITER PROCESS
                state = self.writer.process(state)
                with open(DUMMY_TESTING_DIRECTORY / f"DocRWR_{state["component"].id}.txt", "w", encoding="utf-8") as f:
                    json.dump(state["docstring"], f, indent=4, ensure_ascii=False)
                
                
                # 4. VERIFIER PROCESS 
                state = self.verifier.process(state)
                with open(DUMMY_TESTING_DIRECTORY / f"VerifierState_{state["component"].id}.txt", "w", encoding="utf-8") as f:
                    json.dump(state["verification_result"], f, indent=4, ensure_ascii=False)

                return self.return_documentation_result(state, usage_callback)
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

    
    def return_documentation_result(self, state: AgentState, usage_callback: TokenUsageCallback) -> Dict[str, Any]:
        """Mengembalikan hasil dokumentasi akhir dan statistik penggunaan token."""
        return {
            "docstring": state["docstring"],
            "context": state["context"],
            "final_state": state,
            "usage_stats": usage_callback.get_stats()
        }
        
