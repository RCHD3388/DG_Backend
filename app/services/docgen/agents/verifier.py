# agents/verifier.py

from typing import Optional, Dict, Any
import re

from .base import BaseAgent
from .state import AgentState

class Verifier(BaseAgent):
    """
    Agen Verifier yang mengevaluasi kualitas docstring yang dihasilkan.
    """
    def __init__(self, config_path: Optional[str] = None):
        """Inisialisasi Verifier dengan prompt sistemnya."""
        super().__init__("verifier", config_path=config_path)
        
        self.system_prompt = """You are a Verifier agent responsible for ensuring the quality of generated docstrings. 
        Your role is to evaluate docstrings from the perspective of a first-time user encountering the code component.
        
        Analysis Process:
        1. First read the code component as if you're seeing it for the first time
        2. Read the docstring and analyze how well it helps you understand the code
        3. Evaluate if the docstring provides the right level of abstraction and information
        
        Verification Criteria:
        1. Information Value:
           - Identify parts that merely repeat the code without adding value
           - Flag docstrings that state the obvious without providing insights
           - Check if explanations actually help understand the purpose and usage
        
        2. Appropriate Detail Level:
           - Flag overly detailed technical explanations of implementation
           - Ensure focus is on usage and purpose, not line-by-line explanation
           - Check if internal implementation details are unnecessarily exposed
        
        3. Completeness Check:
           - Verify all required sections are present (summary, args, returns, etc.)
           - Check if each section provides meaningful information
           - Ensure critical usage information is not missing
        
        Output Format:
        Your analysis must include:
        1. <NEED_REVISION>true/false</NEED_REVISION>
           - Indicates if docstring needs improvement
        
        2. If revision needed:
           <MORE_CONTEXT>true/false</MORE_CONTEXT>
           - Indicates if additional context is required for improvement
           - Keep in mind that collecting context is very expensive and may fail, so only use it when absolutely necessary
        
        3. Based on MORE_CONTEXT, provide suggestions at the end of your response:
           If true:
           <SUGGESTION_CONTEXT>explain why and what specific context is needed</SUGGESTION_CONTEXT>
           
           If false:
           <SUGGESTION>specific improvement suggestions</SUGGESTION>
        
        Do not generate other things after </SUGGESTION> or </SUGGESTION_CONTEXT>."""
        
        self.add_to_memory("system", self.system_prompt)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        Mem-parsing respons XML dari LLM menjadi dictionary yang terstruktur.
        Ini adalah implementasi dari _parse_verifier_response dari contoh asli.
        """
        result = {
            'needs_revision': False,
            'needs_context': False,
            'suggestion': '',
            'context_suggestion': ''
        }
        
        # Ekstrak nilai dari setiap tag menggunakan regex
        needs_revision_match = re.search(r'<NEED_REVISION>(.*?)</NEED_REVISION>', response, re.DOTALL)
        if needs_revision_match:
            result['needs_revision'] = needs_revision_match.group(1).strip().lower() == 'true'
        
        more_context_match = re.search(r'<MORE_CONTEXT>(.*?)</MORE_CONTEXT>', response, re.DOTALL)
        if more_context_match:
            result['needs_context'] = more_context_match.group(1).strip().lower() == 'true'
            
        suggestion_match = re.search(r'<SUGGESTION>(.*?)</SUGGESTION>', response, re.DOTALL)
        if suggestion_match:
            result['suggestion'] = suggestion_match.group(1).strip()
            
        context_suggestion_match = re.search(r'<SUGGESTION_CONTEXT>(.*?)</SUGGESTION_CONTEXT>', response, re.DOTALL)
        if context_suggestion_match:
            result['context_suggestion'] = context_suggestion_match.group(1).strip()

        return result

    def process(self, state: AgentState) -> AgentState:
        """
        Menjalankan proses verifikasi dan memperbarui state.
        """
        print("--- VERIFIER ---")
        
        # 1. Ambil data yang relevan dari state
        focal_component = state["focal_component"]
        docstring = state["docstring"]
        context = state["context"]
        
        if not docstring:
            print("PERINGATAN: Tidak ada docstring untuk diverifikasi. Melewatkan Verifier.")
            # Set hasil default jika tidak ada docstring
            state["verification_result"] = {'needs_revision': True, 'suggestion': 'Docstring tidak berhasil dibuat.'}
            return state

        # 2. Susun pesan user untuk LLM
        task_description = f"""
        Context Used:
        {context if context else 'No context was used.'}

        Verify the quality of the following docstring for the following Code Component:
        
        Code Component:
        {focal_component}
        
        Generated Docstring:
        {docstring}
        """
        
        # 3. Kelola memori: selalu mulai dari awal untuk verifikasi yang objektif
        self.clear_memory()
        self.add_to_memory("system", self.system_prompt)
        self.add_to_memory("user", task_description)
        
        # 4. Hasilkan respons mentah dari LLM LangChain
        config = {"tags": [self.name], "callbacks": state["callbacks"]}
        full_response = self.llm.invoke(self.memory, config=config)
        
        # 5. Parsing respons mentah menjadi dictionary yang bersih
        parsed_result = self._parse_response(full_response.content)
        
        # 6. Perbarui state global dengan hasil yang sudah di-parsing
        state["verification_result"] = parsed_result
        
        return state