from pydantic import BaseModel, Field
from typing import Dict, Any, List
import datetime

class DocumentationSummary(BaseModel):
    """
    Model Pydantic untuk data ringkas (summary).
    'id' akan dipetakan dari '_id' yang sudah diserialisasi.
    """
    id: str = Field(..., description="ID unik dokumentasi")
    name: str = Field(..., description="Nama proyek atau analisis")

class DocumentationFull(DocumentationSummary):
    """
    Model Pydantic untuk data lengkap, mewarisi dari summary
    dan menambahkan field konten.
    """
    # Contoh field tambahan, sesuaikan dengan struktur data Anda
    full_content: Dict[str, Any] = Field(..., description="Konten lengkap hasil dokumentasi")
    analysis_artifacts: List[str] = Field(default=[], description="Daftar file artifact (gambar, dll)")