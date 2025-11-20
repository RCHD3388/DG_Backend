import os
from app.services.documentation_service import get_record_from_database, convert_dicts_to_code_components
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
from app.services.docgen.graph_visualizer import GraphVisualizer
from app.core.config import GRAPH_VISUALIZATION_DIRECTORY

# Impor fungsi baru dan class CodeComponent
# (Sesuaikan path impor ini dengan struktur proyek Anda)
# from app.utils.converters import convert_dicts_to_code_components
# from app.models.code_component import CodeComponent 

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

def main(repository_name):
    
    record_code = testing_repository_record_code[repository_name]
    
    # 1. Ambil seluruh dokumen record dari MongoDB
    record_document = get_record_from_database(record_code=record_code)
    
    if record_document and "components" in record_document:
        # 2. Ambil list of dictionaries
        component_dicts = record_document["components"]
        
        # 3. Konversi list of dictionaries menjadi list of CodeComponent
        #    Menggunakan fungsi baru:
        list_of_code_components = convert_dicts_to_code_components(component_dicts)
        
        visualizer = GraphVisualizer(components=list_of_code_components)
    
        # Panggil method helper untuk menghasilkan semua graf
        output_path = GRAPH_VISUALIZATION_DIRECTORY / record_code
        visualizer.generate_all_graphs(output_path)
            
    else:
        print(f"Record dengan ID '{record_code}' tidak ditemukan atau tidak memiliki komponen.")
    
    
    
if __name__ == "__main__":
    connect_to_mongo()
    
    for repository_name in testing_repository_record_code.keys():
        main(repository_name)
    
    close_mongo_connection()