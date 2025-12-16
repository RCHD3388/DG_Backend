import os
import datetime
from typing import List, Optional, Set, Tuple

# Import yang sudah ada (sesuai kode Anda)
from app.schemas.models.code_component_schema import CodeComponent
from app.services.code_component_service import get_hydrated_components_for_record
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
from app.core.config import EVALUATION_RESULTS_DIR 

# Konfigurasi Repository (Tetap sama)
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
    
    "Dexter_C1": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\dexter-main\\dexter-main",
    "DMazeRunner_C1": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\dMazeRunner-master\\dMazeRunner-master",
    "Nanochat_1": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\nanochat-master\\nanochat-master",
    "Nanochat_2": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\nanochat-master\\nanochat-master",
    "Nanochat_3": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\nanochat-master\\nanochat-master",
    
    "M_AutoNUS": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\AutoNUS\\anus",
    "M_Vlrdev": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\vlrdevapi-main\\vlrdevapi-main",
    "M_RPAP": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\RPA-Python-master\\RPA-Python-master",
    
    "DP_Test": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\LabTry\\DemoProject"
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
    
    "Dexter_C1": "526f0351-a43b-4444-8166-eb0e52290a69",
    "DMazeRunner_C1": "30ec627b-61e4-4d8b-a314-b09a4de18016",
    "Nanochat_1": "d2f42775-f357-4c6b-adff-c59f5b3b2367",
    "Nanochat_2": "d57bbb72-4dd6-4e78-8e6e-7e93e576ca95",
    
    "M_AutoNUS": "55f7c95d-1618-4235-80a6-4765d6f5bbb4",
    "M_Vlrdev": "6b43c70a-e878-44c2-ab55-8b919116bcc6",
    "M_RPAP": "524c661a-b3a8-4fd0-ab5e-f2d22a32eeb1",
    
    # "DP_Test": "36d83f09-c0c9-483f-87e9-5210a4944a48",
    "DP_Test": "b21fecc1-970a-4045-b75b-1a3845e16a7f"
}

# Setup Direktori
evaluation_results_dir = EVALUATION_RESULTS_DIR
evaluation_results_dir.mkdir(exist_ok=True, parents=True)
# REPORT_FILE_PATH = os.path.join(evaluation_results_dir, "time_usage_mistral_report.txt")
REPORT_FILE_PATH = os.path.join(evaluation_results_dir, "time_usage_dp_test.txt")

# --- HELPER: Format Waktu ---
def format_duration(seconds: float) -> str:
    """Mengubah detik (float) menjadi string format hh:mm:ss"""
    if seconds is None:
        return "00:00:00"
    
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

# --- FUNGSI UTAMA: Process Count ---
def process_count(
    repository_name: str, 
    excluded_components: Set[str] = set(),
    prior_duration: float = 0.0,  # Akumulasi waktu dari batch sebelumnya
    prior_count: int = 0          # Akumulasi jumlah komponen dari batch sebelumnya
) -> Tuple[Set[str], float, int]: # Mengembalikan (IDs, TotalTime, TotalCount)
    
    # 1. Persiapan Data
    eval_project_root_path = testing_repository_root_path[repository_name]
    eval_record_code = testing_repository_record_code[repository_name]
    
    print(f"Processing extraction for: {repository_name}...")

    components = get_hydrated_components_for_record(
        root_folder_path=eval_project_root_path,
        record_code=eval_record_code
    )
    
    # Total komponen di repo saat ini (hanya untuk info)
    current_repo_total_components = len(components)
    
    # 3. Kumpulkan Data Waktu Checkpoint (Cumulative Time)
    checkpoint_data = []
    processed_components_ids = set() # ID yang ditemukan di batch ini (untuk exclude next batch)
    
    # Masukkan juga ID yang sudah di-exclude sebelumnya agar akumulatif
    all_processed_ids = set(excluded_components) 
    
    for comp in components:
        # Skip jika ada di exclude list (artinya sudah diproses di batch sebelumnya)
        if comp.id in excluded_components:
            continue
            
        try:
            final_state = comp.docgen_final_state
            if (final_state and 
                'time_used' in final_state and 
                'execution_time' in final_state['time_used']):
                
                seconds = final_state['time_used']['execution_time'].get('seconds')
                
                if seconds is not None:
                    checkpoint_data.append((float(seconds), comp.id))
                    processed_components_ids.add(comp.id)
                    all_processed_ids.add(comp.id)
        except Exception:
            pass 

    # 4. Hitung Durasi Individual untuk BATCH INI SAJA
    checkpoint_data.sort(key=lambda x: x[0])
    current_batch_durations = [] 
    
    if checkpoint_data:
        # Asumsi komponen pertama batch ini dimulai dari 0 relatif terhadap batch ini
        current_batch_durations.append(checkpoint_data[0][0]) 
        
        for i in range(1, len(checkpoint_data)):
            current_ckpt = checkpoint_data[i][0]
            prev_ckpt = checkpoint_data[i-1][0]
            duration = current_ckpt - prev_ckpt
            if duration >= 0:
                current_batch_durations.append(duration)

    # 5. Kalkulasi Statistik GABUNGAN (Previous + Current)
    
    # Hitung total waktu batch ini
    current_batch_total_time = sum(current_batch_durations)
    current_batch_count = len(current_batch_durations)
    
    # Gabungkan dengan data sebelumnya (Accumulated)
    grand_total_time = prior_duration + current_batch_total_time
    grand_total_count = prior_count + current_batch_count
    
    # Hitung Rata-rata Total
    avg_time_seconds = 0.0
    if grand_total_count > 0:
        avg_time_seconds = grand_total_time / grand_total_count
        
    # Estimasi Total (opsional, proyeksi jika repo penuh)
    # Kita gunakan grand_total_count sebagai total aktual yang sudah diproses
    
    # 6. Format Report String
    report_lines = []
    report_lines.append(f"Repository Batch: {repository_name}")
    report_lines.append("-" * 50)
    
    # Info Batch Ini
    report_lines.append(f"Current Batch Count     : {current_batch_count}")
    report_lines.append(f"Current Batch Time      : {format_duration(current_batch_total_time)}")
    
    # Info Akumulasi (Prior)
    if prior_count > 0:
        report_lines.append(f"Prior Excluded Count    : {prior_count}")
        report_lines.append(f"Prior Excluded Time     : {format_duration(prior_duration)}")
    
    report_lines.append("-" * 25)
    
    # Info Global (Hasil Akhir)
    report_lines.append(f"GRAND TOTAL Analyzed    : {grand_total_count}")
    report_lines.append(f"GRAND TOTAL Time        : {format_duration(grand_total_time)}")
    report_lines.append(f"AVERAGE Time / Component: {format_duration(avg_time_seconds)} ({avg_time_seconds:.2f}s)")
    
    report_lines.append("\n") 
    final_report_content = "\n".join(report_lines)

    # 7. Simpan ke File
    try:
        with open(REPORT_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(final_report_content)
        print(f"[SUCCESS] Report ditambahkan. Avg: {avg_time_seconds:.2f}s (Total: {grand_total_count} items)")
    except Exception as e:
        print(f"[ERROR] Gagal menulis report: {e}")
        
    # Return Data Akumulasi untuk batch berikutnya
    return all_processed_ids, grand_total_time, grand_total_count


if __name__ == "__main__":
    # Start mongo connection
    connect_to_mongo()
    print()
    
    # Reset file report
    if os.path.exists(REPORT_FILE_PATH):
        with open(REPORT_FILE_PATH, "w") as f:
            f.write(f"Time Usage Report (Cumulative Calculation) - {datetime.datetime.now()}\n")
            f.write("=" * 70 + "\n\n")

    # Contoh Penggunaan dengan Exclude (Misal RPAP diproses 2 tahap)
    # Tahap 1: Proses normal
    # ids, t, c = process_count("Nanochat_1")
    # ids, t, c = process_count("Nanochat_2", excluded_components=ids, prior_duration=t, prior_count=c)
    # ids, t, c = process_count("Nanochat", excluded_components=ids, prior_duration=t, prior_count=c)
    
    # ids, t, c = process_count("Dexter_C1")
    # ids, t, c = process_count("Dexter", excluded_components=ids, prior_duration=t, prior_count=c)
    
    # ids, t, c = process_count("DMazeRunner_C1")
    # ids, t, c = process_count("DMazeRunner", excluded_components=ids, prior_duration=t, prior_count=c)
    
    # processed_ids_auto = process_count("Dexter_C1")
    # processed_ids_auto = process_count("Dexter", excluded_components=processed_ids_auto)
    
    # processed_ids_auto = process_count("DMazeRunner_C1")
    # processed_ids_auto = process_count("DMazeRunner", excluded_components=processed_ids_auto)
    
    # process_count("Economix")
    # process_count("Vlrdev")
    # process_count("PowerPA")
    # process_count("ZmapSDK")
    # process_count("PyPDFForm")
    # process_count("RPAP")
    
    # Tahap 2: Contoh jika RPAP perlu dipanggil lagi dengan data baru, exclude yang lama
    # rpap_ids_batch1 = process_count("RPAP") 
    # process_count("RPAP", excluded_components=rpap_ids_batch1) # Contoh pemanggilan kedua
    
    # Untuk saat ini panggil sekali saja sesuai default
    
    # mistral 
    # ids, t, c = process_count("M_AutoNUS")
    # ids, t, c = process_count("M_RPAP")
    # ids, t, c = process_count("M_Vlrdev")
    
    ids, t, c = process_count("DP_Test")
    
    print("\nSemua proses selesai.")
    close_mongo_connection()