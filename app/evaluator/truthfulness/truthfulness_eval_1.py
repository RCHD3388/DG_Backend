from typing import List, Dict
import json
import datetime
import re
import os
import time

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
    "Dexter": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\dexter-main\\dexter-main"
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
    "Dexter": "8e425e7f-105d-423f-bf51-10c3c7e8e074"
}

# api_keys_list = [
#     "AIzaSyAcK4MrAGuiH690XF-TO5TYygaQ3Pi528o", #searcheragent01
#     "AIzaSyC5QdJlc1uL2WxTIWO-8Z8lqfRMIGjuGko", #searcheragent02
# ]
api_keys_list = [
    "AIzaSyA_wj5YOMNi2Rj9wV8sYnyxz3rqZZb_mYg", #richardraferguy DGProj
    "AIzaSyC61y_8cUqSKAXWtkwlS7XW5wjj13oO9pw", #richard.r22@mhs.istts.ac.id DGProject
]

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

def check_existence_of_component(mentioned: str, components: Dict[str, CodeComponent]):
    
    exist = False
    for comp_id, component in components.items():
        if mentioned in comp_id.split(".")[-1]:
            exist = True
            break
        
    return exist
    

def main(repository_name):
    llm_cur_index = 0
    
    connect_to_mongo()
    print()
    
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
    current_evaluation_results_dir = evaluation_results_dir / f"{repository_name}"
    current_evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    
    results = {}
    
    # EVALUASI SEMUA COMPONENTS
    check_counter = 0
    for comp_id, component in components.items():
        
        # -- LOG --
        print(f"Mengecek komponen {check_counter + 1}/{total_components}: {comp_id}")
        
        # SETUP. mendapatkan LLM yang digunakan
        llm_used_index = llm_cur_index % len(llm_list)
        model = llm_list[llm_used_index]
        llm_cur_index += 1
        
        json_data = component.docgen_final_state.get("final_state").get("documentation_json")
        docstring_text = json.dumps(json_data, indent=2)
        
        # 1. mendapatkan mentioned components dari component
        mentioned_component = extract_components_from_docstring(
            docstring=docstring_text, 
            model=model
        )
        
        # 2. check mentioned component
        component_results = []
        for mentioned in mentioned_component:
            check_name = mentioned
            if "." in mentioned:
                check_name = mentioned.split(".")[-1]
            exist_status = check_existence_of_component(check_name, components)
            
            component_results.append({
                "mentioned": mentioned,
                "exist": exist_status
            })
         
        # FINAL RESULTS   
        final_results = {
            "mentioned_components": component_results,
            "total_mentions": len(mentioned_component),
            "total_exist": len([c for c in component_results if c["exist"]])
        }
        results[component.id] = final_results
        
        # -- LOG --
        check_counter += 1
        time.sleep(4)
        
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
    
    print()
    close_mongo_connection()


if __name__ == "__main__":
    # main("ZmapSDK")
    # main("Vlrdev")
    main("DMazeRunner")