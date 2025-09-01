import ast
import logging
import builtins

logger = logging.getLogger(__name__)

# Built-in Python types and modules that should be excluded from dependencies
BUILTIN_TYPES = {name for name in dir(builtins)}
STANDARD_MODULES = {
    'abc', 'argparse', 'array', 'asyncio', 'base64', 'collections', 'copy', 
    'csv', 'datetime', 'enum', 'functools', 'glob', 'io', 'itertools', 
    'json', 'logging', 'math', 'os', 'pathlib', 'random', 're', 'shutil', 
    'string', 'sys', 'time', 'typing', 'uuid', 'warnings', 'xml'
}
EXCLUDED_NAMES = {'self', 'cls'}

class ImportCollector(ast.NodeVisitor):
    """Collects import statements from Python code."""
    
    def __init__(self):
        self.imports = set()
        self.from_imports = {}  # module -> [names]
        
    def visit_Import(self, node: ast.Import):
        """Process 'import x' statements."""
        for name in node.names:
            self.imports.add(name.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Process 'from x import y' statements."""
        if node.module is not None:
            module = node.module
            if module not in self.from_imports:
                self.from_imports[module] = []
            
            for name in node.names:
                if name.name != '*':
                    self.from_imports[module].append(name.name)
        
        self.generic_visit(node)

class DependencyCollector(ast.NodeVisitor):
    """
    Collects dependencies between code components by analyzing
    attribute access, function calls, and class references.
    """
    
    def __init__(self, imports, from_imports, current_module, repo_modules):
        self.imports = imports
        self.from_imports = from_imports
        self.current_module = current_module
        self.repo_modules = repo_modules
        self.dependencies = set()
        self._current_class = None
        # Track local variables defined in the current context
        self.local_variables = set()
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Process class definitions."""
        old_class = self._current_class
        self._current_class = node.name
        
        # Check for base classes dependencies
        for base in node.bases:
            if isinstance(base, ast.Name):
                # Simple name reference, could be an imported class
                self._add_dependency(base.id)
            elif isinstance(base, ast.Attribute):
                # Module.Class reference
                self._process_attribute(base)
        
        self.generic_visit(node)
        self._current_class = old_class
    
    def visit_Assign(self, node: ast.Assign):
        """Track local variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                # Add to local variables
                self.local_variables.add(target.id)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Process function calls."""
        if isinstance(node.func, ast.Name):
            # Direct function call
            self._add_dependency(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # Method call or module.function call
            self._process_attribute(node.func)
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name):
        """Process name references."""
        if isinstance(node.ctx, ast.Load):
            self._add_dependency(node.id)
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute):
        """Process attribute access."""
        self._process_attribute(node)
        self.generic_visit(node)
    
    def _process_attribute(self, node: ast.Attribute):
        """Process an attribute node to extract potential dependencies."""
        parts = []
        current = node
        
        # Traverse the attribute chain (e.g., module.submodule.Class.method)
        while isinstance(current, ast.Attribute):
            parts.insert(0, current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.insert(0, current.id)
            
            # Skip if the first part is a local variable
            if parts[0] in self.local_variables:
                return
                
            # Skip if the first part is in our excluded names
            if parts[0] in EXCLUDED_NAMES:
                return
                
            # Check if the first part is an imported module
            if parts[0] in self.imports:
                module_path = parts[0]
                # Skip standard library modules
                if module_path in STANDARD_MODULES:
                    return
                    
                # If it's a repo module, add as dependency
                if module_path in self.repo_modules:
                    if len(parts) > 1:
                        # Example: module.Class or module.function
                        self.dependencies.add(f"{module_path}.{parts[1]}")
            
            # Check from imports
            elif parts[0] in self.from_imports.keys():
                # Skip standard library modules
                if parts[0] in STANDARD_MODULES:
                    return
                    
                # Check if the name is in the imported names
                if len(parts) > 1 and parts[1] in self.from_imports[parts[0]]:
                    self.dependencies.add(f"{parts[0]}.{parts[1]}")
    
    def _add_dependency(self, name):
        """Add a potential dependency based on a name reference."""
        # Skip built-in types
        if name in BUILTIN_TYPES:
            return
        # Skip excluded names
        if name in EXCLUDED_NAMES:
            return
        # Skip standard library modules
        if name in STANDARD_MODULES:
            return
            
        # Skip local variables
        if name in self.local_variables:
            return
            
        # Check if name is directly imported from a module
        for module, imported_names in self.from_imports.items():
            if name in imported_names and module in self.repo_modules:
                self.dependencies.add(f"{module}.{name}")
                return
                
        # Check if name refers to a component in the current module
        local_component_id = f"{self.current_module}.{name}"
        self.dependencies.add(local_component_id)
