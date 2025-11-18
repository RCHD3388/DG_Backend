from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ScoreLevel(Enum):
    """Defines the possible score levels for docstring evaluation."""
    POOR = 1
    FAIR = 2
    GOOD = 3
    VERY_GOOD = 4
    EXCELLENT = 5

@dataclass
class SummaryEvaluationExample:
    """Stores an example of docstring summary evaluation with different quality levels."""
    function_signature: str
    summaries: Dict[ScoreLevel, str]
    explanations: Dict[ScoreLevel, str]

@dataclass
class DescriptionEvaluationExample:
    """Stores an example of docstring description evaluation with different quality levels."""
    function_signature: str
    descriptions: Dict[ScoreLevel, str]
    explanations: Dict[ScoreLevel, str]

@dataclass
class ParameterEvaluationExample:
    """Stores an example of docstring parameter evaluation with different quality levels."""
    parameters: Dict[str, str]
    quality_examples: Dict[ScoreLevel, Dict[str, str]]
    explanations: Dict[ScoreLevel, str] 