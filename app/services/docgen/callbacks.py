# utils/callbacks.py (Versi Baru yang Lebih Andal)

from typing import Dict, Any, List, Optional
from uuid import UUID
import pprint

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

class TokenUsageCallback(BaseCallbackHandler):
    """
    Callback Handler yang lebih andal untuk melacak penggunaan token per komponen
    menggunakan pendekatan tumpukan (stack).
    """
    
    def __init__(self):
        self.stats: Dict[str, Dict[str, Any]] = {}
        self._current_tags: List[str] = []
        self._llm_run_tags: Dict[UUID, str] = {}

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], *, run_id: UUID, parent_run_id: UUID | None = None, tags: list[str] | None = None, **kwargs: Any
    ) -> Any:
        # Jika ada tag, dorong tag pertama ke tumpukan
        if tags:
            self._current_tags.append(tags[0])

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], *, run_id: UUID, parent_run_id: UUID | None = None, tags: list[str] | None = None, **kwargs: Any
    ) -> Any:
        # Daftar tag komponen utama Anda (buat lowercase untuk pencarian)
        component_tags = {"writer", "searcher", "reader", "verifier"}

        if tags:
            found_tag = None
            # prioritaskan nama RSWV nya
            for t in tags:
                if t.lower() in component_tags:
                    found_tag = t
                    break
            if found_tag:
                self._llm_run_tags[run_id] = found_tag
            else:
                self._llm_run_tags[run_id] = tags[0]

    def on_chain_end(
        self, outputs: Dict[str, Any], *, run_id: UUID, **kwargs: Any
    ) -> Any:
        # Jika ada tag yang didorong sebelumnya, keluarkan dari tumpukan
        if self._current_tags:
            self._current_tags.pop()

    def on_llm_end(
        self, response: LLMResult, *, run_id: UUID, **kwargs: Any
    ) -> Any:
        """Kumpulkan data saat pemanggilan LLM selesai."""
        
        # --- LOGIKA PENGAMBILAN TAG YANG BARU ---
        # Prioritas 1: Cek apakah ada tag yang disimpan khusus untuk run_id LLM ini
        if run_id in self._llm_run_tags:
            tag = self._llm_run_tags.pop(run_id) # Ambil dan hapus
        # Prioritas 2: Jika tidak, cek tumpukan chain (untuk kasus bersarang)
        elif self._current_tags:
            tag = self._current_tags[-1]
        # Prioritas 3: Jika semua gagal, gunakan 'unknown'
        else:
            tag = "unknown"
        
        if tag not in self.stats:
            self.stats[tag] = {
                "call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            }

        # Dapatkan info token dari respons
        # LangChain untuk Gemini biasanya menempatkan info di sini:
        token_usage = response.generations[0][0].message.usage_metadata

        input_tokens = token_usage.get("input_tokens", 0)
        output_tokens = token_usage.get("output_tokens", 0)
        total_tokens = token_usage.get("total_tokens", 0)

        # Update statistik
        self.stats[tag]["call_count"] += 1
        self.stats[tag]["input_tokens"] += input_tokens
        self.stats[tag]["output_tokens"] += output_tokens
        self.stats[tag]["total_tokens"] += total_tokens

    def get_stats(self) -> Dict[str, Any]:
        """Mengembalikan statistik yang terkumpul."""
        total = {
            "call_count": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0
        }
        for component_stats in self.stats.values():
            for key, value in component_stats.items():
                total[key] += value
        
        return {"components": self.stats, "total": total}

    def reset(self):
        """Mereset statistik untuk proses berikutnya."""
        self.stats = {}
        self._current_tags = []