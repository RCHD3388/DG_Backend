from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict, Any, Literal

# Model pembantu untuk struktur yang berulang
class DocstringParameter(BaseModel):
    """Mendefinisikan satu parameter (di Parameters, Attributes, dll)"""
    name: str = Field(..., description="Nama parameter atau atribut.")
    type: str = Field(..., description="Tipe data dari parameter (misal: 'int', 'str', 'None', dan lainnya).")
    description: str = Field(..., description="Penjelasan singkat parameter.")
    default: Optional[Any] = Field(None, description="Nilai default, jika ada.")

class DocstringReturn(BaseModel):
    """Mendefinisikan nilai kembali (di Returns atau Yields)"""
    type: str = Field(..., description="Tipe data dari nilai yang dikembalikan oleh Returns atau Yields.")
    description: str = Field(..., description="Penjelasan nilai yang dikembalikan.")

class DocstringRaise(BaseModel):
    """Mendefinisikan error yang di-raise"""
    error: str = Field(..., description="Tipe error yang di-raise (misal: 'ValueError', 'LinAlgException').")
    description: str = Field(..., description="Kondisi di mana error ini di-raise.")
    
class DocstringWarning(BaseModel):
    """Mendefinisikan error yang di-raise"""
    warning: str = Field(..., description="Tipe Warning yang di-raise (misal: 'DeprecationWarning', 'RuntimeWarning').")
    description: str = Field(..., description="Kondisi di mana warning ini di-raise.")
    
class DocstringSeeAlso(BaseModel):
    """Mendefinisikan error yang di-raise"""
    name: str = Field(..., description="Fungsi atau Class yang direferensikan (misal: 'core.Agent', 'core.service.file_service').")
    description: str = Field(..., description="Deskripsi singkat dari item yang direferensikan")

# --- SKEMA OUTPUT UTAMA (Baru) ---
# Ini menggantikan DocstringOutput Anda sebelumnya
class NumpyDocstring(BaseModel):
    """
    Skema terstruktur yang MENCERMINKAN standar NumPyDoc.
    LLM bertugas mengisi field-field ini, BUKAN menulis reST.
    """
    
    # 1. Summary
    short_summary: str = Field(..., description="Ringkasan satu baris, imperatif untuk fungsi, deskriptif untuk kelas.") 
    
    # 2. Extended Summary (Opsional)
    extended_summary: Optional[str] = Field(None, description="Paragraf deskripsi yang lebih panjang.") 
    
    # 3. Parameters (Untuk Fungsi/Metode)
    parameters: Optional[List[DocstringParameter]] = Field(None, description="Daftar semua parameter fungsi/metode.") 

    # 4. --- Bagian Khusus Class ---
    attributes: Optional[List[DocstringParameter]] = Field(None, description="KHUSUS KELAS: Daftar atribut publik kelas.") 
    # ---------------------------

    # 5. Returns (Untuk Fungsi)
    returns: Optional[List[DocstringReturn]] = Field(None, description="Daftar nilai yang dikembalikan (untuk fungsi normal).") 
    
    # 6. Yields (Untuk Generator)
    yields: Optional[List[DocstringReturn]] = Field(None, description="Daftar nilai yang di-yield (untuk generator).") 

    # 7. Receives (Untuk Generator) (Opsional)
    receives: Optional[List[DocstringParameter]] = Field(None, description="Parameter yang diterima oleh metode .send() generator.") 

    # 8. Raises (Opsional)
    raises: Optional[List[DocstringRaise]] = Field(None, description="Daftar error yang mungkin di-raise.") 

    # 9. Warns (Opsional)
    warns: Optional[List[DocstringWarning]] = Field(None, description="Daftar Warning (misal: [{'warning': 'UserWarning', 'description': '...'}])") 
    
    # 10. Warnings (Opsional)
    warnings_section: Optional[str] = Field(None, description="Teks bebas untuk peringatan umum kepada pengguna.")

    # 11. See Also (Opsional)
    see_also: Optional[List[DocstringSeeAlso]] = Field(None, description="Daftar fungsi/kelas terkait (misal: [{'name': 'core.Agent', 'description': '...'}]).") 

    # 12. Notes (Opsional)
    notes: Optional[str] = Field(None, description="Teks bebas untuk catatan implementasi, algoritma, atau teori. Hanya jika hal tersebut penting")  

    # 13. Examples (Opsional)
    examples: Optional[str] = Field(None, description="Contoh kode penggunaan dalam format doctest (termasuk '>>> ').") 
    
    
# READER AGENT OUTPUT
class ReaderOutput(BaseModel):
    """Skema output JSON untuk Reader."""
    
    info_need: bool = Field(
        ..., 
        description="True jika informasi tambahan (internal atau eksternal) diperlukan, False jika konteks saat ini cukup."
    )
    
    internal_expand: Optional[List[str]] = Field(
        default=None, 
        description="Daftar component ID internal yang perlu diexpand (Misal, 'main.core.main_agent.Agent.get_log'). Kosongkan jika tidak ada."
    )
    
    external_retrieval: Optional[List[str]] = Field(
        default=None,
        description="Daftar query pencarian eksternal (jika info_need true dan benar-benar diperlukan). Kosongkan jika tidak ada."
    )
    

# VERIFIER AGENT OUTPUT
class SectionCritique(BaseModel):
    """Kritik spesifik untuk satu bagian dari docstring."""
    section: str = Field(..., description="Bagian yang dievaluasi, misal: 'parameters', 'examples', 'short_summary'.")
    is_accurate: bool = Field(..., description="Apakah bagian ini akurat secara semantik berdasarkan kode?")
    critique: str = Field(..., description="Kritik spesifik. Tulis 'Akurat.' jika lolos, atau jelaskan kesalahannya jika gagal.")

class SingleCallVerificationReport(BaseModel):
    """Laporan verifikasi lengkap dari satu panggilan LLM."""
    critiques: List[SectionCritique] = Field(..., description="Daftar kritik untuk setiap bagian utama dokumentasi.")
    
    # --- PERUBAHAN DIMULAI DI SINI ---
    suggested_next_step: Literal["finished", "writer", "reader"] = Field(...,
        description="Keputusan strategis berdasarkan evaluasi. 'finished' (jika semua `is_accurate` true), 'writer' (jika perlu perbaikan konten), 'reader' (jika butuh konteks eksternal)."
    )
    suggestion_feedback: str = Field(...,
        description="Satu paragraf ringkas yang menjelaskan keputusan. Jika 'writer', jelaskan apa yang harus diperbaiki. Jika 'reader', jelaskan KONTEKS SPESIFIK apa yang harus dicari."
    )