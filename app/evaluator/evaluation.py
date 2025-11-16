from typing import List
from app.schemas.models.code_component_schema import CodeComponent

from app.services.code_component_service import get_hydrated_components_for_record
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
from app.evaluator.completeness_eval import FunctionCompletenessEvaluator, ClassCompletenessEvaluator, save_completeness_report, CompletenessResultRow
from app.core.config import EVALUATION_RESULTS_DIR 
import datetime

testing_repository_root_path = {
    "AutoNUS": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\AutoNUS\\anus", 
    "Economix": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\economix_server\\server-main",
    "Nanochat": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\nanochat-master\\nanochat-master",
    "Vlrdev": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\vlrdevapi-main\\vlrdevapi-main",
    "PowerPA": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\PowerPlayAssistant-main\\PowerPlayAssistant-main",
    "ZmapSDK": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\ZmapSDK-main\\ZmapSDK-main",
    "DMazeRunner": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\dMazeRunner-master\\dMazeRunner-master"
}

testing_repository_record_code = {
    "AutoNUS": "4326d0d0-d41e-423e-b666-573a25f51c0d",
    "Economix": "116d3ef1-fcce-41f9-887f-17630d872219",
    "Nanochat" : "15dcbf1a-10b9-4d1e-afc0-6b0f239263ee",
    "Vlrdev": "4d954681-f678-43f6-9645-621990afca9d",
    "PowerPA": "cb9850ed-9d21-48a0-b6c4-40926295d47b",
    "ZmapSDK": "8b313e9f-31d3-4c7d-aad7-cf21d0cff991",
}

def evaluate_completeness(
    components: List[CodeComponent], 
    current_evaluation_results_dir: str
):
    """
    Mengevaluasi kelengkapan semua komponen dan menyimpan laporan
    berformat tabel ke file .txt.
    """
    
    function_evaluator = FunctionCompletenessEvaluator()
    class_evaluator = ClassCompletenessEvaluator() 
    
    all_results: List[CompletenessResultRow] = []
    
    for component in components:
        evaluation_score = 0.0
        
        # 1. FUNCTION / METHOD COMPLETENESS
        if component.component_type == "function" or component.component_type == "method":
            
            # 1. Jalankan evaluasi
            evaluation_score = function_evaluator.evaluate(component=component)
            
            # 2. Ambil state internal dari evaluator
            required_sections = function_evaluator.required_sections
            
            # 3. Hitung seksi yang hilang
            missing_sections = set()
            for section, is_required in function_evaluator.element_required.items():
                # Jika wajib ada, TAPI skornya (ditemukan) adalah False
                if is_required and not function_evaluator.element_scores[section]:
                    missing_sections.add(section)
                    
            # 4. Simpan hasil terstruktur
            result_row = CompletenessResultRow(
                component_id=component.id,
                component_type=component.component_type.capitalize(),
                score=evaluation_score,
                required=required_sections,
                missing=missing_sections
            )
            all_results.append(result_row)

        # --- REVISI 2: Isi logika untuk CLASS COMPLETENESS ---
        elif component.component_type == "class":
            
            # 1. Jalankan evaluasi
            evaluation_score = class_evaluator.evaluate(component=component)
            
            # 2. Ambil state internal dari evaluator
            required_sections = class_evaluator.required_sections
            
            # 3. Hitung seksi yang hilang
            missing_sections = set()
            for section, is_required in class_evaluator.element_required.items():
                if is_required and not class_evaluator.element_scores[section]:
                    missing_sections.add(section)
                    
            # 4. Simpan hasil terstruktur
            result_row = CompletenessResultRow(
                component_id=component.id,
                component_type=component.component_type.capitalize(),
                score=evaluation_score,
                required=required_sections,
                missing=missing_sections
            )
            all_results.append(result_row)
    
    
    if not all_results:
        print("[EVALUATOR] Tidak ada komponen yang dievaluasi.")
        return

    # --- REVISI: Hitung total dan teruskan ke save function ---
    total_components = len(all_results)
    total_score = sum(res.score for res in all_results)
    overall_score = total_score / total_components
    
    # (Mengganti 'save_completeness_report' menjadi '_save_completeness_report'
    # agar konsisten dengan definisi)
    save_completeness_report(
        all_results, 
        current_evaluation_results_dir,
        overall_score,
        total_components  # <-- REVISI: Teruskan argumen baru
    )
    
    return

def evaluate_truthfulness():
    return

def evaluation(repository_name):
    
    # mendapatkan ROOT PATH dan RECORD CODE dari project yang ingin dievaluasi
    eval_project_root_path = testing_repository_root_path[repository_name]
    eval_record_code = testing_repository_record_code[repository_name]
    
    components = get_hydrated_components_for_record(
        root_folder_path=eval_project_root_path,
        record_code=eval_record_code
    )
    
    evaluation_results_dir = EVALUATION_RESULTS_DIR
    evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    
    # setup results PATH
    current_date_time = datetime.datetime.now()
    # current_evaluation_results_dir = evaluation_results_dir / f"{repository_name}_{current_date_time.strftime('%d_%m_%y__%H_%M')}"
    current_evaluation_results_dir = evaluation_results_dir / f"{repository_name}"
    current_evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    
    # E1. evaluate COMPLETENESS
    evaluate_completeness(
        components=components, 
        current_evaluation_results_dir=current_evaluation_results_dir
    )
    
    # E2. evaluate TRUTHFULNESS
    
    
    return

if __name__ == "__main__":
    # start mongodb connection
    connect_to_mongo()
    print()
    
    evaluation("AutoNUS"); print()
    evaluation("Economix"); print()
    evaluation("Nanochat"); print()
    evaluation("Vlrdev"); print()
    evaluation("PowerPA"); print()
    evaluation("ZmapSDK"); print()
    # evaluation("DMazeRunner"); print()
    
    # close mongo connection
    print()
    close_mongo_connection()