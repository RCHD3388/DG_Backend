# utils/state.py

from typing import TypedDict, Optional, Dict, Any, List

class AgentState(TypedDict):
    """Mendefinisikan state yang mengalir melalui orchestrator."""
    # Input
    focal_component: str
    docstring: Optional[str] 
    
    # State Dinamis
    context: str
    reader_response: Optional[str]
    verification_result: Optional[Dict[str, Any]] # <-- FIELD BARU DITAMBAHKAN

    # Counter Alur Kerja
    reader_search_attempts: int
    verifier_rejection_count: int

    # Callback handler untuk melacak token
    callbacks: List[Any]