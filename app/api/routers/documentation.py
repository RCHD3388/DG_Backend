from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.schemas.response_schema import StandardResponse
from app.schemas.response.documentation_schema import DocumentationSummary, DocumentationFull
from app.services.documentation_service import (
    get_all_documentations_from_db, 
    get_record_from_database
)

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