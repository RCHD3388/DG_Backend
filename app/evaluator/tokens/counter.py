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

def process_count(repository_name):
    # ---------------------------------------------------------
    # KONFIGURASI HARGA (USD per 1 Juta Token)
    # ---------------------------------------------------------
    USD_TO_IDR = 16739
    
    PRICING = {
        "flash": {"input_price": 0.30, "output_price": 2.50},  # Reader, Writer, Verifier
        "pro":   {"input_price": 1.25, "output_price": 10.00}  # Searcher
    }
    
    # Mapping Agent ke Model
    AGENT_CONFIG = {
        "reader":   "flash",
        "writer":   "flash",
        "verifier": "flash",
        "searcher": "pro"
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
    # LOGIKA EKSTRAKSI DATA (PRECISION MODE)
    # ---------------------------------------------------------
    total_components = len(components)
    
    # Struktur Penyimpanan Data Global (Input & Output Dipisah)
    global_stats = {
        "reader":   {"calls": 0, "input": 0, "output": 0, "total": 0},
        "searcher": {"calls": 0, "input": 0, "output": 0, "total": 0},
        "writer":   {"calls": 0, "input": 0, "output": 0, "total": 0},
        "verifier": {"calls": 0, "input": 0, "output": 0, "total": 0},
        "grand_total": {"calls": 0, "input": 0, "output": 0, "total": 0}
    }
    
    table_rows_detail = []

    for comp in components:
        # Ambil data usage_stats
        final_state = comp.docgen_final_state if comp.docgen_final_state else {}
        usage_stats = final_state.get("usage_stats", {})
        agent_details = usage_stats.get("components", {})
        
        # Row data untuk tabel detail komponen
        row_data = {"id": comp.id}
        comp_total_call = 0
        comp_total_tok = 0

        # Loop per agent untuk akurasi
        for agent_name in ["reader", "searcher", "writer", "verifier"]:
            agent_data = agent_details.get(agent_name, {})
            
            # AMBIL DATA MENTAH (Input & Output terpisah)
            c_calls = agent_data.get("call_count", 0)
            c_input = agent_data.get("input_tokens", 0)
            c_output = agent_data.get("output_tokens", 0)
            c_total = agent_data.get("total_tokens", 0) # Biasanya c_input + c_output

            # Akumulasi Global per Agent
            global_stats[agent_name]["calls"]  += c_calls
            global_stats[agent_name]["input"]  += c_input
            global_stats[agent_name]["output"] += c_output
            global_stats[agent_name]["total"]  += c_total
            
            # Akumulasi Grand Total
            global_stats["grand_total"]["calls"]  += c_calls
            global_stats["grand_total"]["input"]  += c_input
            global_stats["grand_total"]["output"] += c_output
            global_stats["grand_total"]["total"]  += c_total

            # Akumulasi Lokal per Component (untuk tabel detail)
            comp_total_call += c_calls
            comp_total_tok += c_total
            
            # Format untuk kolom detail: "{calls} x ({total})"
            row_data[agent_name] = f"{c_calls} x ({c_total})"

        # Simpan data baris detail
        row_data["total_call"] = str(comp_total_call)
        row_data["total_token"] = str(comp_total_tok)
        table_rows_detail.append(row_data)

    # ---------------------------------------------------------
    # PERHITUNGAN BIAYA (AKURAT)
    # ---------------------------------------------------------
    financial_report = []
    total_cost_usd_accumulated = 0.0

    for agent_name in ["reader", "searcher", "writer", "verifier"]:
        model_type = AGENT_CONFIG[agent_name]
        prices = PRICING[model_type]
        
        # Ambil total input & output agent tersebut
        total_input = global_stats[agent_name]["input"]
        total_output = global_stats[agent_name]["output"]
        
        # RUMUS: (Token / 1,000,000) * Harga
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

    # ---------------------------------------------------------
    # GENERATE REPORT TEXT (FORMATTING RAPI)
    # ---------------------------------------------------------
    lines = []
    def fmt_num(n): return f"{n:,}"
    def fmt_dec(n): return f"{n:,.2f}"
    
    lines.append("=" * 100)
    lines.append(f"  ACCURATE USAGE & COST REPORT: {repository_name}")
    lines.append("=" * 100)
    lines.append(f"  Date             : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Components       : {total_components}")
    lines.append(f"  Exchange Rate    : 1 USD = {USD_TO_IDR:,} IDR")
    lines.append("-" * 100)
    lines.append("")

    # --- SECTION 1: TOKEN BREAKDOWN (INPUT vs OUTPUT) ---
    # Penting: Menampilkan input/output terpisah agar user percaya hitungannya benar
    lines.append(">>> SECTION 1: TOKEN BREAKDOWN (INPUT vs OUTPUT)")
    
    w_ag = 12
    w_in = 15
    w_out = 15
    w_tot = 15
    w_call = 12

    header_token = (
        f"| {'AGENT':<{w_ag}} | "
        f"{'INPUT TOKENS':>{w_in}} | "
        f"{'OUTPUT TOKENS':>{w_out}} | "
        f"{'TOTAL TOKENS':>{w_tot}} | "
        f"{'CALLS':>{w_call}} |"
    )
    lines.append("-" * len(header_token))
    lines.append(header_token)
    lines.append("-" * len(header_token))

    for agent in ["reader", "searcher", "writer", "verifier"]:
        st = global_stats[agent]
        lines.append(
            f"| {agent.upper():<{w_ag}} | "
            f"{fmt_num(st['input']):>{w_in}} | "
            f"{fmt_num(st['output']):>{w_out}} | "
            f"{fmt_num(st['total']):>{w_tot}} | "
            f"{fmt_num(st['calls']):>{w_call}} |"
        )
    
    lines.append("-" * len(header_token))
    gt = global_stats["grand_total"]
    lines.append(
        f"| {'TOTAL':<{w_ag}} | "
        f"{fmt_num(gt['input']):>{w_in}} | "
        f"{fmt_num(gt['output']):>{w_out}} | "
        f"{fmt_num(gt['total']):>{w_tot}} | "
        f"{fmt_num(gt['calls']):>{w_call}} |"
    )
    lines.append("=" * len(header_token))
    lines.append("")

    # --- SECTION 2: FINANCIAL REPORT (COST) ---
    lines.append(">>> SECTION 2: ESTIMATED COST (Based on Input/Output Split)")
    
    w_mod = 22
    w_c_usd = 18
    w_c_idr = 25
    
    header_fin = (
        f"| {'AGENT (MODEL)':<{w_mod}} | "
        f"{'COST (USD)':>{w_c_usd}} | "
        f"{'COST (IDR)':>{w_c_idr}} |"
    )
    lines.append("-" * len(header_fin))
    lines.append(header_fin)
    lines.append("-" * len(header_fin))

    for item in financial_report:
        lines.append(
            f"| {item['agent'].title() + ' (' + item['model'].split()[-1] + ')':<{w_mod}} | "
            f"${item['cost_usd']:>{w_c_usd-1},.5f} | " # 5 decimal for precision
            f"Rp {item['cost_idr']:>{w_c_idr-3},.2f} |"
        )

    lines.append("-" * len(header_fin))
    total_idr = total_cost_usd_accumulated * USD_TO_IDR
    lines.append(
        f"| {'GRAND TOTAL COST':<{w_mod}} | "
        f"${total_cost_usd_accumulated:>{w_c_usd-1},.5f} | "
        f"Rp {total_idr:>{w_c_idr-3},.2f} |"
    )
    lines.append("=" * len(header_fin))
    lines.append("")

    # --- SECTION 3: AVERAGES ---
    div = total_components if total_components > 0 else 1
    lines.append(">>> SECTION 3: AVERAGE CONSUMPTION PER COMPONENT")
    lines.append(f"  Average Total Tokens : {fmt_dec(gt['total']/div)}")
    lines.append(f"  Average Input Tokens : {fmt_dec(gt['input']/div)}")
    lines.append(f"  Average Output Tokens: {fmt_dec(gt['output']/div)}")
    lines.append(f"  Average Cost (IDR)   : Rp {total_idr/div:,.2f}")
    lines.append("")

    # --- SECTION 4: DETAILED LOGS ---
    lines.append(">>> SECTION 4: COMPONENT DETAILS")
    
    w_id = 60
    w_col = 22
    w_tot_s = 15
    
    header_det = (
        f"{'COMPONENT ID':<{w_id}} | "
        f"{'READER':<{w_col}} | "
        f"{'SEARCHER':<{w_col}} | "
        f"{'WRITER':<{w_col}} | "
        f"{'VERIFIER':<{w_col}} | "
        f"{'TOT CALL':<{w_tot_s}} | "
        f"{'TOT TOK':<{w_tot_s}}"
    )
    lines.append("-" * len(header_det))
    lines.append(header_det)
    lines.append("-" * len(header_det))

    for row in table_rows_detail:
        lines.append(
            f"{row['id']:<{w_id}} | "
            f"{row['reader']:<{w_col}} | "
            f"{row['searcher']:<{w_col}} | "
            f"{row['writer']:<{w_col}} | "
            f"{row['verifier']:<{w_col}} | "
            f"{row['total_call']:<{w_tot_s}} | "
            f"{row['total_token']:<{w_tot_s}}"
        )

    # Write File
    report_path = current_evaluation_results_dir / "usage_report.txt"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Report saved: {report_path}")
    except Exception as e:
        print(f"Error saving report: {e}")

    return


if __name__ == "__main__":
    # start mongodb connection
    connect_to_mongo()
    print()
    
    process_count("AutoNUS"); print()
    process_count("Economix"); print()
    process_count("Nanochat"); print()
    process_count("Vlrdev"); print()
    process_count("PowerPA"); print()
    process_count("ZmapSDK"); print()
    process_count("DMazeRunner"); print()
    process_count("PyPDFForm"); print()
    process_count("Dexter"); print()
    process_count("RPAP"); print()
    
    # close mongo connection
    print()
    close_mongo_connection()