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
        super().__init__("Reader", config_path)
        
        self.system_prompt = """You are a Reader agent responsible for determining if more context
        is needed to generate a high-quality docstring. You should analyze the code component and
        current context to make this determination.

        You have access to two types of information sources:

        1. Internal Codebase Information (from local code repository):
            For Functions:
            - Code components called within the function body
            - Places where this function is called

            For Methods:
            - Code components called within the method body
            - Places where this method is called
            - The class this method belongs to

            For Classes:
            - Code components called in the __init__ method
            - Places where this class is instantiated
            - Complete class implementation beyond __init__

        2. External Open Internet retrieval Information:
            - External Retrieval is extremely expensive. Only request external open internet retrieval information if the component involves a novel, state of the art, recently-proposed algorithms or techniques.
              (e.g. computing a novel loss function (NDCG Loss, Alignment and Uniformity Loss, etc), certain novel metrics (Cohen's Kappa, etc), specialized novel ideas)
            - Each query should be a clear, natural language question

        Your response should:
        1. First provide a free text analysis of the current code and context
        2. Explain what additional information might be needed (if any)
        3. Include an <INFO_NEED>true</INFO_NEED> tag if more information is needed,
           or <INFO_NEED>false</INFO_NEED> if current context is sufficient
        4. If more information is needed, end your response with a structured request in XML format:

        <REQUEST>
            <INTERNAL>
                <CALLS>
                    <CLASS>class1,class2</CLASS>
                    <FUNCTION>func1,func2</FUNCTION>
                    <METHOD>self.method1,instance.method2,class.method3</METHOD>
                </CALLS>
                <CALL_BY>true/false</CALL_BY>
            </INTERNAL>
            <RETRIEVAL>
                <QUERY>query1,query2</QUERY>
            </RETRIEVAL>
        </REQUEST>

        Important rules for structured request:
        1. For CALLS sections, only include names that are explicitly needed
        2. If no items exist for a category, use empty tags (e.g., <CLASS></CLASS>)
        3. CALL_BY should be "true" only if you need to know what calls/uses a component
        4. Each external QUERY should be a concise, clear, natural language search query
        5. Use comma-separated values without spaces for multiple items
        6. For METHODS, keep dot notation in the same format as the input.
        7. Only first-level calls of the focal code component are accessible. Do not request information on code components that are not directly called by the focal component.
        8. External Open-Internet Retrieval is extremely expensive. Only request external open internet retrieval information if the component involves a novel, state of the art, recently-proposed algorithms or techniques.
              (e.g. computing a novel loss function (NDCG Loss, Alignment and Uniformity Loss, etc), certain novel metrics (Cohen's Kappa, etc), specialized novel ideas)


        Important rules:
        1. Only request internal codebase information that you think is necessary for docstring generation task. For some components that is simple and obvious, you do not need any other information for docstring generation.
        2. External Open-Internet retrieval request is extremely expensive. Only request information that you think is absolutely necessary for docstring generation task.

        <Example_response>
        The current code shows a database connection function. To write a comprehensive docstring, we need to understand:
        1. Where this function is called - this will reveal the expected input patterns and common use cases
        2. What internal database functions it relies on - this will help document any dependencies or prerequisites

        This additional context is necessary because database connections often have specific setup requirements and usage patterns that should be documented for proper implementation.

        <INFO_NEED>true</INFO_NEED>

        <REQUEST>
            <INTERNAL>
                <CALLS>
                    <CLASS></CLASS>
                    <FUNCTION>execute_query,connect_db</FUNCTION>
                    <METHOD>self.process_data,data_processor._internal_process</METHOD>
                </CALLS>
                <CALL_BY>true</CALL_BY>
            </INTERNAL>
            <RETRIEVAL>
                <QUERY></QUERY>
            </RETRIEVAL>
        </REQUEST>

        </Example_response>

        Keep in mind that:

        3. You do not need to generate docstring for the component. Just determine if more information is needed.
        """
        
        self.add_to_memory("system", self.system_prompt)

    def process(self, state: AgentState) -> AgentState:
        """
        Menganalisa kode. Perhatikan bahwa ia TIDAK membersihkan memorinya sendiri.
        Orchestrator yang bertanggung jawab untuk itu.
        """
        print(f"--- READER ---")
        
        # 1. Susun pesan user berdasarkan state saat ini
        task_description = f"""
        <context>
        Current context:
        {state['context'] if state['context'] else 'No context provided yet.'}
        </context>

        <component>
        Analyze the following code component:
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