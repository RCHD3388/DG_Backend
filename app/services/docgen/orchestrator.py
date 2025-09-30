# orchestrator.py

import yaml
import re
from typing import Dict, Any

from app.services.docgen.agents.reader import Reader
from app.services.docgen.state import AgentState
from app.services.docgen.callbacks import TokenUsageCallback
from app.services.docgen.base import OrchestratorBase
from app.core.config import YAML_CONFIG_PATH

class Orchestrator(OrchestratorBase):
    def __init__(self, repo_path: str = "", config_path: str = YAML_CONFIG_PATH):
        print("Initiate Manual Orchestrator ...")
        
        self.config = {}
        with open(str(config_path), 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.repo_path = repo_path 

        flow_config = self.config.get('flow_control', {})
        self.max_reader_search_attempts = flow_config.get('max_reader_search_attempts', 3)

        self.reader = Reader(config_path=config_path)
        # self.searcher = Searcher(config_path=config_path) # Nanti

    def process(self, focal_component: str) -> Dict[str, Any]:
        """Menjalankan seluruh alur kerja dan mengembalikan hasil + statistik."""
        
        # Setiap proses mendapatkan callback handler baru
        usage_callback = TokenUsageCallback()
        
        state: AgentState = {
            "focal_component": focal_component,
            "context": "",
            "reader_response": None,
            "reader_search_attempts": 0,
            "callbacks": [usage_callback]
        }

        # --- Loop Reader-Searcher (Sama seperti kode asli Anda) ---
        while True:
            # Panggil Reader. Reader akan menggunakan memori internalnya.
            state = self.reader.process(state)
            break


        return {
            "result": state['reader_response'],
            "final_state": state,
            "usage_stats": usage_callback.get_stats()
        }
