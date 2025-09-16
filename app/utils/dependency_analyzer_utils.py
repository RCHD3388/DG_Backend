import ast
import os
from pathlib import Path

def add_parent_to_nodes(tree: ast.AST) -> None:
    """
    Add a 'parent' attribute to each node in the AST.
    
    Args:
        tree: The AST to process
    """
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

def file_to_module_path(file_path: Path) -> str:
        """Convert a file path to a Python module path."""
        # Remove .py extension and convert / to .
        path = file_path[:-3] if file_path.endswith(".py") else file_path
        return path.replace(os.path.sep, ".")