from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.schemas.response_schema import StandardResponse
from app.schemas.response.documentation_schema import DocumentationSummary, DocumentationFull
from app.services.documentation_service import (
    get_all_documentations_from_db, 
    get_record_from_database,
    convert_dicts_to_code_components
)
from app.schemas.response.analyze_schema import  GenerateResultResponse, GenerateResultRequest
from app.core.config import DOCUMENT_RESULTS_DIRECTORY
from app.services.document_format.docx_generator import DocxDocumentationGenerator, convert_docx_to_pdf
import os

router = APIRouter(
    prefix="/documentations",
    tags=["Documentation"]
)

@router.get(
    "/",
    response_model=StandardResponse[List[DocumentationSummary]],
    summary="Get All Documentation Summaries"
)
async def get_all_documentations():
    """
    Mengambil daftar semua hasil dokumentasi yang tersimpan di database.
    Endpoint ini mengembalikan data ringkas (summary) dari setiap dokumentasi.
    """
    try:
        documents = get_all_documentations_from_db()
        return StandardResponse(data=documents)
    except Exception as e:
        print(f"[ERROR] Gagal mengambil semua dokumentasi: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kesalahan internal saat mengambil data: {e}"
        )

@router.get(
    "/{doc_id}",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Get One Full Documentation by ID"
)
async def get_documentation_by_id(doc_id: str):
    """
    Mengambil satu data dokumentasi lengkap berdasarkan ID uniknya dari MongoDB.
    """
    try:
        # Gunakan fungsi yang diadaptasi dari yang Anda berikan
        document = get_record_from_database(doc_id, sidebar_mode=True)
        
        if document:
            return StandardResponse(data=document)
        else:
            # Jika 'None', berarti tidak ditemukan
            raise HTTPException(
                status_code=404,
                detail=f"Dokumentasi dengan ID '{doc_id}' tidak ditemukan."
            )
    except HTTPException as e:
        # Melempar kembali 404
        raise e
    except Exception as e:
        # Menangani error lain, misal format ID salah
        print(f"[ERROR] Gagal mengambil dokumentasi {doc_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kesalahan: {e}"
        )
        
@router.post(
    "/{process_id}/generate-result",
    response_model=StandardResponse[GenerateResultResponse],
    summary="Generate Downloadable Documentation Files"
)
async def generate_downloadable_result(process_id: str, body: GenerateResultRequest):
    
    print(process_id)
    record_doc = get_record_from_database(
        record_code=process_id, 
        sidebar_mode=False 
    )
    
    if not record_doc:
        raise HTTPException(status_code=404, detail=f"Process with ID '{process_id}' not found.")
    
    components = convert_dicts_to_code_components(record_doc['components'])
    
    components.sort(key=lambda x: (x.file_path, x.id))

    # Setup Output
    output_dir = os.path.join(str(DOCUMENT_RESULTS_DIRECTORY), process_id)
    os.makedirs(output_dir, exist_ok=True)
    
    # Nama file dengan label bahasa
    language = "id"
    lang_suffix = "ID" if language == "id" else "EN"
    docx_filename = f"Documentation_{lang_suffix}.docx"
    full_file_path = os.path.join(output_dir, docx_filename)

    # --- GENERATE ---
    generator = DocxDocumentationGenerator(
        project_name=f"Code Documentation", 
        language=language,
        use_table_format=True if body.mode == "table" else False
    )
    
    generator.add_title_page()
    generator.add_table_of_contents(components)
    for comp in components:
        generator.add_component_documentation(comp)
        
    generator.save(full_file_path)

    # Convert as PDF
    pdf_filename = docx_filename.replace(".docx", ".pdf")
    pdf_full_path = os.path.join(output_dir, pdf_filename)
    convert_docx_to_pdf(full_file_path, pdf_full_path)
    
    return StandardResponse(data=GenerateResultResponse(
        pdf_url=f"{process_id}/{pdf_filename}",
        docx_url=f"{process_id}/{docx_filename}"
    ))