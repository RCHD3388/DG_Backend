from typing import Dict, List, Any
from app.schemas.models.code_component_schema import CodeComponent

class InternalCodeParser:
    def __init__(self, repo_path: str, components: Dict[str, CodeComponent] = {}, dependency_graph: Dict[str, List[str]] = {}, pagerank_scores: Dict[str, float] = {}):
        self.repo_path = repo_path
        self.components = components
        self.dependency_graph = dependency_graph
        self.pagerank_scores = pagerank_scores
        self.fetched_class_skeletons = {}

    def find_dependencies(self, component_id: str) -> List[str]:
        """Mengembalikan daftar nama dependensi untuk sebuah komponen."""
        return list(self.dependency_graph.get(component_id, []))

    def find_called_by(self, component_id: str) -> List[str]:
        """Mengembalikan daftar lokasi di mana komponen dipanggil."""
        return list(self.components.get(component_id, {}).used_by)
    
    def find_pagerank_scores(self) -> Dict[str, float]:
        """Mengembalikan skor PageRank."""
        return self.pagerank_scores
    
    def get_component_by_id(self, component_id: str) -> CodeComponent:
        """Mengembalikan komponen."""
        return self.components.get(component_id, {})
    
    def get_component_docstring(self, component_id: str) -> str:
        """Mengembalikan daftar docstring dari semua komponen."""
        return self.components.get(component_id, {}).generated_doc
    
    def get_component_source_code(self, component_id: str) -> str:
        """Mengembalikan daftar kode sumber dari semua komponen."""
        return self.components.get(component_id, {}).source_code
    
    def get_class_skeleton(self, current_component: CodeComponent) -> str:
        """Mengembalikan Snipet class context"""
        
        if current_component.component_type == "class":
            
            # 1. Get ID (class, class_init)
            class_id = current_component.id
            class_init_id = f"{class_id}.__init__"
            
            # 2. Get component (class, class_init)
            class_component = self.components.get(class_id, {})
            class_init_component = self.components.get(class_init_id, {})
            
            # 3. CHECK if fetched
            if class_id in self.fetched_class_skeletons:
                return self.fetched_class_skeletons.get(class_id)
            
            # 4a. Setup file path - startline - endline
            file_path = class_component.file_path
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            start_line = class_component.start_line
            end_line = class_init_component.end_line
            
            # 4b. Get segment
            lines = source.splitlines()
            segment_lines = lines[start_line - 1:end_line]
            class_sekeleton_code = "\n".join(segment_lines)
            
            # 4c. Save to internal parser
            self.fetched_class_skeletons[class_id] = class_sekeleton_code
            
            # 5. Return
            return class_sekeleton_code
        
        return ""
    
    def find_called_by_snippet(self, component_id: str, max_used_by_samples: int) -> list:
        """Mengembalikan daftar kode sumber dari used by komponen."""
        current_component = self.components.get(component_id, {})
        called_by = current_component.used_by
        
        # 1. Filter called by IF method
        if current_component.component_type == "method":
            called_by = self.filter_method_used_by_component(component_id, called_by)
        
        # get component length
        def get_component_length(caller_id: str) -> int:
            """Helper function untuk mendapatkan panjang komponen dalam baris."""
            caller_component = self.components.get(caller_id, {})
            if caller_component and caller_component.end_line > 0:
                # Menambahkan 1 karena end_line - start_line bisa 0 untuk satu baris
                return caller_component.end_line - caller_component.start_line + 1
            return float('inf')
        
        # 2. Get sorted called by
        gathered_content = []
        sorted_called_by = sorted(called_by, key=get_component_length)
        
        # 3. Get snippet
        num_samples = min(len(sorted_called_by), max_used_by_samples)
        sample_called_by = sorted_called_by[:num_samples]
        
        for sample_id in sample_called_by:
            sample_component = self.components.get(sample_id, {})
            
            gathered_content.append({
                "id": sample_id,
                "component_type": sample_component.component_type,
                "snippet": self.get_class_skeleton(sample_component) if sample_component.component_type == "class" else self.get_component_source_code(sample_id)
            })
        
        return gathered_content
    
    def find_class_prefix_for_method(self, component_id: str):
        parts = component_id.split('.')
        return ".".join(parts[:-1])
    
    def filter_method_used_by_component(self, method_id: str, called_by: List[str]) -> List[str]:
        """Mengembalikan daftar kode filtered used by komponen."""
        
        class_id_prefix = self.find_class_prefix_for_method(method_id)
        
        filtered_list = []
        for caller_id in called_by:
            # 2. Cek apakah pemanggil berasal dari kelas yang sama
            #    Kita cek jika caller_id dimulai dengan prefix kelas yang sama dan diikuti oleh '.'
            #    Ini untuk memastikan kita tidak salah memfilter 'MyClass' itu sendiri jika ia memanggil.
            
            if caller_id == class_id_prefix:
                print(f"[InternalCodeParser] Delete class dari method called by: '{caller_id}'")
                continue # Lewati (jangan tambahkan ke daftar baru)
            
            filtered_list.append(caller_id)
            
        return filtered_list