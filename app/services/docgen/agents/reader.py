# agents/reader.py

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

import traceback

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from langchain_core.globals import set_debug 

from ..base import BaseAgent
from ..state import AgentState

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable
from app.services.docgen.agents.agent_output_schema import ReaderOutput
# ==============================================================================
# 2. IMPLEMENTASI AGEN READER (BARU)
# ==============================================================================

class Reader(BaseAgent):
    """
    Agen Reader yang diimplementasikan menggunakan LangChain LCEL 
    dan menghasilkan output JSON terstruktur.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Inisialisasi Reader, parser, template, dan chain."""
        super().__init__("Reader", config_path=config_path)
        
        # 2.1. Inisialisasi Parser Pydantic
        self.json_parser = PydanticOutputParser(pydantic_object=ReaderOutput)
        
        # 2.2. Definisi Prompt Sistem (Diadaptasi untuk JSON)
        self.system_prompt_template: str = """You are a Reader agent responsible for determining if more context is needed to generate a high-quality docstring. You should analyze the code component and current context to make this determination.

1. `### CLASS CONTEXT`: If the component is a method, this section shows the class definition and `__init__` method.
2. `### INTERNAL CONTEXT`: This section contains information retrieved from the local codebase.
    - `#### Dependencies`: Lists other components (functions, classes, methods) that the main component calls or used.
    - `#### Usage Examples (called_by)`: Shows real code snippets of how the main component is used elsewhere, if found.
3. `### EXTERNAL CONTEXT`: Information retrieved from the LLM:
    - External Retrieval is extremely expensive. Only request external open internet retrieval information if the component involves a novel, state of the art, recently-proposed algorithms or techniques.
        (e.g. computing a novel loss function (NDCG Loss, Alignment and Uniformity Loss, etc), certain novel metrics (Cohen's Kappa, etc), specialized novel ideas)
    - Each query should be a clear, natural language question

Your Task:
Based on the code component and the provided context, you must decide if you have enough information OR if more context needs to be gathered using the available tools (`EXPAND` for internal code, `RETRIEVAL` for external knowledge).

Output Format:
Your ENTIRE output MUST be a single, valid JSON object strictly adhering to the schema provided under `OUTPUT FORMAT INSTRUCTIONS`. Do not add any text or explanation outside the JSON structure.

Tool Rules:
1. `internal_expand` (Internal Code Expansion):
   - Use this to request the full source code for a dependency ID listed in the `### INTERNAL CONTEXT` under `Dependencies`.
   - Request ONLY if the existing context (docstring/summary) for that dependency is insufficient to understand its role.
   - To make a request, you MUST use the component's unique component ID
   - The component ID you want to expand should be found EXCLUSIVELY in the `Dependencies` block, labeled as `Component: component.id.goes.here`.
   - **CRITICAL**: You MUST copy the full, dot-separated ID precisely as it appears in the `Dependencies` section.
   - **DO NOT** request IDs mentioned elsewhere (e.g., in code examples or external context).
   - **DO NOT** invent, shorten, modify, guess, or infer component IDs in any way.
   - **If an ID is not explicitly listed under `Dependencies`, you CANNOT request it.**
   - **Invalid or hallucinated IDs will be ignored.** If you are unsure about an ID, it is better to leave `internal_expand` empty for that ID.
2. `external_retrieval` (External Knowledge Search):
   - CRITICAL: This is very expensive. Use ONLY if the code involves novel, state-of-the-art, or very recently proposed algorithms/techniques NOT explainable by standard programming knowledge or existing context.
   - (Examples: Novel loss functions, specific niche metrics, very new research concepts).
   - If used, provide concise, clear, natural language search queries.

Decision Logic (`info_need`):
- Set `info_need` to `false` if the current context and code are sufficient to write a good docstring.
- Set `info_need` to `true` if you need to request more context using `internal_expand` or `external_retrieval`.

IMPORTANT: Your job is NOT to write the docstring, only to determine if information gathering is complete. Focus on necessity. Often, no extra info is needed.
"""
        # 2.3. Definisi Template Pesan Human (akan dibuat di _build_human_prompt)
        # Kita tidak mendefinisikannya di sini lagi

        # 2.4. Inisialisasi Chain LLM (LCEL)
        self.llm_chain: Runnable = self._setup_reader_chain()

    def _setup_reader_chain(self) -> Runnable:
        """Membangun chain LCEL untuk Reader."""
        
        format_instructions = self.json_parser.get_format_instructions()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt_template + \
                       "\n\nOUTPUT FORMAT INSTRUCTIONS (JSON):\n---\n{format_instructions}\n---"),
            MessagesPlaceholder(variable_name="chat_history")
        ]).partial(format_instructions=format_instructions)
        
        chain = prompt | self.llm | self.json_parser
        return chain

    def _build_human_prompt(self, state: AgentState) -> str:
        """Membangun string prompt manusia untuk Reader."""
        
        context = state.get('context', 'No context provided yet.')
        focal_component = state['focal_component']
        
        # (Anda bisa menyesuaikan format ini jika perlu)
        task_description = f"""
Current Context:
---
{context}
---

Focal Component to be Documented:
---
{focal_component}
---

Analyze the component and context. Decide if more information is needed via EXPAND or RETRIEVAL, and generate the required JSON output.
"""
        return task_description

    def process(self, state: AgentState) -> AgentState:
        """
        Menganalisa kode menggunakan LCEL chain dan output JSON.
        """
        print(f"[Reader]: Run - Analysing component to determine info needs...")
        
        if not self.llm_chain:
            self.llm_chain = self._setup_reader_chain()

        config = {"tags": [self.name], "callbacks": state.get("callbacks", [])}

        # 1. Bangun prompt manusia
        human_task_prompt = self._build_human_prompt(state)
        
        # 2. Tambahkan prompt tugas ke memori
        # Diasumsikan Orchestrator membersihkan memori SEBELUM panggilan ini
        # Jika ada feedback dari Verifier ('reader_prompt_suggestion'), itu sudah ada di memori
        self.add_to_memory("user", human_task_prompt)
        
        # 3. Siapkan input untuk chain
        llm_input = {"chat_history": self.memory}
        
        parsed_output: Optional[ReaderOutput] = None
        
        try:
            # 4. Panggil chain LANGSUNG (sudah termasuk parsing)
            parsed_output: ReaderOutput = self.llm_chain.invoke(llm_input, config=config)

            # 5. Simpan output (sukses) ke memori (Simpan JSON string-nya)
            self.add_to_memory("assistant", parsed_output.model_dump_json())

        except Exception as e: # Tangkap SEMUA exception (LLM error, Parsing Error)
            print(f"[Reader]: CRITICAL: LLM Reader chain failed! Error: {e}")
            print(traceback.format_exc())

            # 6. Buat output default saat GAGAL
            parsed_output = ReaderOutput(info_need=False) # Default: anggap tidak perlu info

            # 7. Simpan pesan error ke memori (opsional, tapi bagus untuk debug)
            error_msg = f'{{"error": "Reader failed", "details": "{str(e)}"}}'
            self.add_to_memory("assistant", error_msg)
            
        state['reader_response'] = parsed_output # Menyimpan objek Pydantic

        return state
    

# BASE VERSION READER V0
# class Reader(BaseAgent):
#     """Agen Reader yang diimplementasikan menggunakan LangChain."""
    
#     def __init__(self, config_path: Optional[str] = None):
#         super().__init__("reader", config_path)
        
#         self.system_prompt = """You are a Reader agent responsible for determining if more context
#         is needed to generate a high-quality docstring. You should analyze the code component and
#         current context to make this determination.

#         You have access to three types of information sources:

#         1. `### CLASS CONTEXT`: If the component is a method, this section shows the class definition and `__init__` method.
#         2. `### INTERNAL CONTEXT`: This section contains information retrieved from the local codebase.
#             - `#### Dependencies`: Lists other components (functions, classes, methods) that the main component calls or used.
#             - `#### Usage Examples (called_by)`: Shows real code snippets of how the main component is used elsewhere, if found.
#         3. `### EXTERNAL CONTEXT`: Information retrieved from the LLM:
#             - External Retrieval is extremely expensive. Only request external open internet retrieval information if the component involves a novel, state of the art, recently-proposed algorithms or techniques.
#               (e.g. computing a novel loss function (NDCG Loss, Alignment and Uniformity Loss, etc), certain novel metrics (Cohen's Kappa, etc), specialized novel ideas)
#             - Each query should be a clear, natural language question

#         Your Task :
#         Based on the code component and the provided context, you must decide if you have enough information.

#         Your response should:
#         1. Your response MUST BE a single, valid XML block
#         2. DO NOT provide any text, or explanation before or after the XML structure. Your entire response MUST conform strictly to the following format
#         -. Include an <INFO_NEED>true</INFO_NEED> tag if more information is needed,
#            or <INFO_NEED>false</INFO_NEED> if current context is sufficient
#         -. If more information is needed, you MUST end your response with a structured request in XML format:
        
#         <REQUEST>
#             <INTERNAL>
#                 <EXPAND>component.id.one,component.id.two</EXPAND>
#             </INTERNAL>
#             <RETRIEVAL>
#                 <QUERY>query1,query2</QUERY>
#             </RETRIEVAL>
#         </REQUEST>

#         Important rules for structured request:
#         1. You have two tools available inside the `<REQUEST>` tag: 
#             A. `EXPAND` (for Internal Code):
#                 - Use this to request the full source code for a dependency that was either:
#                     a) Provided only as a docstring, and you need to see the implementation logic.
#                 - To make a request, you MUST use the component's unique component ID
#                 - The component ID you want to expand should be found in one place in the context you receive:
#                     a) Inside a `Dependencies` block, labeled as `Component: component.id.goes.here`.
#                 - You MUST copy the full, dot-separated ID precisely as it is written.
#                 - DO NOT invent, shorten, or modify the component IDs in any way. If you are unsure, do not request it.
#             B. `RETRIEVAL` (for External Knowledge):
#                 - External Open-Internet Retrieval is extremely expensive. Only request external open internet retrieval information if the component involves a novel, state of the art, recently-proposed algorithms or techniques.
#                     (e.g. computing a novel loss function (NDCG Loss, Alignment and Uniformity Loss, etc), certain novel metrics (Cohen's Kappa, etc), specialized novel ideas)
#                 - Each external QUERY should be a concise, clear, natural language search query
                
#         2. If no items exist for a category, use empty tags (e.g., <EXPAND></EXPAND>)
#         3. Use comma-separated values without spaces for multiple items
            
#         Important rules:
#         1. Only request internal codebase information that you think is necessary for docstring generation task. For some components that is simple and obvious, you do not need any other information for docstring generation.
#         2. FINAL CHECK: Any component ID requested in `<EXPAND>` MUST be a literal copy of an ID found in the current context's `Dependencies` block.
#         3. External Open-Internet (Using LLM) retrieval request is extremely expensive. Only request information that you think is absolutely necessary for docstring generation task.

#         Example response:
#         <INFO_NEED>true</INFO_NEED>
#         <REQUEST>
#             <INTERNAL>
#                 <EXPAND>optimizers.utils.get_loss_gradient</EXPAND>
#             </INTERNAL>
#             <RETRIEVAL>query1</RETRIEVAL>
#         </REQUEST>

        
#         3. Keep in mind that: You do not need to generate docstring for the component. Just determine if more information is needed. Your job is NOT to write the docstring. It is to ensure all necessary information is gathered.
#         """
        
#         self.add_to_memory("system", self.system_prompt)

#     def process(self, state: AgentState) -> AgentState:
#         """
#         Menganalisa kode. Perhatikan bahwa ia TIDAK membersihkan memorinya sendiri.
#         Orchestrator yang bertanggung jawab untuk itu.
#         """
#         print(f"[Reader]: Run - Analysing component to determine info needs ...")
        
#         # 1. Susun pesan user berdasarkan state saat ini
#         task_description = f"""
#         <context>
#         Current context:
#         {state['context'] if state['context'] else 'No context provided yet.'}
#         </context>

#         <component>
#         Focal component to be documented:
#         {state['focal_component']}
#         </component>
#         """
#         # Hapus pesan user sebelumnya jika ada, lalu tambahkan yang baru
#         self._memory = [msg for msg in self._memory if msg.type != "human"]
#         self.add_to_memory("user", task_description)

#         # 2. Hasilkan respons menggunakan LLM LangChain dengan memori saat ini
#         config = {"tags": [self.name], "callbacks": state["callbacks"]}
#         print(self.memory)
#         response_message = self.llm.invoke(self.memory, config=config)
        
#         # 3. Tambahkan respons AI ke memori agar diingat untuk putaran berikutnya (jika diperlukan)
#         self.add_to_memory("assistant", response_message.content)

#         # 4. Perbarui state global dengan hasil dari pemanggilan ini
#         state['reader_response'] = response_message.content

#         return state