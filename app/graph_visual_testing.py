import os
from app.services.documentation_service import get_record_from_database, convert_dicts_to_code_components
from app.core.mongo_client import close_mongo_connection, connect_to_mongo
from app.services.docgen.graph_visualizer import GraphVisualizer
from app.core.config import GRAPH_VISUALIZATION_DIRECTORY

# Impor fungsi baru dan class CodeComponent
# (Sesuaikan path impor ini dengan struktur proyek Anda)
# from app.utils.converters import convert_dicts_to_code_components
# from app.models.code_component import CodeComponent 

def main():
    connect_to_mongo()
    # isi 17 : 7611c5bc-3eae-48a0-8218-0bdf3abf0893
    # isi 165 : 98e71f2c-8207-4a2a-98cf-7da7d1f9ad65
    record_code = "7611c5bc-3eae-48a0-8218-0bdf3abf0893"
    
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
    
    close_mongo_connection()
    
if __name__ == "__main__":
    main()