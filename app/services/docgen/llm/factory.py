# llm/factory.py

import yaml
import os
from typing import Dict, Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from string import Template

class LLMFactory:
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """Memuat file konfigurasi YAML dan mengganti variabel lingkungan."""
        with open(config_path, 'r') as f:
            raw_config = f.read()
        # Ganti placeholder seperti ${VAR_NAME} dengan nilai env var
        template = Template(raw_config)
        config_str = template.substitute(os.environ)
        return yaml.safe_load(config_str)

    @staticmethod
    def create_llm(llm_config: Dict[str, Any]) -> BaseChatModel:
        """Membuat instance model LangChain berdasarkan konfigurasi."""
        llm_type = llm_config.get("type", "google").lower()

        params = {
            "model": llm_config.get("model"),
            "temperature": llm_config.get("temperature"),
            "google_api_key": llm_config.get("api_key"),
        }
        
        if llm_type == "google":
            params["max_output_tokens"] = llm_config.get("max_output_tokens")
        
        params = {k: v for k, v in params.items() if v is not None}

        if llm_type == "google":
            return ChatGoogleGenerativeAI(**params)
        # Tambahkan provider lain di sini
        # elif llm_type == "openai":
        #     return ChatOpenAI(**params)
        else:
            raise ValueError(f"Tipe LLM '{llm_type}' tidak didukung.")