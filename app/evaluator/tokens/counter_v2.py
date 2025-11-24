import os
import datetime
from typing import Dict, Any

# Import yang sudah ada
from app.schemas.models.code_component_schema import CodeComponent
from app.services.code_component_service import get_hydrated_components_for_record
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
from app.core.config import EVALUATION_RESULTS_DIR 

# Konfigurasi Repository (Sama seperti sebelumnya)
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
    "RPAP": "D:\\ISTTS\\Semester_7\\TA\\Project_TA\\Evaluation\\extracted_projects\\RPA-Python-master\\RPA-Python-master"
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
    "RPAP": "632a3373-663a-4b41-bfe7-ea7f597a84f0"
}

def process_count(repository_name, global_accumulator: Dict[str, Any] = None):
    # ---------------------------------------------------------
    # KONFIGURASI HARGA & AGEN
    # ---------------------------------------------------------
    USD_TO_IDR = 16739
    PRICING = {
        "flash": {"input_price": 0.30, "output_price": 2.50},
        "pro":   {"input_price": 1.25, "output_price": 10.00}
    }
    AGENT_CONFIG = {
        "reader": "flash", "writer": "flash", "verifier": "flash", "searcher": "pro"
    }

    # ---------------------------------------------------------
    # SETUP PATH & CONNECTION
    # ---------------------------------------------------------
    eval_project_root_path = testing_repository_root_path[repository_name]
    eval_record_code = testing_repository_record_code[repository_name]
    
    print(f"Processing extraction for: {repository_name}...")

    components = get_hydrated_components_for_record(
        root_folder_path=eval_project_root_path,
        record_code=eval_record_code
    )
    
    evaluation_results_dir = EVALUATION_RESULTS_DIR
    evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    current_evaluation_results_dir = evaluation_results_dir / f"{repository_name}"
    current_evaluation_results_dir.mkdir(exist_ok=True, parents=True)
    
    # ---------------------------------------------------------
    # LOGIKA EKSTRAKSI DATA
    # ---------------------------------------------------------
    total_components = len(components)
    
    # Update Total Component Global
    if global_accumulator is not None:
        global_accumulator["total_components"] += total_components

    # Struktur Penyimpanan Data Lokal
    global_stats = {
        "reader":   {"calls": 0, "input": 0, "output": 0, "total": 0},
        "searcher": {"calls": 0, "input": 0, "output": 0, "total": 0},
        "writer":   {"calls": 0, "input": 0, "output": 0, "total": 0},
        "verifier": {"calls": 0, "input": 0, "output": 0, "total": 0},
        "grand_total": {"calls": 0, "input": 0, "output": 0, "total": 0}
    }
    
    call_distribution = {
        "reader": {}, "searcher": {}, "writer": {}, "verifier": {}
    }
    
    table_rows_detail = []

    for comp in components:
        final_state = comp.docgen_final_state if comp.docgen_final_state else {}
        usage_stats = final_state.get("usage_stats", {})
        agent_details = usage_stats.get("components", {})
        
        row_data = {"id": comp.id}
        comp_total_call = 0
        comp_total_tok = 0

        for agent_name in ["reader", "searcher", "writer", "verifier"]:
            agent_data = agent_details.get(agent_name, {})
            
            c_calls = agent_data.get("call_count", 0)
            c_input = agent_data.get("input_tokens", 0)
            c_output = agent_data.get("output_tokens", 0)
            c_total = agent_data.get("total_tokens", 0)

            # 1. Akumulasi Lokal
            global_stats[agent_name]["calls"]  += c_calls
            global_stats[agent_name]["input"]  += c_input
            global_stats[agent_name]["output"] += c_output
            global_stats[agent_name]["total"]  += c_total
            
            global_stats["grand_total"]["calls"]  += c_calls
            global_stats["grand_total"]["input"]  += c_input
            global_stats["grand_total"]["output"] += c_output
            global_stats["grand_total"]["total"]  += c_total

            comp_total_call += c_calls
            comp_total_tok += c_total
            
            row_data[agent_name] = f"{c_calls} x ({c_total})"

            # 2. Tracking Frekuensi Lokal
            if c_calls not in call_distribution[agent_name]:
                call_distribution[agent_name][c_calls] = 0
            call_distribution[agent_name][c_calls] += 1
            
            # 3. --- UPDATE GLOBAL ACCUMULATOR ---
            if global_accumulator is not None:
                if c_calls not in global_accumulator["distribution"][agent_name]:
                    global_accumulator["distribution"][agent_name][c_calls] = 0
                global_accumulator["distribution"][agent_name][c_calls] += 1

        row_data["total_call"] = str(comp_total_call)
        row_data["total_token"] = str(comp_total_tok)
        table_rows_detail.append(row_data)

    # ---------------------------------------------------------
    # PERHITUNGAN BIAYA & REPORT GENERATION (LOKAL)
    # ---------------------------------------------------------
    # ... (Bagian ini tetap sama, menghasilkan report per repo seperti sebelumnya) ...
    
    financial_report = []
    total_cost_usd_accumulated = 0.0

    for agent_name in ["reader", "searcher", "writer", "verifier"]:
        model_type = AGENT_CONFIG[agent_name]
        prices = PRICING[model_type]
        total_input = global_stats[agent_name]["input"]
        total_output = global_stats[agent_name]["output"]
        
        cost_input = (total_input / 1_000_000) * prices["input_price"]
        cost_output = (total_output / 1_000_000) * prices["output_price"]
        total_agent_cost = cost_input + cost_output
        total_cost_usd_accumulated += total_agent_cost
        
        financial_report.append({
            "agent": agent_name,
            "model": f"Gemini 2.5 {model_type.capitalize()}",
            "input_cnt": total_input,
            "output_cnt": total_output,
            "cost_usd": total_agent_cost,
            "cost_idr": total_agent_cost * USD_TO_IDR
        })

    # Generate Lines
    lines = []
    def fmt_num(n): return f"{n:,}"
    def fmt_dec(n): return f"{n:,.2f}"
    
    lines.append("=" * 100)
    lines.append(f"  ACCURATE USAGE & COST REPORT: {repository_name}")
    lines.append("=" * 100)
    # ... (Bagian Section 1 - 4 tetap sama) ...
    
    # --- SECTION 1: TOKEN BREAKDOWN ---
    lines.append(">>> SECTION 1: TOKEN BREAKDOWN")
    w_ag = 12; w_in = 15; w_out = 15; w_tot = 15; w_call = 12
    header_token = f"| {'AGENT':<{w_ag}} | {'INPUT TOKENS':>{w_in}} | {'OUTPUT TOKENS':>{w_out}} | {'TOTAL TOKENS':>{w_tot}} | {'CALLS':>{w_call}} |"
    lines.append("-" * len(header_token)); lines.append(header_token); lines.append("-" * len(header_token))
    for agent in ["reader", "searcher", "writer", "verifier"]:
        st = global_stats[agent]
        lines.append(f"| {agent.upper():<{w_ag}} | {fmt_num(st['input']):>{w_in}} | {fmt_num(st['output']):>{w_out}} | {fmt_num(st['total']):>{w_tot}} | {fmt_num(st['calls']):>{w_call}} |")
    lines.append("-" * len(header_token))
    
    # --- SECTION 2: FINANCIAL ---
    lines.append(""); lines.append(">>> SECTION 2: ESTIMATED COST")
    w_mod = 22; w_c_usd = 18; w_c_idr = 25
    header_fin = f"| {'AGENT (MODEL)':<{w_mod}} | {'COST (USD)':>{w_c_usd}} | {'COST (IDR)':>{w_c_idr}} |"
    lines.append("-" * len(header_fin)); lines.append(header_fin); lines.append("-" * len(header_fin))
    for item in financial_report:
        lines.append(f"| {item['agent'].title():<{w_mod}} | ${item['cost_usd']:>{w_c_usd-1},.5f} | Rp {item['cost_idr']:>{w_c_idr-3},.2f} |")
    lines.append("-" * len(header_fin))
    total_idr = total_cost_usd_accumulated * USD_TO_IDR
    lines.append(f"| {'GRAND TOTAL COST':<{w_mod}} | ${total_cost_usd_accumulated:>{w_c_usd-1},.5f} | Rp {total_idr:>{w_c_idr-3},.2f} |")
    lines.append("=" * len(header_fin)); lines.append("")

    # --- SECTION 5: CALL FREQUENCY DISTRIBUTION (LOKAL) ---
    lines.append(">>> SECTION 5: AGENT CALL FREQUENCY DISTRIBUTION (LOCAL)")
    for agent in ["reader", "searcher", "writer", "verifier"]:
        lines.append(f"--- DISTRIBUSI: {agent.upper()} ---")
        dist = call_distribution[agent]
        sorted_calls = sorted(dist.keys())
        w_cc = 15; w_comp_cnt = 20; w_pct = 15
        header_dist = f"| {'JML PANGGILAN':<{w_cc}} | {'JML KOMPONEN':<{w_comp_cnt}} | {'PERSENTASE':<{w_pct}} |"
        lines.append("-" * len(header_dist)); lines.append(header_dist); lines.append("-" * len(header_dist))
        for calls in sorted_calls:
            count = dist[calls]
            pct = (count / total_components) * 100 if total_components > 0 else 0
            lines.append(f"| {str(calls) + ' kali':<{w_cc}} | {fmt_num(count):<{w_comp_cnt}} | {fmt_dec(pct) + '%':<{w_pct}} |")
        lines.append("-" * len(header_dist)); lines.append("")

    report_path = current_evaluation_results_dir / "usage_report.txt"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Report saved: {report_path}")
    except Exception as e:
        print(f"Error saving report: {e}")

def generate_aggregate_report(global_accumulator):
    """
    Fungsi khusus untuk membuat laporan gabungan semua repository
    """
    total_comps_all = global_accumulator["total_components"]
    
    lines = []
    def fmt_num(n): return f"{n:,}"
    def fmt_dec(n): return f"{n:,.2f}"
    
    lines.append("=" * 100)
    lines.append(f"  AGGREGATE CALL FREQUENCY REPORT (ALL REPOSITORIES)")
    lines.append("=" * 100)
    lines.append(f"  Date             : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Total Repositories: 10") 
    lines.append(f"  Total Components  : {fmt_num(total_comps_all)}")
    lines.append("-" * 100)
    lines.append("")
    
    lines.append(">>> AGGREGATE AGENT CALL FREQUENCY DISTRIBUTION")
    lines.append("Ini adalah rekapitulasi dari seluruh repository yang telah diproses.")
    lines.append("")

    for agent in ["reader", "searcher", "writer", "verifier"]:
        lines.append(f"--- DISTRIBUSI GLOBAL: {agent.upper()} ---")
        
        dist = global_accumulator["distribution"][agent]
        sorted_calls = sorted(dist.keys())
        
        w_cc = 15
        w_comp_cnt = 20
        w_pct = 15
        
        header_dist = (
            f"| {'JML PANGGILAN':<{w_cc}} | "
            f"{'JML KOMPONEN':<{w_comp_cnt}} | "
            f"{'PERSENTASE':<{w_pct}} |"
        )
        
        lines.append("-" * len(header_dist))
        lines.append(header_dist)
        lines.append("-" * len(header_dist))
        
        for calls in sorted_calls:
            count = dist[calls]
            pct = (count / total_comps_all) * 100 if total_comps_all > 0 else 0
            lines.append(
                f"| {str(calls) + ' kali':<{w_cc}} | "
                f"{fmt_num(count):<{w_comp_cnt}} | "
                f"{fmt_dec(pct) + '%':<{w_pct}} |"
            )
        lines.append("-" * len(header_dist))
        lines.append("")

    # Simpan di Root Evaluation Folder
    output_path = EVALUATION_RESULTS_DIR / "aggregate_call_frequency.txt"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\n[SUCCESS] Aggregate Report saved to: {output_path}")
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan aggregate report: {e}")

if __name__ == "__main__":
    connect_to_mongo()
    print()
    
    # --- INISIALISASI AKUMULATOR GLOBAL ---
    GLOBAL_STATS_ACCUMULATOR = {
        "distribution": {
            "reader": {}, "searcher": {}, "writer": {}, "verifier": {}
        },
        "total_components": 0
    }
    
    # Proses dengan menyertakan akumulator
    process_count("AutoNUS", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("Economix", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("Nanochat", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("Vlrdev", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("PowerPA", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("ZmapSDK", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("DMazeRunner", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("PyPDFForm", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("Dexter", GLOBAL_STATS_ACCUMULATOR); print()
    process_count("RPAP", GLOBAL_STATS_ACCUMULATOR); print()
    
    # GENERATE GLOBAL REPORT DI AKHIR
    generate_aggregate_report(GLOBAL_STATS_ACCUMULATOR)
    
    print()
    close_mongo_connection()