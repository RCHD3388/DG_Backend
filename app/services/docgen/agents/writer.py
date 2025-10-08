# agents/writer.py

from typing import Optional
import re

from app.services.docgen.base import BaseAgent
from app.services.docgen.state import AgentState

class Writer(BaseAgent):
    """
    Agen Writer yang menghasilkan docstring berkualitas tinggi berdasarkan
    kode dan konteks yang disediakan dalam AgentState.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Inisialisasi Writer, memuat semua template prompt."""
        super().__init__("Writer", config_path=config_path)
        
        # Base prompt dan prompt spesifik dimuat sekali saat inisialisasi
        self.base_prompt = """You are a Writer agent responsible for generating high-quality 
        docstrings that are both complete and helpful. Accessible context is provided to you for 
        generating the docstring.
        
        General Guidelines:
        1. Make docstrings actionable and specific:
           - Focus on practical usage
           - Highlight important considerations
           - Include warnings or gotchas
        
        2. Use clear, concise language:
           - Avoid jargon unless necessary
           - Use active voice
           - Be direct and specific
        
        3. Type Information:
           - Include precise type hints
           - Note any type constraints
           - Document generic type parameters
        
        4. Context and Integration: 
           - Explain component relationships
           - Note any dependencies
           - Describe side effects
        
        5. Follow Google docstring format:
           - Use consistent indentation
           - Maintain clear section separation
           - Keep related information grouped"""
        
        self.class_prompt = """You are documenting a CLASS. Focus on describing the object it represents 
        and its role in the system.

        Required sections:
        1. Summary: 
           - One-line description focusing on WHAT the class represents
           - Avoid repeating the class name or obvious terms
           - Focus on the core purpose or responsibility
        
        2. Description: 
           - WHY: Explain the motivation and purpose behind this class
           - WHEN: Describe scenarios or conditions where this class should be used
           - WHERE: Explain how it fits into the larger system architecture
           - HOW: Provide a high-level overview of how it achieves its purpose
        
        3. Example: 
           - Show a practical, real-world usage scenario
           - Include initialization and common method calls
           - Demonstrate typical workflow

        Conditional sections:
        1. Parameters (if class's __init__ has parameters):
           - Focus on explaining the significance of each parameter
           - Include valid value ranges or constraints
           - Explain parameter relationships if they exist
        
        2. Attributes:
           - Explain the purpose and significance of each attribute
           - Include type information and valid values
           - Note any dependencies between attributes"""
        
        self.function_prompt = """You are documenting a FUNCTION or METHOD. Focus on describing 
        the action it performs and its effects.

        Required sections:
        1. Summary:
           - One-line description focusing on WHAT the function does
           - Avoid repeating the function name
           - Emphasize the outcome or effect
        
        2. Description:
           - WHY: Explain the purpose and use cases
           - WHEN: Describe when to use this function
           - WHERE: Explain how it fits into the workflow
           - HOW: Provide high-level implementation approach

        Conditional sections:
        1. Args (if present):
           - Explain the significance of each parameter
           - Include valid value ranges or constraints
           - Note any parameter interdependencies
        
        2. Returns:
           - Explain what the return value represents
           - Include possible return values or ranges
           - Note any conditions affecting the return value
        
        3. Raises:
           - List specific conditions triggering each exception
           - Explain how to prevent or handle exceptions
        
        4. Examples (if public and not abstract):
           - Show practical usage scenarios
           - Include common parameter combinations
           - Demonstrate error handling if relevant"""
        
        # Inisialisasi memori dengan prompt sistem dasar
        self.add_to_memory("system", self.base_prompt)
        self.start_tag = "<DOCSTRING>"
        self.end_tag = "</DOCSTRING>"

    def _is_class_component(self, code: str) -> bool:
        """Menentukan apakah komponen kode adalah sebuah kelas."""

        return code.strip().startswith("class ")

    def _get_specific_prompt(self, code: str) -> str:
        """Memilih prompt yang sesuai (kelas atau fungsi/metode)."""

        is_class = self._is_class_component(code)
        additional_prompt = self.class_prompt if is_class else self.function_prompt
        return additional_prompt

    def _extract_docstring(self, response: str) -> str:
        """Mengekstrak docstring dari tag XML di dalam respons LLM."""

        match = re.search(rf'{self.start_tag}(.*?){self.end_tag}', response, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            # Fallback jika tag tidak ditemukan, kembalikan seluruh respons
            print("[Writer]: Docstring tags not found, returning full response.")
            return response.strip()

    def process(self, state: AgentState) -> AgentState:
        """
        Menjalankan proses pembuatan docstring dan memperbarui state.
        """
        print("[Writer]: Run - Generating docstring ...")
        
        focal_component = state["focal_component"]
        context = state["context"]
        
        # 1. Susun pesan user dengan menggabungkan konteks, prompt spesifik, dan kode
        task_description = f"""
        Available context:
        {context if context else "No context was gathered."}

        {self._get_specific_prompt(focal_component)}

        Now, generate a high-quality docstring for the following Code Component based on the Available context:
        
        <FOCAL_CODE_COMPONENT>
        {focal_component}
        </FOCAL_CODE_COMPONENT>

        Keep in mind:
        1. Generate docstring between XML tag: <DOCSTRING> and </DOCSTRING>
        2. Do not add triple quotes (\"\"\") to your generated docstring.
        3. Always double check if the generated docstring is within the XML tags.
        """
        
        # 2. Kelola memori: hapus pesan user sebelumnya, lalu tambahkan yang baru
        self._memory = [msg for msg in self._memory if msg.type != "human"]
        self.add_to_memory("user", task_description)
        
        # 3. Hasilkan respons menggunakan LLM LangChain
        config = {"tags": [self.name], "callbacks": state["callbacks"]}
        full_response = self.llm.invoke(self.memory, config=config)
        
        # 4. Ekstrak docstring bersih dari respons
        generated_docstring = self._extract_docstring(full_response.content)
        
        # 5. Perbarui state global dengan docstring yang dihasilkan
        state["docstring"] = generated_docstring

        # Tambahkan respons AI ke memori untuk konsistensi (opsional, tapi praktik yang baik)
        self.add_to_memory("assistant", generated_docstring)
        
        return state