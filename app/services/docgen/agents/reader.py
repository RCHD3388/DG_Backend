# agents/reader.py

from typing import Optional, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

from ..base import BaseAgent
from ..state import AgentState

class Reader(BaseAgent):
    """Agen Reader yang diimplementasikan menggunakan LangChain."""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__("reader", config_path)
        
        self.system_prompt = """You are a Reader agent responsible for determining if more context
        is needed to generate a high-quality docstring. You should analyze the code component and
        current context to make this determination.

        You have access to three types of information sources:

        1. `### CLASS CONTEXT`: If the component is a method, this section shows the class definition and `__init__` method.
        2. `### INTERNAL CONTEXT`: This section contains information retrieved from the local codebase.
            - `#### Dependencies`: Lists other components (functions, classes, methods) that the main component calls or used.
            - `#### Usage Examples (called_by)`: Shows real code snippets of how the main component is used elsewhere, if found.
        3. `### EXTERNAL CONTEXT`: Information retrieved from the LLM:
            - External Retrieval is extremely expensive. Only request external open internet retrieval information if the component involves a novel, state of the art, recently-proposed algorithms or techniques.
              (e.g. computing a novel loss function (NDCG Loss, Alignment and Uniformity Loss, etc), certain novel metrics (Cohen's Kappa, etc), specialized novel ideas)
            - Each query should be a clear, natural language question

        Your Task :
        Based on the code component and the provided context, you must decide if you have enough information.

        Your response should:
        1. First provide a free text analysis of the current code and context
        2. Explain what additional information might be needed (if any)
        3. Include an <INFO_NEED>true</INFO_NEED> tag if more information is needed,
           or <INFO_NEED>false</INFO_NEED> if current context is sufficient
        4. If more information is needed, you MUST end your response with a structured request in XML format:

        <REQUEST>
            <INTERNAL>
                <EXPAND>component.id.one,component.id.two</EXPAND>
            </INTERNAL>
            <RETRIEVAL>
                <QUERY>query1,query2</QUERY>
            </RETRIEVAL>
        </REQUEST>

        Important rules for structured request:
        1. You have two tools available inside the `<REQUEST>` tag: 
            A. **`EXPAND` (for Internal Code):**
                - Use this to request the full source code for a dependency that was either:
                    a) Provided only as a docstring, and you need to see the implementation logic.
                    b) Mentioned in the `[INFO] Omissions` note as being left out.

            B. `RETRIEVAL` (for External Knowledge):
                - External Open-Internet Retrieval is extremely expensive. Only request external open internet retrieval information if the component involves a novel, state of the art, recently-proposed algorithms or techniques.
                    (e.g. computing a novel loss function (NDCG Loss, Alignment and Uniformity Loss, etc), certain novel metrics (Cohen's Kappa, etc), specialized novel ideas)
                - Each external QUERY should be a concise, clear, natural language search query
                
        2. If no items exist for a category, use empty tags (e.g., <EXPAND></EXPAND>)
        3. Use comma-separated values without spaces for multiple items
        4. Component IDs for `<EXPAND>` MUST be copied EXACTLY.
            - The component ID you want to expand can be found in one places in the context you receive:
                a) Inside a `Dependencies` block, labeled as `Component: component.id.goes.here`.
            - You MUST copy the full, dot-separated ID precisely as it is written.
            - DO NOT invent, shorten, or modify the component IDs in any way. If you are unsure, do not request it.
            
        Important rules:
        1. Only request internal codebase information that you think is necessary for docstring generation task. For some components that is simple and obvious, you do not need any other information for docstring generation.
        2. External Open-Internet (Using LLM) retrieval request is extremely expensive. Only request information that you think is absolutely necessary for docstring generation task.

        Example response:
        The provided context for `calculate_adaptive_learning_rate` shows its dependencies, including `get_loss_gradient`. The 
        docstring for `get_loss_gradient` was given, but it doesn't clarify how it handles sparse gradients, which seems critical for 
        this adaptive function. I need to see its full implementation.
        
        <INFO_NEED>true</INFO_NEED>
        <REQUEST>
            <INTERNAL>
                <EXPAND>optimizers.utils.get_loss_gradient</EXPAND>
            </INTERNAL>
            <RETRIEVAL></RETRIEVAL>
        </REQUEST>

        
        3. Keep in mind that: You do not need to generate docstring for the component. Just determine if more information is needed. Your job is NOT to write the docstring. It is to ensure all necessary information is gathered.
        """
        
        self.add_to_memory("system", self.system_prompt)

    def process(self, state: AgentState) -> AgentState:
        """
        Menganalisa kode. Perhatikan bahwa ia TIDAK membersihkan memorinya sendiri.
        Orchestrator yang bertanggung jawab untuk itu.
        """
        print(f"[Reader]: Run - Analysing component to determine info needs ...")
        
        # 1. Susun pesan user berdasarkan state saat ini
        task_description = f"""
        <context>
        Current context:
        {state['context'] if state['context'] else 'No context provided yet.'}
        </context>

        <component>
        Focal component to be documented:
        {state['focal_component']}
        </component>
        """
        # Hapus pesan user sebelumnya jika ada, lalu tambahkan yang baru
        self._memory = [msg for msg in self._memory if msg.type != "human"]
        self.add_to_memory("user", task_description)

        # 2. Hasilkan respons menggunakan LLM LangChain dengan memori saat ini
        config = {"tags": [self.name], "callbacks": state["callbacks"]}
        response_message = self.llm.invoke(self.memory, config=config)
        
        # 3. Tambahkan respons AI ke memori agar diingat untuk putaran berikutnya (jika diperlukan)
        self.add_to_memory("assistant", response_message.content)

        # 4. Perbarui state global dengan hasil dari pemanggilan ini
        state['reader_response'] = response_message.content

        return state