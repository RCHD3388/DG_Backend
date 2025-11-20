from typing import List, Dict
import json
import datetime
import re
import os
import time
import ast

from app.schemas.models.code_component_schema import CodeComponent
from app.services.code_component_service import get_hydrated_components_for_record, convert_dicts_to_code_components, map_components_by_id
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
from app.evaluator.completeness_eval import FunctionCompletenessEvaluator, ClassCompletenessEvaluator, save_completeness_report, CompletenessResultRow
from app.core.config import EVALUATION_RESULTS_DIR 

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

testing_repository_root_path = {
    "AutoNUS": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\AutoNUS\\anus", 
    "Economix": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\economix_server\\server-main",
    "Nanochat": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\nanochat-master\\nanochat-master",
    "Vlrdev": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\vlrdevapi-main\\vlrdevapi-main",
    "PowerPA": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\PowerPlayAssistant-main\\PowerPlayAssistant-main",
    "ZmapSDK": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\ZmapSDK-main\\ZmapSDK-main",
    "DMazeRunner": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\dMazeRunner-master\\dMazeRunner-master",
    "PyPDFForm": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\PyPDFForm-master\\PyPDFForm-master",
    "Dexter": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\dexter-main\\dexter-main",
    "RPAP": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\RPA-Python-master\\RPA-Python-master",
    
    "M_AutoNUS": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\AutoNUS\\anus",
    "M_Vlrdev": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\vlrdevapi-main\\vlrdevapi-main",
    "M_RPAP": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\RPA-Python-master\\RPA-Python-master"
}

testing_repository_record_code = {
    "AutoNUS": "4326d0d0-d41e-423e-b666-573a25f51c0d",
    "Economix": "116d3ef1-fcce-41f9-887f-17630d872219",
    "Nanochat" : "15dcbf1a-10b9-4d1e-afc0-6b0f239263ee",
    "Vlrdev": "4d954681-f678-43f6-9645-621990afca9d",
    "PowerPA": "cb9850ed-9d21-48a0-b6c4-40926295d47b",
    "ZmapSDK": "8b313e9f-31d3-4c7d-aad7-cf21d0cff991",
    "DMazeRunner": "66d6e69a-da43-4618-b715-aaaedfddee16",
    "PyPDFForm": "f18be374-49a0-4245-a750-67f2ea88a54b",
    "Dexter": "8e425e7f-105d-423f-bf51-10c3c7e8e074",
    "RPAP": "632a3373-663a-4b41-bfe7-ea7f597a84f0",
    
    "M_AutoNUS": "55f7c95d-1618-4235-80a6-4765d6f5bbb4",
    "M_Vlrdev": "6b43c70a-e878-44c2-ab55-8b919116bcc6",
    "M_RPAP": "524c661a-b3a8-4fd0-ab5e-f2d22a32eeb1"
}

api_keys_list = [
    "AIzaSyB3ePXqNh86z_qFuqCDnHnlR3ctSbY7uYE", # tikno
    "AIzaSyDjLZu3oY0JnZOBO7MkI4_ukWo1P-WkzUI", #eval08
    "AIzaSyCcw6MiszvalIwPKFPbALJIP1negIsBQfo", # tikno2
    "AIzaSyAPcsBEtG9FkvNtB3syUN_cj0nBbofX9a4", #tikno3
    "AIzaSyDrmEr2KLko7qcer21CT0f-WeDmx1yVoAk", #tikno4
]

# api_keys_list = [
#     "AIzaSyA_wj5YOMNi2Rj9wV8sYnyxz3rqZZb_mYg", #richardraferguy DGProj
#     "AIzaSyC61y_8cUqSKAXWtkwlS7XW5wjj13oO9pw", #richard.r22@mhs.istts.ac.id DGProject
# ]

llm_list: List[ChatGoogleGenerativeAI] = []

print(f"Mempersiapkan {len(api_keys_list)} koneksi LLM...")

for api_key in api_keys_list:
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",         
            google_api_key=api_key,   
            temperature=0.0           
        )
        
        llm_list.append(llm)
        print(f"Berhasil membuat koneksi untuk key ...{api_key[-4:]}")

    except Exception as e:
        print(f"Gagal membuat koneksi untuk key ...{api_key[-4:]}: {e}")

print(f"\nTotal koneksi LLM yang berhasil dibuat: {len(llm_list)}")


def extract_components_from_docstring(
    docstring: str, 
    model: BaseChatModel  # <-- REVISI: 'model' sekarang menjadi parameter
) -> List[str]:
    
    # --- REVISI: Definisikan Prompt Template (Gaya LangChain) ---
    prompt_template = ChatPromptTemplate.from_template(
        """
        Please extract all the non-common (very likely to be newly-defined in the repository) code components (classes, methods, functions) mentioned in 
        the following documentation. 

        Ignore the example part of the documentation if it exists (the code component you extract should not come from the example code).
        
        For example, "List", "Pandas" is a very common class and library in Python, so it should not be included.
        On the other hand, "InMemoryCacheTool" is not a common component, so it should be included.

        Return only a Python list of strings with the exact names.
        If no code components are mentioned, return an empty list.
        
        Documentation:
        ```
        {documentation}
        ```
        
        Format your response as a Python list wrapped in XML tags like this:
        <python_list>["ClassA", "method_b", "function_c"]</python_list>
        """
    )
    
    # --- REVISI: Tentukan Output Parser (hanya butuh string) ---
    output_parser = StrOutputParser()

    # --- REVISI: Buat Rantai (Chain) LCEL ---
    chain = prompt_template | model | output_parser
    
    try:
        # --- REVISI: Panggil rantai (chain) menggunakan .invoke() ---
        response_text = chain.invoke({"documentation": docstring})
        
        # --- LOGIKA PARSING ASLI ANDA (TIDAK DIUBAH) ---
        # Ekstrak list dari XML tags
        match = re.search(r'<python_list>(.*?)</python_list>', response_text, re.DOTALL)
        if match:
            list_str = match.group(1)
            try:
                # Safely evaluate the list string
                components = eval(list_str)
                if isinstance(components, list):
                    return components
            except:
                # If evaluation fails, extract strings manually
                components = re.findall(r'"([^"]*)"', list_str)
                return components
        
        # Fallback: try to extract using regex for regular list
        match = re.search(r'\[.*?\]', response_text, re.DOTALL)
        if match:
            list_str = match.group(0)
            try:
                # Safely evaluate the list string
                components = eval(list_str)
                if isinstance(components, list):
                    return components
            except:
                # If evaluation fails, extract strings manually
                components = re.findall(r'"([^"]*)"', list_str)
                return components
        
        # Fallback: try to find any mention of code looking elements
        components = re.findall(r'`([^`]+)`', docstring)
        return [c for c in components if not c.startswith('(') and not c.endswith(')')]
    
    except Exception as e:
        print(f"Error calling Gemini API via LangChain: {e}")
        
        components = re.findall(r'`([^`]+)`', docstring)
        return [c for c in components if not c.startswith('(') and not c.endswith(')')]

# --- HELPER 1: Visitor untuk Body (Raises & Warns) ---
class LocalBodyVisitor(ast.NodeVisitor):
    """
    Menjelajahi body fungsi untuk mencari Exception yang di-raise 
    dan Warning yang dimunculkan.
    """
    def __init__(self, target_word: str):
        self.target = target_word
        self.found = False

    def visit_Raise(self, node: ast.Raise):
        """Mendeteksi: raise ValueError(...)"""
        if node.exc:
            # Cek nama exception (misal: ValueError)
            # Menggunakan ast.unparse untuk menangani nama sederhana atau module.Name
            try:
                if self.target in ast.unparse(node.exc):
                    self.found = True
            except:
                pass # Fallback untuk python versi lama jika unparse gagal
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Mendeteksi: warnings.warn(...)"""
        # Cek apakah ini pemanggilan warnings.warn
        is_warning = False
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == 'warn':
                # Cek apakah objectnya 'warnings' (bisa dikembangkan untuk alias)
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'warnings':
                    is_warning = True
        elif isinstance(node.func, ast.Name) and node.func.id == 'warn':
             # Asumsi 'warn' diimport langsung
             is_warning = True
        
        if is_warning:
            # Cek argumen pertama (pesan) atau argumen kedua (kategori warning)
            for arg in node.args:
                try:
                    if self.target in ast.unparse(arg):
                        self.found = True
                except:
                    pass
        
        self.generic_visit(node)

class ClassAttributeVisitor(ast.NodeVisitor):
    """
    Mencari atribut dalam class, baik itu Class Variable, 
    Instance Attribute (di __init__), atau Property.
    """
    def __init__(self, target_name: str):
        self.target = target_name
        self.found = False

    def visit_Assign(self, node: ast.Assign):
        """Mendeteksi Class Variable: my_var = ..."""
        # Hanya proses jika ini di level class (bukan di dalam method, kecuali dipanggil manual)
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == self.target:
                self.found = True
        # Kita tidak generic_visit ke dalam assign untuk efisiensi
    
    def visit_AnnAssign(self, node: ast.AnnAssign):
        """Mendeteksi Class Variable dengan Type Hint: my_var: int = ..."""
        if isinstance(node.target, ast.Name) and node.target.id == self.target:
            self.found = True

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """
        1. Mendeteksi Property (method dengan nama target & decorator @property)
        2. Masuk ke __init__ untuk cari self.target
        """
        # Cek 1: Apakah ini Property dengan nama yang sesuai?
        if node.name == self.target:
            for decorator in node.decorator_list:
                # Cek decorator @property
                if isinstance(decorator, ast.Name) and decorator.id == 'property':
                    self.found = True
                    return
        
        # Cek 2: Apakah ini __init__? Jika ya, cari self.target
        if node.name == '__init__':
            # Kita iterasi body __init__ secara manual untuk mencari assignment ke self
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        self._check_self_assignment(target)
                elif isinstance(stmt, ast.AnnAssign):
                    self._check_self_assignment(stmt.target)
                    
        # Kita tidak generic_visit ke dalam function lain untuk menghindari
        # false positive dari variabel lokal.

    def _check_self_assignment(self, target_node):
        """Helper untuk mengecek pattern: self.target = ..."""
        if isinstance(target_node, ast.Attribute):
            if target_node.attr == self.target:
                # Pastikan object-nya adalah 'self'
                if isinstance(target_node.value, ast.Name) and target_node.value.id == 'self':
                    self.found = True

# --- HELPER 2: Pengecekan Signature (Parameter & Return) ---
def _check_local_signature(node: ast.AST, mentioned: str) -> bool:
    """
    Memeriksa apakah 'mentioned' ada di parameter (nama/tipe/default) atau return type.
    """
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
        
    # 1. Cek Return Type Annotation
    if node.returns:
        try:
            if mentioned in ast.unparse(node.returns):
                return True
        except:
            pass

    # 2. Cek Arguments (Args, Kwargs, Defaults)
    all_args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    if node.args.vararg: all_args.append(node.args.vararg)
    if node.args.kwarg: all_args.append(node.args.kwarg)
    
    for arg in all_args:
        # a. Cek Nama Parameter
        if mentioned == arg.arg:
            return True
            
        # b. Cek Tipe Parameter (Annotation)
        if arg.annotation:
            try:
                if mentioned in ast.unparse(arg.annotation):
                    return True
            except:
                pass

    # 3. Cek Default Values
    # (defaults berada di node.args.defaults dan node.args.kw_defaults)
    all_defaults = node.args.defaults + node.args.kw_defaults
    for default_val in all_defaults:
        if default_val is not None:
            try:
                # unparse akan mengubah node (misal Constant(10)) menjadi string "10"
                # atau Name(id='MyClass') menjadi "MyClass"
                if mentioned in ast.unparse(default_val):
                    return True
            except:
                pass
                
    return False

def check_existence_of_component(mentioned: str, 
                                 components: Dict[str, CodeComponent],
                                 current_component: CodeComponent = None):
    
    for comp_id, component in components.items():
        component.node
        if mentioned in comp_id.split(".")[-1]:
            return True
        
    if current_component and current_component.node:
        node = current_component.node
        
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # a. Signature (Param Name, Param Type, Return)
            if _check_local_signature(node, mentioned):
                return True
            # b. Body (Raises, Warns)
            body_visitor = LocalBodyVisitor(mentioned)
            body_visitor.visit(node)
            if body_visitor.found:
                return True
        
        # --- KASUS B: CLASS (REVISI) ---
        elif isinstance(node, ast.ClassDef):
            attr_visitor = ClassAttributeVisitor(mentioned)
            
            for body_item in node.body:
                attr_visitor.visit(body_item)
                
                if isinstance(body_item, ast.FunctionDef) and body_item.name == "__init__":
                    if _check_local_signature(body_item, mentioned):
                        return True
            if attr_visitor.found:
                return True
        
        if current_component.component_type == "method":
            
            parent_id = ".".join(current_component.id.split(".")[:-1])
            parent_component = components.get(parent_id)
            
            attr_visitor = ClassAttributeVisitor(mentioned)
            
            for body_item in parent_component.node.body:
                attr_visitor.visit(body_item)
                
            if attr_visitor.found:
                return True

    return False
    

def main(repository_name, type: str = None):
    llm_cur_index = 0
    
    # Get Components
    eval_project_root_path = testing_repository_root_path[repository_name]
    eval_record_code = testing_repository_record_code[repository_name]
    components = map_components_by_id(get_hydrated_components_for_record(
        root_folder_path=eval_project_root_path,
        record_code=eval_record_code
    ))
    total_components = len(components)
    
    # Setup Path
    evaluation_results_dir = EVALUATION_RESULTS_DIR
    evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    
    if type:
        evaluation_results_dir = evaluation_results_dir / f"{type}"
        evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    
    current_evaluation_results_dir = evaluation_results_dir / f"{repository_name}"
    current_evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    
    results = {}
    
    # --- Load Existing Report (Caching) ---
    report_filename = "truthfulness_report.json" # Menggunakan .json sesuai format data
    report_path = os.path.join(current_evaluation_results_dir, report_filename)
    existing_details = {}

    if os.path.exists(report_path):
        try:
            with open(report_path, "r") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, dict) and "details" in existing_data:
                    existing_details = existing_data["details"]
            print(f"[INFO] Ditemukan laporan sebelumnya. {len(existing_details)} komponen ter-load dari cache.")
        except Exception as e:
            print(f"[WARN] Gagal memuat laporan lama: {e}. Melanjutkan tanpa cache.")
    else:
        print(f"[INFO] Tidak ada laporan sebelumnya ditemukan. Memulai baru.")
    # ------------------------------------------------
    
    # EVALUASI SEMUA COMPONENTS
    check_counter = 0
    for comp_id, component in components.items():
        
        # -- LOG --
        print(f"Mengecek komponen {check_counter + 1}/{total_components}: {comp_id}")
        
        mentioned_component_names = []
        from_cache = False

        # --- 1.1 USING CACHE ---
        if comp_id in existing_details:
            cached_comp_data = existing_details[comp_id]
            
            # Cek validitas data cache (harus punya 'mentioned_components')
            if "mentioned_components" in cached_comp_data:
                # Ambil nama 'mentioned' dari list dictionary
                mentioned_component_names = [
                    item["mentioned"] for item in cached_comp_data["mentioned_components"]
                ]
                from_cache = True
                print(f"   -> [CACHE HIT] Menggunakan data lama ({len(mentioned_component_names)} mentions).")
        # -------------------------------------------
        
        # --- 1.2 USING LLM ---
        if not from_cache:
            llm_used_index = llm_cur_index % len(llm_list)
            model = llm_list[llm_used_index]
            llm_cur_index += 1
            
            json_data = component.docgen_final_state.get("final_state").get("documentation_json")
            docstring_text = json.dumps(json_data, indent=2)
            
            # 1. mendapatkan mentioned components dari component
            mentioned_component_names = extract_components_from_docstring(
                docstring=docstring_text, 
                model=model
            )
        # -------------------------------------------
        
        # 2. check mentioned component
        component_results = []
        for mentioned in mentioned_component_names:
            check_name = mentioned
            if "." in mentioned:
                check_name = mentioned.split(".")[-1]
            exist_status = check_existence_of_component(check_name, components, component)
            
            component_results.append({
                "mentioned": mentioned,
                "exist": exist_status
            })
         
        # FINAL RESULTS   
        final_results = {
            "mentioned_components": component_results,
            "total_mentions": len(mentioned_component_names),
            "total_exist": len([c for c in component_results if c["exist"]])
        }
        results[component.id] = final_results
        
        # -- LOG --
        check_counter += 1
        # time.sleep(4)
        
    # -- Final Report --
    total_mentions = sum(res["total_mentions"] for res in results.values())
    total_exist = sum(res["total_exist"] for res in results.values())
    
    final_report_data = {
        "score": (total_exist / total_mentions) * 100,
        "total_mentions": total_mentions,
        "total_exist": total_exist,
        "details": results  
    }
    
    # Simpan hasil ke dalam file JSON
    output_path = os.path.join(current_evaluation_results_dir, "truthfulness_report.json")
    with open(output_path, "w") as f:
        json.dump(final_report_data, f, indent=2)
    


if __name__ == "__main__":
    connect_to_mongo()
    print()
    
    # main("AutoNUS")
    # main("Dexter")
    # main("DMazeRunner")
    # main("Economix")
    # main("Nanochat")
    # main("PowerPA")
    # main("PyPDFForm")
    # main("Vlrdev")
    # main("ZmapSDK")
    
    # main("M_AutoNUS", "mistral")
    # main("M_Vlrdev", "mistral")
    main("M_RPAP", "mistral")
    
    
    print()
    close_mongo_connection()