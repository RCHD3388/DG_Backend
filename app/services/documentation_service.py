from typing import Optional, Dict, Any, List
from app.core.mongo_client import get_db 
from app.schemas.models.code_component_schema import CodeComponent

def _serialize_mongo_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
    return doc

def get_all_documentations_from_db(
    collection: str = "documentation_results"
) -> List[Dict[str, Any]]:
    
    try:
        db = get_db()
        collection_obj = db[collection]
        
        projection = {
            "name": 1,
        }
        
        cursor = collection_obj.find({}, projection)
        
        return [_serialize_mongo_document(doc) for doc in cursor]
        
    except Exception as e:
        print(f"[DB ERROR] Gagal mengambil semua data: {e}")
        return []

def get_record_from_database(
    record_code: str, collection: str = "documentation_results",
    sidebar_mode: bool = False
    ) -> Optional[Dict[str, Any]]:
    
    # 1. Operasi Database (find_one)
    record_document: Optional[Dict[str, Any]] = None
    try:
        db = get_db()
        collection_obj = db[collection]
        print(collection_obj)
        record_document = collection_obj.find_one({"_id": record_code})
            
    except Exception as e:
        print(f"[DB ERROR] Gagal mengambil data record '{record_code}': {e}")
        return None
    
    if record_document:
        if not sidebar_mode:
            return record_document
        
        # 3.  Restrukturisasi untuk Sidebar (sidebar_mode = True)
        temp_record_document = record_document.copy()
        try:
            methods_to_process = []
            new_top_level_components = []
            
            original_components = record_document.get('components', [])
            if not original_components:
                return record_document
            
            # Pemisahan component code 
            for comp in original_components:
                if comp.get('component_type') == 'method':
                    methods_to_process.append(comp)
                else:
                    new_top_level_components.append(comp)
                    
            # 3.2. PASS 2: Buat lookup HANYA dari komponen top-level
            component_lookup = {}
            for comp in new_top_level_components:
                # Hanya proses jika ada ID
                comp_id = comp.get('id')
                if comp_id:
                    component_lookup[comp_id] = comp
                # Inisialisasi list method jika ini adalah class
                if comp.get('component_type') == 'class':
                    comp['method_components'] = []
            
            # 3.3. PASS 3: Proses dan pindahkan method
            # Iterasi HANYA pada list method yang sudah dipisah
            
            for method_comp in methods_to_process:
                method_id = method_comp.get('id', '')
                
                if '.' not in method_id:
                    new_top_level_components.append(method_comp)
                    continue
                    
                parent_id = ".".join(method_id.split('.')[:-1])
                
                parent_comp = component_lookup.get(parent_id)
                
                if parent_comp and parent_comp.get('component_type') == 'class':
                    # SUKSES: Parent adalah class, pindahkan method ke dalamnya
                    # (Kita memodifikasi 'parent_comp' via referensi)
                    parent_comp['method_components'].append(method_comp)
                else:
                    # GAGAL: Parent tidak ada atau bukan class.
                    # Tambahkan method ini sebagai top-level
                    new_top_level_components.append(method_comp)
            
            # 3.4. (Opsional tapi disarankan)
            for comp in new_top_level_components:
                if comp.get('component_type') == 'class' and comp.get('method_components'):
                    # Pastikan kita sorting list method yang benar
                    comp['method_components'].sort(
                        key=lambda m: m.get('start_line', 0)
                    )

            # 3.5. Ganti list components lama dengan yang baru (sudah difilter)
            record_document['components'] = new_top_level_components
            
            # 3.6. Kembalikan data yang sudah dimodifikasi
            return record_document
            
        except Exception as e:
            print(f"[RESTRUCTURE ERROR] Gagal merestrukturisasi data sidebar: {e}.")
            return temp_record_document
    else:
        # Ini bukan error, tapi datanya memang tidak ada
        print(f"[DB INFO] Record '{record_code}' tidak ditemukan di koleksi '{collection}'.")
        return None

def convert_dicts_to_code_components(component_dicts: List[Dict[str, Any]]) -> List[CodeComponent]:
    
    code_components_list: List[CodeComponent] = []
    
    if not isinstance(component_dicts, list):
        print(f"[CONVERSION ERROR] Input expected to be a list, but got {type(component_dicts)}")
        return code_components_list
        
    for data_dict in component_dicts:
        try:
            # Menggunakan static method .from_dict() yang sudah Anda buat
            component = CodeComponent.from_dict(data_dict)
            code_components_list.append(component)
            
        except KeyError as e:
            # Error ini terjadi jika salah satu field wajib (spt 'id' atau 'file_path') 
            # tidak ada di data dictionary dari DB.
            print(f"[CONVERSION ERROR] Gagal memproses komponen: Field wajib {e} tidak ada. Komponen dilewati.")
        except Exception as e:
            # Menangkap error tak terduga lainnya
            item_id = data_dict.get('id', 'ID_TIDAK_DIKETAHUI')
            print(f"[CONVERSION ERROR] Error saat memproses komponen '{item_id}': {e}. Komponen dilewati.")
            
    return code_components_list