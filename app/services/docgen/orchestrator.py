# orchestrator.py

import yaml
import re
from typing import Dict, Any

from app.services.docgen.agents.reader import Reader
from app.services.docgen.state import AgentState
from app.services.docgen.callbacks import TokenUsageCallback
from app.services.docgen.base import OrchestratorBase
from app.core.config import YAML_CONFIG_PATH
from app.services.docgen.agents.searcher import Searcher
from app.services.docgen.agents.writer import Writer
from app.services.docgen.agents.verifier import Verifier

class Orchestrator(OrchestratorBase):
    def __init__(self, repo_path: str = "", config_path: str = YAML_CONFIG_PATH):
        print("Initiate Manual Orchestrator ...")
        
        self.config = {}
        with open(str(config_path), 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.repo_path = repo_path 

        flow_config = self.config.get('flow_control', {})
        self.max_reader_search_attempts = flow_config.get('max_reader_search_attempts', 3)
        self.max_verifier_rejections = flow_config.get('max_verifier_rejections', 2)

        self.reader = Reader(config_path=config_path)
        self.searcher = Searcher(config_path=config_path)
        self.writer = Writer(config_path=config_path)
        self.verifier = Verifier(config_path=config_path)

    def process(self, focal_component: str) -> Dict[str, Any]:
        """Menjalankan seluruh alur kerja dan mengembalikan hasil + statistik."""
        
        # Setiap proses mendapatkan callback handler baru
        usage_callback = TokenUsageCallback()
        
        state: AgentState = {
            "focal_component": focal_component,
            "docstring": "",
            "context": "",
            "reader_response": None,
            "reader_search_attempts": 0,
            "callbacks": [usage_callback]
        }

        # --- Loop Reader-Searcher (Sama seperti kode asli Anda) ---
        while True:
            # 1. READER PROCESS.
            state = self.reader.process(state)

            # Periksa apakah Reader membutuhkan lebih banyak info
            match = re.search(r'<INFO_NEED>(.*?)</INFO_NEED>', state['reader_response'], re.DOTALL)
            needs_info = match and match.group(1).strip().lower() == 'true'

            if needs_info and state["reader_search_attempts"] < self.max_reader_search_attempts:
                state["reader_search_attempts"] += 1
                # 2. SEARCHER PROCESS

            else:
                print("[Orchestrator] Searcher max attempts reached.")

            # WRITER-VERIFIER CYCLE
            while True:
                
                # 3. WRITER PROCESS
                state = self.writer.process(state)
                # 4. VERIFIER PROCESS 
                state = self.verifier.process(state)

                if not state["verification_result"]["needs_revision"] or state['verifier_rejection_count'] >= self.max_reader_search_attempts:
                    # -> IF DONE (docstring accepted or max rejections reached, exit loop)
                    if state['verifier_rejection_count'] >= self.max_reader_search_attempts:
                        print("[Orchestrator]: Verifier max rejections reached.")
                    else:
                        print("[Orchestrator]: Docstring generated successfully!.. No more revision needed.")
                    break
                else:
                    # -> ELSE NEED REVISION, increment rejection count and regenerate
                    state['verifier_rejection_count'] += 1
                    print(f"[Orchestrator] Docstring rejected {state['verifier_rejection_count']} times, regenerating ...")

                    self.writer.clear_memory()

                    if state['verification_result']['needs_context']:
                        # -> IF NEED CONTEXT, break to Reader-Searcher loop
                        
                        # 1. Add context suggestion to reader memory
                        # 2. Clear Writer and Verifier memory to start fresh 
                        # 3. Use Break

                        break
                    else:
                        # -> ELSE JUST REGENERATE, continue inner loop
                        
                        # 1. Add suggestion to writer memory
                        # Done

                        break

            break

        return {
            "result": state['reader_response'],
            "final_state": state,
            "usage_stats": usage_callback.get_stats()
        }
