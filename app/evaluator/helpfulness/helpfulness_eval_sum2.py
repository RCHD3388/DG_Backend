from typing import List, Dict
import json
import datetime
import re
import os
import time

from app.schemas.models.code_component_schema import CodeComponent
from app.services.code_component_service import get_hydrated_components_for_record, convert_dicts_to_code_components, map_components_by_id
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
from app.evaluator.helpfulness.helpfulness_summary import EvaluatorSummaryDokumentasi
from app.evaluator.helpfulness.helpfulness_description import EvaluatorDeskripsiDokumentasi
from app.evaluator.helpfulness.helpfulness_parameter import EvaluatorParameterDokumentasi
from app.core.config import EVALUATION_RESULTS_DIR 
from langchain_core.messages import HumanMessage, SystemMessage

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
}

# api_keys_list = [
#     "AIzaSyAk15nyhP0l_fCtJykak-sicHpcjAi73rQ", #rmh
#     "AIzaSyCMIYWCfDPUS96uiGDopbEX13LARvU51Co", #xg8
# ]

# api_keys_list = [
#     "AIzaSyAP_6gEXrGrSyRyMrGCs0UOsC_5nf3Ha50", #xg38 GemEvalTru
#     "AIzaSyBkaMjqhVfRtJf1MwerHFhkcP9l0BNJnbY", #rraferg33@gmail.com GeminiEvalTru
# ]


# api_keys_list = [
#     "AIzaSyDXx_7xwHT5Q3917MBIN51GebwYvtC5-Nw", #eval01
#     "AIzaSyASMF2dvtM8bKA4V3n3OFUfXqCEeeTe3Os", #eval06
# ]

# api_keys_list = [
#     "AIzaSyArOi2ZJto6q9kP0O2Zm6JcaP6mLgFmt_4", #ver05
#     "AIzaSyBm76jEgvaVu8GQldzfgL51BiKdFN675RA", #ver06
# ]

# api_keys_list = [
#     "AIzaSyAPcsBEtG9FkvNtB3syUN_cj0nBbofX9a4", #tikno3
#     "AIzaSyDrmEr2KLko7qcer21CT0f-WeDmx1yVoAk", #tikno4
#     "AIzaSyDH2j_VAvITzm0xJbmVSBnCodsOKDFDimg"
# ]

api_keys_list = [
    "AIzaSyDrS5GiBl-ljFSNp5xeRkPJcO00D1_f_fo", #searcher02
    "AIzaSyCbv5tW_b1U07IBBTdsMCCFpOBHxqdQjUo", #evalllm01 evaluationTA
    "AIzaSyDcq9VWA8JUhh75rnR3HUnvIvrFt9hqG4s",
    "AIzaSyDH2j_VAvITzm0xJbmVSBnCodsOKDFDimg"
]


llm_list: List[ChatGoogleGenerativeAI] = []

print(f"Mempersiapkan {len(api_keys_list)} koneksi LLM...")

for api_key in api_keys_list:
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",         
            google_api_key=api_key,   
            temperature=0.1           
        )
        
        llm_list.append(llm)
        print(f"Berhasil membuat koneksi untuk key ...{api_key[-4:]}")

    except Exception as e:
        print(f"Gagal membuat koneksi untuk key ...{api_key[-4:]}: {e}")

print(f"\nTotal koneksi LLM yang berhasil dibuat: {len(llm_list)}")
    

def main_eval_summary(repository_name, 
         summary_evaluator: EvaluatorSummaryDokumentasi,
):
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
    
    output_path = os.path.join(current_evaluation_results_dir, f"helpfulness_summary.json")
    
    results = {}
    
    if os.path.exists(output_path):
        try:
            with open(output_path, "r") as f:
                existing_data = json.load(f)
                # Ambil 'details' jika ada, jika tidak biarkan kosong
                results = existing_data.get("details", {})
            print(f"[INFO] Melanjutkan evaluasi. Memuat {len(results)} hasil sebelumnya")
        except Exception as e:
            print(f"[WARN] Gagal memuat file lama: {e}. Memulai evaluasi dari awal.")
    
    # EVALUASI SEMUA COMPONENTS
    check_counter = 0
    for comp_id, component in components.items():
        
        # -- LOG --
        if comp_id in results:
            print(f"Mengecek komponen {check_counter + 1}/{total_components}: {comp_id} -> [SKIPPED] Sudah dievaluasi.")
            check_counter += 1
            continue # Lanjut ke komponen berikutnya tanpa memanggil LLM
        print(f"Mengecek komponen {check_counter + 1}/{total_components}: {comp_id}")
        
        # SETUP. mendapatkan LLM yang digunakan
        llm_used_index = llm_cur_index % len(llm_list)
        model = llm_list[llm_used_index]
        llm_cur_index += 1
        
        json_data = component.docgen_final_state.get("final_state").get("documentation_json")
        docstring_text = json.dumps(json_data, indent=2)
        
        # -- EVALUASI --
        # E1. Buat prompt
        prompt = summary_evaluator.get_evaluation_prompt(component, docstring_text)
        messages = [
            SystemMessage(content="Anda adalah pakar evaluasi kualitas dokumentasi kode."),
            HumanMessage(content=prompt)
        ]
        
        try:
            # E2. Panggil LLM
            response_message = model.invoke(messages)
            response_text = response_message.content
            
            # E3. Parse LLM response
            score, suggestion = summary_evaluator.parse_llm_response(response_text)
            
            # E4. Simpan hasil
            results[comp_id] = {
                "score": score,
                "suggestion": suggestion,
                "component_type": component.component_type,
                "raw_response": response_text  # Opsional: simpan respon mentah untuk debug
            }
            print(f"   -> Skor: {score}/5")

        except Exception as e:
            print(f"   -> ERROR saat evaluasi {comp_id}: {e}")
            results[comp_id] = {
                "score": 0,
                "suggestion": f"Error during evaluation: {str(e)}",
                "component_type": component.component_type
            }
        
        # -- LOG --
        check_counter += 1
        time.sleep(4)
        
        # -- Final Report --
        total_score = sum(item['score'] for item in results.values())
        avg_score = total_score / len(results) if results else 0
        
        final_report_data = {
            "repository_name": repository_name,
            "average_summary_score": avg_score,
            "total_components": len(results),
            "details": results
        }
        
        # Simpan hasil ke dalam file JSON
        output_path = os.path.join(current_evaluation_results_dir, "helpfulness_summary.json")
        with open(output_path, "w") as f:
            json.dump(final_report_data, f, indent=2)
    
    print()
    close_mongo_connection()


def clean_summary_evaluation_results(
    file_path: str, 
    output_path: str,
    components: Dict[str, CodeComponent],
    repository_name: str
):
    print(f"\n[CLEANUP] Memulai pembersihan data evaluasi parameter di: {file_path}")
    evaluator = EvaluatorSummaryDokumentasi()
    
    if not os.path.exists(file_path):
        print(f"[CLEANUP ERROR] File tidak ditemukan: {file_path}")
        return

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[CLEANUP ERROR] Gagal membaca JSON: {e}")
        return

    original_details = data.get("details", {})
    original_count = len(original_details)
    
    new_details = {}
    skipped_count = 0
    
    # 2. Filter Data
    print(f"[CLEANUP] Memproses {original_count} entri...")
    
    for comp_id, eval_result in original_details.items():
        
        # Cek apakah komponen ada di map komponen kita
        if comp_id not in components:
            continue
        
        score, _ = evaluator.parse_llm_response(eval_result["raw_response"])
        eval_result['score'] = score 
        new_details[comp_id] = eval_result
            
    total_evaluated = len(new_details)
    total_score = sum(item['score'] for item in new_details.values())
    new_avg_score = total_score / total_evaluated if total_evaluated > 0 else 0
    
    # Perbarui struktur data
    print(skipped_count)
    new_final_data = {
        "repository_name": repository_name,
        "average_summary_score": new_avg_score,
        "total_components": len(components),
        "details": new_details
    }
    
    # 4. Simpan Ulang ke File
    try:
        with open(output_path, 'w') as f:
            json.dump(new_final_data, f, indent=2)
        print(f"[CLEANUP SUCCESS] Data berhasil diperbarui.")
        
    except Exception as e:
        print(f"[CLEANUP ERROR] Gagal menyimpan file baru: {e}")

def cleancing_data(repository_name):
    connect_to_mongo()
    print()
    
    eval_project_root_path = testing_repository_root_path[repository_name]
    eval_record_code = testing_repository_record_code[repository_name]
    components = map_components_by_id(get_hydrated_components_for_record(
        root_folder_path=eval_project_root_path,
        record_code=eval_record_code
    ))
    
    # Setup Path
    evaluation_results_dir = EVALUATION_RESULTS_DIR
    evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    current_evaluation_results_dir = evaluation_results_dir / f"{repository_name}"
    current_evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    
    file_path = os.path.join(current_evaluation_results_dir, f"helpfulness_summary.json")
    # output_path = os.path.join(current_evaluation_results_dir, f"helpfulness_sum.json")
    
    clean_summary_evaluation_results(file_path=file_path, output_path=file_path, components=components, repository_name=repository_name)
    
    print()
    close_mongo_connection()

if __name__ == "__main__":
    
    # cleancing_data("AutoNUS")
    
    summary_evaluator = EvaluatorSummaryDokumentasi()
    
    # main_eval_summary("Economix", summary_evaluator)
    # main_eval_summary("Vlrdev", summary_evaluator)
    # main_eval_summary("DMazeRunner", summary_evaluator)
    
    # main_eval_summary("PyPDFForm", summary_evaluator)
    main_eval_summary("Nanochat", summary_evaluator)
    # main_eval_summary("AutoNUS", summary_evaluator)
    
    
    # main_eval_summary("PowerPA", summary_evaluator)
    # main_eval_summary("ZmapSDK", summary_evaluator)
    # main_eval_summary("Dexter", summary_evaluator)
    # main_eval_summary("RPAP", summary_evaluator)
    