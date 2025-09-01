from typing import Dict, List, Set, Tuple, Optional, Any, Union
import os
import ast
import json
from pathlib import Path
from dataclasses import dataclass, field
import logging

from app.services.dependency_analyzer.collector import DependencyCollector, ImportCollector
logger = logging.getLogger("Dependency Parser")

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

def add_parent_to_nodes(tree: ast.AST) -> None:
    """
    Add a 'parent' attribute to each node in the AST.
    
    Args:
        tree: The AST to process
    """
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

class DependencyParser:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.relevant_files: List[Path] = []
        self.components: Dict[str, CodeComponent] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
        self.modules: Set[str] = set()

    def parse_repository(self):
        if not self.relevant_files:
            self.relevant_files = self.get_relevant_files()

        print(f"Repo path (parsing): {self.repo_path}")

        # FIRST PASS: Collect all components
        for file_path in self.relevant_files:
            relative_path = file_path.relative_to(self.repo_path)
            module_path = self._file_to_module_path(str(relative_path))
            self.modules.add(module_path)

            # Parse the file to collect components
            self._parse_file(str(file_path), str(relative_path), module_path)

        # SECOND PASS: build dependencies
        self._resolve_dependencies()

        # THIRD PASS: class and method dependencies
        self._add_class_method_dependencies()

        logger.info(f"Total components collected: {len(self.components)}")
        return self.components

    def get_relevant_files(self):
        logger.info(f"Parsing repository at {self.repo_path}")

        all_py_files = self.repo_path.rglob('*.py')
        current_relevant_files = []
        for file_path in all_py_files:
            path_parts = {part.lower() for part in file_path.parts}
        
            # Kondisi untuk mengecualikan file
            is_in_venv = "venv" in path_parts
            is_in_pycache = "__pycache__" in path_parts
            is_in_tests_dir = "tests" in path_parts or "test" in path_parts
            is_test_file = file_path.name.startswith("test_") or file_path.name.endswith("_test.py")

            # Jika tidak ada kondisi pengecualian yang terpenuhi, tambahkan file ke list
            if not (is_in_venv or is_in_pycache or is_in_tests_dir or is_test_file):
                current_relevant_files.append(file_path)
                # logging.info(f"{file_path}")

        logger.info(f"Total relevant Python files to parse: {len(current_relevant_files)}")
        self.relevant_files = current_relevant_files

        return current_relevant_files
    
    def _file_to_module_path(self, file_path: Path) -> str:
        """Convert a file path to a Python module path."""
        # Remove .py extension and convert / to .
        path = file_path[:-3] if file_path.endswith(".py") else file_path
        return path.replace(os.path.sep, ".")
    # --- PARSING FILES START ---
    def _parse_file(self, file_path: str, relative_path: str, module_path: str):
        """Parse a single Python file to collect code components."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)

            # Add parent field to AST nodes for easier traversal
            add_parent_to_nodes(tree)
            
            # Collect Project Components
            self._collect_components(tree, file_path, relative_path, module_path, source)

        except (SyntaxError, UnicodeDecodeError) as e:
            logger.warning(f"Error parsing {file_path}: {e}")

    def _collect_components(self, tree: ast.AST, file_path: str, relative_path: str, 
                          module_path: str, source: str):
        """Collect all code components (functions, classes, methods) from an AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Class definition
                class_id = f"{module_path}.{node.name}"
                
                # Check if the class has a docstring
                has_docstring = (
                    len(node.body) > 0 
                    and isinstance(node.body[0], ast.Expr) 
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                )
                
                # Extract docstring if it exists
                docstring = self._get_docstring(source, node) if has_docstring else ""
                
                component = CodeComponent(
                    id=class_id,
                    node=node,
                    component_type="class",
                    file_path=file_path,
                    relative_path=relative_path,
                    source_code=self._get_source_segment(source, node),
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    has_docstring=has_docstring,
                    docstring=docstring
                )
                
                self.components[class_id] = component
                
                # Collect methods within the class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_id = f"{class_id}.{item.name}"
                        
                        # Check if the method has a docstring
                        method_has_docstring = (
                            len(item.body) > 0 
                            and isinstance(item.body[0], ast.Expr) 
                            and isinstance(item.body[0].value, ast.Constant)
                            and isinstance(item.body[0].value.value, str)
                        )
                        
                        # Extract docstring if it exists
                        method_docstring = self._get_docstring(source, item) if method_has_docstring else ""
                        
                        method_component = CodeComponent(
                            id=method_id,
                            node=item,
                            component_type="method",
                            file_path=file_path,
                            relative_path=relative_path,
                            source_code=self._get_source_segment(source, item),
                            start_line=item.lineno,
                            end_line=getattr(item, "end_lineno", item.lineno),
                            has_docstring=method_has_docstring,
                            docstring=method_docstring
                        )
                        
                        self.components[method_id] = method_component
            
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only collect top-level functions
                if hasattr(node, 'parent') and isinstance(node.parent, ast.Module):
                    func_id = f"{module_path}.{node.name}"
                    
                    # Check if the function has a docstring
                    has_docstring = (
                        len(node.body) > 0 
                        and isinstance(node.body[0], ast.Expr) 
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    )
                    
                    # Extract docstring if it exists
                    docstring = self._get_docstring(source, node) if has_docstring else ""
                    
                    component = CodeComponent(
                        id=func_id,
                        node=node,
                        component_type="function",
                        file_path=file_path,
                        relative_path=relative_path,
                        source_code=self._get_source_segment(source, node),
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        has_docstring=has_docstring,
                        docstring=docstring
                    )
                    
                    self.components[func_id] = component

    def _get_source_segment(self, source: str, node: ast.AST) -> str:
        """Get source code segment for an AST node."""
        try:
            if hasattr(ast, "get_source_segment"):
                segment = ast.get_source_segment(source, node)
                if segment is not None:
                    return segment
            
            # Fallback to manual extraction
            lines = source.split("\n")
            start_line = node.lineno - 1
            end_line = getattr(node, "end_lineno", node.lineno) - 1
            return "\n".join(lines[start_line:end_line + 1])
        
        except Exception as e:
            logger.warning(f"Error getting source segment: {e}")
            return ""
    
    def _get_docstring(self, source: str, node: ast.AST) -> str:
        """Get the docstring for a given AST node."""
        try:
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                for item in node.body:
                    if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
                        if isinstance(item.value.value, str):
                            return item.value.value
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant):
                        if isinstance(item.value.value, str):
                            return item.value.value
            return ""
        except Exception as e:
            logger.warning(f"Error getting docstring: {e}")
            return 
    
    # --- PARSING FILES END ---

    # --- RESOLVE DEPENDENCIES START ---
    def _resolve_dependencies(self):
        for component_id, component in self.components.items():
            file_path = component.file_path

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    source = f.read()
                
                # Parse file to get imports
                tree = ast.parse(source)
                
                # Add parent field to AST nodes for easier traversal
                add_parent_to_nodes(tree)
                
                # Collect imports
                import_collector = ImportCollector()
                import_collector.visit(tree)

                # Find the component node in the tree
                component_node = None
                module_path = self._file_to_module_path(component.relative_path)
                
                if component.component_type == "function":
                    # Find top-level function
                    for node in ast.iter_child_nodes(tree):
                        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) 
                                and node.name == component.id.split(".")[-1]):
                            component_node = node
                            break
                
                elif component.component_type == "class":
                    # Find class
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.ClassDef) and node.name == component.id.split(".")[-1]:
                            component_node = node
                            break
                
                elif component.component_type == "method":
                    # Find method inside class
                    class_name, method_name = component.id.split(".")[-2:]
                    class_node = None
                    
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.ClassDef) and node.name == class_name:
                            class_node = node
                            for item in node.body:
                                if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) 
                                        and item.name == method_name):
                                    component_node = item
                                    break
                            break
                
                if component_node:
                    # Collect dependencies for this specific component
                    dependency_collector = DependencyCollector(
                        import_collector.imports,
                        import_collector.from_imports,
                        module_path,
                        self.modules
                    )
                    
                    # For functions and methods, collect variables defined in the function
                    if isinstance(component_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Add function parameters to local variables
                        for arg in component_node.args.args:
                            dependency_collector.local_variables.add(arg.arg)
                            
                    dependency_collector.visit(component_node)
                    
                    # Add dependencies to the component
                    component.depends_on.update(dependency_collector.dependencies)
                    
                    # Filter out non-existent dependencies
                    component.depends_on = {
                        dep for dep in component.depends_on 
                        if dep in self.components or dep.split(".", 1)[0] in self.modules
                    }
                
            except (SyntaxError, UnicodeDecodeError) as e:
                logger.warning(f"Error analyzing dependencies in {file_path}: {e}")

    def _add_class_method_dependencies(self):
        """
        Third pass to make classes dependent on their methods (except __init__).
        """
        # Group components by class
        class_methods = {}
        
        # Collect all methods for each class
        for component_id, component in self.components.items():
            if component.component_type == "method":
                parts = component_id.split(".")
                if len(parts) >= 2:
                    method_name = parts[-1]
                    class_id = ".".join(parts[:-1])
                    
                    if class_id not in class_methods:
                        class_methods[class_id] = []
                    
                    # Don't include __init__ methods as dependencies of the class
                    if method_name != "__init__":
                        class_methods[class_id].append(component_id)
        
        # Add method dependencies to their classes
        for class_id, method_ids in class_methods.items():
            if class_id in self.components:
                class_component = self.components[class_id]
                for method_id in method_ids:
                    class_component.depends_on.add(method_id)

    def save_dependency_graph(self, output_path: str):
        """Save the dependency graph to a JSON file."""
        # Convert to serializable format
        serializable_components = {
            comp_id: component.to_dict()
            for comp_id, component in self.components.items()
        }
        
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serializable_components, f, indent=2)
        