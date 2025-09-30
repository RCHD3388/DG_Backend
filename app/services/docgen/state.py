# utils/state.py

from typing import TypedDict, Optional, Dict, Any, List

class AgentState(TypedDict):
    """Mendefinisikan state yang mengalir melalui orchestrator."""
    # Input
    focal_component: str
    
    # State Dinamis
    context: str
    reader_response: Optional[str]
    # ... tambahkan field untuk Writer, Verifier nanti

    # Counter Alur Kerja
    reader_search_attempts: int

    # Callback handler untuk melacak token
    callbacks: List[Any]