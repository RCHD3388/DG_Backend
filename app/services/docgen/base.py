from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from .llm.factory import LLMFactory
from .state import AgentState

# LangChain Imports
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from app.utils.CustomLogger import CustomLogger

logger = CustomLogger("BaseAgent")

class OrchestratorBase(ABC):
  def __init__(self, name):
    self.name = name


class BaseAgent(ABC):
    """
    Base class untuk agen, terintegrasi dengan LangChain dan
    memiliki fungsionalitas manajemen memori yang dikontrol secara eksternal.
    """
    def __init__(self, name: str, llm_config: Dict[str, Any]):
        self.name = name
        self._memory: list[BaseMessage] = []
        self.llm: BaseChatModel = self._initialize_llm(llm_config)
        self.system_prompt: str = "" # Setiap anak akan mengisi ini

    def _initialize_llm(self, llm_config: Dict[str, Any]) -> BaseChatModel:
        
        if not llm_config:
            raise ValueError(f"Konfigurasi LLM Kosong : {self.name} Agent")
        
        logger.info_print(f"{self.name} LLM Config: {llm_config.get('model')} ({llm_config.get("api_key")})")

        return LLMFactory.create_llm(llm_config)
    
    def add_to_memory(self, role: str, content: str) -> None:
        """Menambah pesan ke memori internal."""
        if role == "system":
            self._memory.append(SystemMessage(content=content))
        elif role == "user":
            self._memory.append(HumanMessage(content=content))
        elif role == "assistant":
            self._memory.append(AIMessage(content=content))

    def refresh_memory(self, new_memory: list[Dict[str, Any]]) -> None:
        """Mengganti memori dengan yang baru, mengonversi ke objek LangChain."""
        self.clear_memory()
        for msg in new_memory:
            self.add_to_memory(msg["role"], msg["content"])

    def clear_memory(self) -> None:
        """Membersihkan memori internal."""
        self._memory = []

    @property
    def memory(self) -> list[BaseMessage]:
        return self._memory.copy()

    @abstractmethod
    def process(self, state: AgentState) -> AgentState:
        """
        Metode proses utama. Berbeda dengan kode asli, sekarang menerima
        dan mengembalikan AgentState untuk integrasi alur kerja yang bersih.
        """
        pass
    
    

# class BaseAgent(ABC):
#     """
#     Base class untuk agen, terintegrasi dengan LangChain dan
#     memiliki fungsionalitas manajemen memori yang dikontrol secara eksternal.
#     """
#     def __init__(self, name: str, config_path: Optional[str] = None):
#         self.name = name
#         self._memory: list[BaseMessage] = []
#         self.llm: BaseChatModel = self._initialize_llm(name, config_path)
#         self.system_prompt: str = "" # Setiap anak akan mengisi ini

#     def _initialize_llm(self, agent_name: str, config_path: Optional[str] = None) -> BaseChatModel:
#         if config_path is None:
#             config_path = "config/agent_config.yaml"
            
#         config = LLMFactory.load_config(config_path)
#         agent_config = config.get("agent_llms", {}).get(agent_name.lower())
        
#         if agent_config: print(f"{agent_name} CONFIG : SPECIFIC LLM Config")
#         else: print(f"{agent_name} CONFIG : DEFAULT LLM Config")
        
#         llm_config = agent_config if agent_config else config.get("llm", {})

#         return LLMFactory.create_llm(llm_config)
    
#     def add_to_memory(self, role: str, content: str) -> None:
#         """Menambah pesan ke memori internal."""
#         if role == "system":
#             self._memory.append(SystemMessage(content=content))
#         elif role == "user":
#             self._memory.append(HumanMessage(content=content))
#         elif role == "assistant":
#             self._memory.append(AIMessage(content=content))

#     def refresh_memory(self, new_memory: list[Dict[str, Any]]) -> None:
#         """Mengganti memori dengan yang baru, mengonversi ke objek LangChain."""
#         self.clear_memory()
#         for msg in new_memory:
#             self.add_to_memory(msg["role"], msg["content"])

#     def clear_memory(self) -> None:
#         """Membersihkan memori internal."""
#         self._memory = []

#     @property
#     def memory(self) -> list[BaseMessage]:
#         return self._memory.copy()

#     @abstractmethod
#     def process(self, state: AgentState) -> AgentState:
#         """
#         Metode proses utama. Berbeda dengan kode asli, sekarang menerima
#         dan mengembalikan AgentState untuk integrasi alur kerja yang bersih.
#         """
#         pass