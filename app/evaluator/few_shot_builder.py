import textwrap
from typing import List, Dict
from app.schemas.models.code_component_schema import CodeComponent

from app.services.code_component_service import get_hydrated_components_for_record, map_components_by_id
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
from app.evaluator.completeness_eval import FunctionCompletenessEvaluator, ClassCompletenessEvaluator, save_completeness_report, CompletenessResultRow
from app.core.config import EVALUATION_RESULTS_DIR 
import datetime

def generate_numpy_docstring_full(doc_data: dict) -> str:
    """
    Mengonversi struktur data kamus lengkap menjadi string format Numpy Doc Style.

    Fungsi ini menangani semua bagian standar Numpy (Parameters, Returns, 
    Raises, Notes, Examples, dll.). 
    
    Jika nilai sebuah bagian adalah 'None' atau kosong dalam kamus input, 
    seluruh bagian tersebut (termasuk tajuknya) akan dilewatkan 
    dari output akhir.
    """
    
    parts = []

    # --- Fungsi Pembantu Internal ---

    def _add_section_simple_list(section_key: str, header: str):
        """ 
        Untuk: Raises, Warns, See Also
        Format:
        
        Header
        ------
        nama_item : deskripsi item
        """
        if item_list := doc_data.get(section_key):
            parts.append("")
            parts.append(header)
            parts.append("-" * len(header))
            for item in item_list:
                name = item.get("name", "")
                desc = item.get("description", "")
                # Format: nama : deskripsi
                parts.append(f"{name} : {desc}")

    def _add_section_complex_list(section_key: str, header: str):
        """ 
        Untuk: Parameters, Attributes
        Format:
        
        Header
        ------
        nama_item : tipe_item
            Deskripsi (dengan indentasi).
        """
        if item_list := doc_data.get(section_key):
            parts.append("")
            parts.append(header)
            parts.append("-" * len(header))
            for item in item_list:
                name = item.get("name", "")
                itype = item.get("type", "")
                desc = item.get("description", "")
                
                # Baris pertama: 'nama' atau 'nama : tipe'
                line = f"{name}"
                if itype:
                    line += f" : {itype}"
                parts.append(line)
                
                if desc:
                    # Deskripsi harus di-indent
                    # Bungkus teks (wrap) agar rapi, lalu beri indentasi
                    wrapped_desc = textwrap.fill(desc, width=75) # 79 total - 4 indent
                    indented_desc = textwrap.indent(wrapped_desc, "    ")
                    parts.append(indented_desc)

    def _add_section_return_list(section_key: str, header: str):
        """ 
        Untuk: Returns, Yields, Receives
        Format:
        
        Header
        ------
        [nama_opsional :] tipe
            Deskripsi (dengan indentasi).
        """
        if item_list := doc_data.get(section_key):
            parts.append("")
            parts.append(header)
            parts.append("-" * len(header))
            for item in item_list:
                name = item.get("name", "")
                rtype = item.get("type", "")
                desc = item.get("description", "")
                
                line = ""
                if name:
                    line += f"{name} : "
                if rtype:
                    line += rtype
                
                if line:
                    # Jika ada 'nama' atau 'tipe', tambahkan baris
                    parts.append(line.strip())
                    if desc:
                        # Deskripsi di-indent
                        wrapped_desc = textwrap.fill(desc, width=75)
                        indented_desc = textwrap.indent(wrapped_desc, "    ")
                        parts.append(indented_desc)
                elif desc:
                    # Jika hanya deskripsi, tidak perlu indentasi
                    parts.append(desc)

    def _add_section_free_text(section_key: str, header: str):
        """ 
        Untuk: Notes, Examples, Warnings
        Format:
        
        Header
        ------
        Teks bebas di bawahnya...
        """
        if text := doc_data.get(section_key):
            parts.append("")
            parts.append(header)
            parts.append("-" * len(header))
            parts.append(text)
    
    # --- Eksekusi Utama ---

    # 1. Ringkasan (Summaries)
    if short := doc_data.get("short_summary"):
        parts.append(short)
    
    if extended := doc_data.get("extended_summary"):
        if parts: parts.append("") # Tambah baris kosong jika ada ringkasan singkat
        parts.append(extended)

    # 2. Bagian Terstruktur (memanggil fungsi pembantu)
    _add_section_complex_list("parameters", "Parameters")
    _add_section_complex_list("attributes", "Attributes")
    
    _add_section_return_list("returns", "Returns")
    _add_section_return_list("yields", "Yields")
    _add_section_return_list("receives", "Receives")
    
    _add_section_simple_list("raises", "Raises")
    _add_section_simple_list("warns", "Warns")
    _add_section_free_text("warnings_section", "Warnings")
    
    _add_section_simple_list("see_also", "See Also")
    
    _add_section_free_text("notes", "Notes")
    _add_section_free_text("examples", "Examples")

    # Gabungkan semua bagian menjadi satu string
    return "\n".join(parts)


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
    "DMazeRunner": "66d6e69a-da43-4618-b715-aaaedfddee16"
}


def build_few_shot_prompt() -> str:
    """
    Memuat komponen dari database, memformat contoh few-shot yang dipilih,
    dan menyimpannya ke 'fewshot_data.txt'.
    """
    
    # Ganti dengan path dan fungsi Anda yang sebenarnya
    try:
        connect_to_mongo()
    except NameError:
        print("PERINGATAN: Fungsi `connect_to_mongo` tidak ditemukan. Lanjut tanpa koneksi (untuk demo).")
        
    print("Mendapatkan data komponen...")
    
    components: Dict[str, CodeComponent] = {}
    try:
        # Panggilan fungsi Anda yang sebenarnya
        components = map_components_by_id(get_hydrated_components_for_record(
             root_folder_path=testing_repository_root_path["AutoNUS"],
             record_code=testing_repository_record_code["AutoNUS"]
        ))
    except NameError:
        print("PERINGATAN: Fungsi `get_hydrated_components_for_record` tidak ditemukan.")
        print("ERROR: Tidak dapat memuat komponen. Keluar.")
        return ""

    if not components:
        print("ERROR: Tidak ada komponen yang dimuat dari database. Keluar.")
        return ""
        
    print(f"Berhasil memuat {len(components)} total komponen.")
    
    example_key = [
        "models.base.base_model.BaseModel",
        "tools.base.tool_result.ToolResult",
        "core.agent.tool_agent.ToolAgent",
        "core.memory.long_term.LongTermMemory",
        "tools.text.TextTool.execute",
        "core.agent.tool_agent.ToolAgent.load_tool",
        "core.orchestrator.AgentOrchestrator.list_agents"
    ]    
    
    print(f"Memproses {len(example_key)} contoh few-shot...")
    
    few_shot_examples = []
    
    for key in example_key:
        component = components.get(key)
        
        # Pengecekan 1: Pastikan komponen ada
        if not component:
            print(f"PERINGATAN: Komponen '{key}' tidak ditemukan. Dilewati.")
            continue
            
        # Pengecekan 2: Pastikan ada source code (INPUT)
        source_input = component.source_code
        if not source_input:
            print(f"PERINGATAN: `source_code` kosong untuk '{key}'. Dilewati.")
            continue
            
        # Pengecekan 3: Pastikan ada data docgen (OUTPUT)
        doc_data = component.docgen_final_state.get("final_state").get("documentation_json")
        if not doc_data:
            print(f"PERINGATAN: `docgen_final_state` kosong untuk '{key}'. Dilewati.")
            continue
            
        # 1. Dapatkan INPUT
        source_input_formatted = source_input.strip()
        
        # 2. Hasilkan OUTPUT
        docstring_output = generate_numpy_docstring_full(doc_data).strip()
        
        # 3. Format contoh
        example_str = (
            f"[INPUT]\n"
            f"{source_input_formatted}\n\n"
            f"[OUTPUT]\n"
            f'"""\n{docstring_output}\n"""'
        )
        few_shot_examples.append(example_str)
        print(f"  > Berhasil memproses: {key}")
        
    # 4. Tulis ke file
    output_filename = "fewshot_data.txt"
    
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            # Gabungkan setiap contoh dengan pemisah yang jelas
            f.write("\n\n---\n\n".join(few_shot_examples))
        
        print(f"\n✅ Berhasil! {len(few_shot_examples)} contoh telah disimpan ke '{output_filename}'.")
        
    except IOError as e:
        print(f"\n❌ ERROR: Gagal menulis ke file '{output_filename}': {e}")
    
    # 5. Tutup koneksi
    try:
        print("Menutup koneksi Mongo...")
        close_mongo_connection()
    except NameError:
        print("PERINGATAN: Fungsi `close_mongo_connection` tidak ditemukan.")
    
    return output_filename

def get_numpy_format() -> str:
    
    connect_to_mongo()
    
    components: Dict[str, CodeComponent] = {}
    components = map_components_by_id(get_hydrated_components_for_record(
        root_folder_path=testing_repository_root_path["AutoNUS"],
        record_code=testing_repository_record_code["AutoNUS"]
    ))
    
    example_key = [
        "core.memory.long_term.LongTermMemory.get_stats"
    ]    
    
    few_shot_examples = []
    
    for key in example_key:
        component = components.get(key)
        doc_data = component.docgen_final_state.get("final_state").get("documentation_json")
        docstring_output = generate_numpy_docstring_full(doc_data).strip()
        few_shot_examples.append(docstring_output)
        print(f"  > Berhasil memproses: {key}")
        
    # 4. Tulis ke file
    output_filename = "docstring_compare.txt"
    
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            # Gabungkan setiap contoh dengan pemisah yang jelas
            f.write("\n\n---\n\n".join(few_shot_examples))
        
        print(f"\n✅ Berhasil! {len(few_shot_examples)} contoh telah disimpan ke '{output_filename}'.")
        
    except IOError as e:
        print(f"\n❌ ERROR: Gagal menulis ke file '{output_filename}': {e}")
    
    close_mongo_connection()
    
    return output_filename


if __name__ == "__main__":
    get_numpy_format()