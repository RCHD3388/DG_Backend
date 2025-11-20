from .docx_generator import DocxDocumentationGenerator, convert_docx_to_pdf
from app.core.config import DOCUMENT_RESULTS_DIRECTORY
from app.services.code_component_service import get_hydrated_components_for_record
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
import os

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

def main_generate_docs(repository_name: str, language: str = "id", use_table_format: bool = True):
    """
    Generate dokumen dengan pilihan bahasa.
    """
    connect_to_mongo()
    
    try:
        project_root_path = testing_repository_root_path[repository_name]
        record_code = testing_repository_record_code[repository_name]
        
        components = get_hydrated_components_for_record(
            root_folder_path=project_root_path,
            record_code=record_code
        )
        
        if not components:
            return

        # --- SORTING LOGIC UNTUK DAFTAR ISI ---
        # Kita ingin urutan: File Path -> Class -> Methods of that Class
        # 1. Sort by File Path
        # 2. Sort by ID (ini biasanya otomatis menaruh 'MyClass' sebelum 'MyClass.method')
        components.sort(key=lambda x: (x.file_path, x.id))

        # Setup Output
        output_dir = os.path.join(str(DOCUMENT_RESULTS_DIRECTORY), record_code)
        os.makedirs(output_dir, exist_ok=True)
        
        # Nama file dengan label bahasa
        lang_suffix = "ID" if language == "id" else "EN"
        docx_filename = f"{repository_name}_Documentation_{lang_suffix}.docx"
        full_file_path = os.path.join(output_dir, docx_filename)

        # --- GENERATE ---
        generator = DocxDocumentationGenerator(
            project_name=f"{repository_name} API", 
            language=language,
            use_table_format=use_table_format # <-- Teruskan parameter ini
        )
        
        generator.add_title_page()
        
        # Tambahkan Daftar Isi di awal
        generator.add_table_of_contents(components)
        
        # Tambahkan Konten
        for comp in components:
            generator.add_component_documentation(comp)
            
        generator.save(full_file_path)

        # Convert as PDF
        pdf_filename = docx_filename.replace(".docx", ".pdf")
        pdf_full_path = os.path.join(output_dir, pdf_filename)
        convert_docx_to_pdf(full_file_path, pdf_full_path)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        close_mongo_connection()

# --- Contoh Pemanggilan ---
if __name__ == "__main__":
    # Pastikan nama repo sesuai dengan key di testing_repository_root_path
    main_generate_docs("PowerPA", "id", use_table_format=False)
    # pass