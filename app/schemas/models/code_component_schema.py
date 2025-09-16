import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum

@dataclass
class CodeComponent:
    """
    Represents a single code component (function, class, or method) in a Python codebase.
    
    Stores the component's identifier, AST node, dependencies, and other metadata.
    """
    # Unique identifier for the component, format: module_path.ClassName.method_name
    id: str
    
    # AST node representing this component
    node: ast.AST
    
    # Type of component: 'class', 'function', or 'method'
    component_type: str
    
    # Full path to the file containing this component
    file_path: str
    
    # Relative path within the repo
    relative_path: str
    
    # Set of component IDs this component depends on
    depends_on: Set[str] = field(default_factory=set)
    
    # Original source code of the component
    source_code: Optional[str] = None
    
    # Line numbers in the file (1-indexed)
    start_line: int = 0
    end_line: int = 0
    
    # Whether the component already has a docstring
    has_docstring: bool = False
    
    # Content of the docstring if it exists, empty string otherwise
    docstring: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert this component to a dictionary representation for JSON serialization."""
        return {
            'id': self.id,
            'component_type': self.component_type,
            'file_path': self.file_path,
            'relative_path': self.relative_path,
            'depends_on': list(self.depends_on),
            'start_line': self.start_line,
            'end_line': self.end_line,
            'has_docstring': self.has_docstring,
            'docstring': self.docstring
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'CodeComponent':
        """Create a CodeComponent from a dictionary representation."""
        component = CodeComponent(
            id=data['id'],
            node=None,  # AST node is not serialized
            component_type=data['component_type'],
            file_path=data['file_path'],
            relative_path=data['relative_path'],
            depends_on=set(data.get('depends_on', [])),
            start_line=data.get('start_line', 0),
            end_line=data.get('end_line', 0),
            has_docstring=data.get('has_docstring', False),
            docstring=data.get('docstring', "")
        )
        return component

class ResolverStrategy(str, Enum):
    FIRST = "main-alternatif"
    SECOND = "second-alternatif"