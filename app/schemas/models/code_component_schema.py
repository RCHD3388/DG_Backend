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
    used_by: Set[str] = field(default_factory=set)
    
    # Original source code of the component
    source_code: Optional[str] = ""
    docgen_final_state: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # Line numbers in the file (1-indexed)
    component_signature: str = ""
    start_line: int = 0
    end_line: int = 0
    header_end_line: int = 0
    
    # Whether the component already has a docstring
    has_docstring: bool = False
    
    # Content of the docstring if it exists, empty string otherwise
    docstring: str = ""
    dependency_graph_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert this component to a dictionary representation for JSON serialization."""
        return {
            'id': self.id,
            'component_type': self.component_type,
            'file_path': self.file_path,
            'relative_path': self.relative_path,
            'depends_on': list(self.depends_on),
            'used_by': list(self.used_by),
            'docgen_final_state': self.docgen_final_state,
            'component_signature': self.component_signature,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'has_docstring': self.has_docstring,
            'docstring': self.docstring,
            'dependency_graph_url': self.dependency_graph_url
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
            used_by=set(data.get('used_by', [])),
            docgen_final_state=data.get('docgen_final_state', ""),
            component_signature=data.get('component_signature', ""),
            start_line=data.get('start_line', 0),
            end_line=data.get('end_line', 0),
            has_docstring=data.get('has_docstring', False),
            docstring=data.get('docstring', ""),
            dependency_graph_url=data.get('dependency_graph_url', "")
        )
        return component

class ResolverStrategy(str, Enum):
    FIRST = "main-alternatif"
    SECOND = "second-alternatif"