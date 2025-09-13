import ast
import importlib
import inspect
import logging
import builtins
import sys

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
    """Collects secondary import statements from Python code."""
    
    def __init__(self):
        self.imports = {}
        self.wildcard_modules = []
    
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports[name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        modname = node.module

        if modname is not None:
            for alias in node.names:
                if alias.name == "*":
                    self.wildcard_modules.append(modname)
                else:
                    name = alias.asname or alias.name
                    self.imports[name] = f"{modname}.{alias.name}" # Simpan sebagai 'modul.nama_asli'
        
        self.generic_visit(node)

class DependencyCollector(ast.NodeVisitor):
    """
    Collects dependencies between code components by analyzing
    attribute access, function calls, and class references.
    """
    
    def __init__(self, imports, wildcard_modules, current_module, repo_modules, repo_path):
        self.imports = imports
        self.wildcard_symbols = {}
        self.repo_path = repo_path
        self.path_changed = False
        self._solve_wildcard_symbol(wildcard_modules)

        self.current_module = current_module
        self.repo_modules = repo_modules
        self.dependencies = set()
        self._current_class = None

        # Track local variables defined in the current context
        self.local_variables = set()

        # Track local variables as aliases
        self.local_aliases = {}

        print(f"Imports: {self.imports}")
        print(f"Wildcard Symbols: {self.wildcard_symbols}\n")

    def _solve_wildcard_symbol(self, wildcard_modules):
        self._change_to_target_path_path(self.repo_path)
        for modname in wildcard_modules:
            print(f"Trying to import {modname}")
            try:
                mod = importlib.import_module(modname)
                print(f"mod {mod}")
                for sym in dir(mod):
                    if not sym.startswith("_") and (inspect.isfunction(getattr(mod, sym)) or \
                        inspect.isclass(getattr(mod, sym))):
                        self.wildcard_symbols[sym] = f"{modname}.{sym}"
            except Exception as e:
                print(f"Failed to import {modname}: {e}")
                pass
        self._return_to_original_path()
    
    # --- IMPORT PATH RESOLVER START ---
    def _change_to_target_path_path(self, path):
        if path not in sys.path:
            sys.path.insert(0, str(path))
            self.path_changed = True
    def _return_to_original_path(self):
        if self.path_changed:
            sys.path.remove(str(self.repo_path))
            self.path_changed = False
    # --- IMPORT PATH RESOLVER END ---

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
        self._add_dependency(node.id)
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        self._process_attribute(node)
        self.generic_visit(node)

    def _process_attribute(self, node: ast.Attribute):
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        fullname = ".".join(reversed(parts))
        self._add_dependency(fullname)

    def _add_dependency(self, name):
        """Add a potential dependency based on a name reference."""
        
        if name in BUILTIN_TYPES:
            return
        if name in EXCLUDED_NAMES:
            return
        if name in STANDARD_MODULES:
            return

        name_parts = name.split('.')
        resolved_path = None
        resolved_index = None

        # --- RESOLVE PATH START ---
        for i in range(len(name_parts), 0, -1):
            # Ambil 'i' bagian pertama dari list
            current_parts = name_parts[:i]
            sub_path = ".".join(current_parts)
            
            if sub_path in self.imports:
                resolved_index = i
                resolved_path = self.imports[sub_path]
                break
            elif sub_path in self.wildcard_symbols:
                resolved_index = i
                resolved_path = self.wildcard_symbols[sub_path]
                break

        parts = []
        if resolved_path:
            resolved_parts = resolved_path.split('.')
            if len(name.split('.')) > 1:
                parts = resolved_parts + name.split('.')[(resolved_index):]
            else:
                parts = resolved_parts # Jika name hanya 'fungsi_x'
        else:
            # Jika tidak ditemukan di `imports` atau `wildcard_symbols`, mungkin ini adalah nama modul tingkat atas atau simbol bawaan.
            parts = self.current_module.split('.') + name.split('.')

        print(f"\n[*] Found dependency: {name} -> {parts}")
        # --- RESOLVE PATH END ---
        
        if not parts:
            return
        
        # --- TRACE TRUE ORIGIN ---
        self._change_to_target_path_path(self.repo_path)
        
        self._return_to_original_path()

        self.dependencies.add(name)

