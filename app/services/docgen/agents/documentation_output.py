from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict, Any

# Model pembantu untuk struktur yang berulang
class DocstringParameter(BaseModel):
    """Mendefinisikan satu parameter (di Parameters, Attributes, dll)"""
    name: str = Field(..., description="Nama parameter atau atribut.")
    type: str = Field(..., description="Tipe data dari parameter (misal: 'int', 'str', 'array_like').")
    description: str = Field(..., description="Penjelasan singkat parameter.")
    default: Optional[Any] = Field(None, description="Nilai default, jika ada.")

class DocstringReturn(BaseModel):
    """Mendefinisikan nilai kembali (di Returns atau Yields)"""
    name: Optional[str] = Field(None, description="Nama variabel yang dikembalikan (opsional).")
    type: str = Field(..., description="Tipe data dari nilai yang dikembalikan.")
    description: str = Field(..., description="Penjelasan nilai yang dikembalikan.")

class DocstringRaise(BaseModel):
    """Mendefinisikan error yang di-raise"""
    error: str = Field(..., description="Tipe error yang di-raise (misal: 'ValueError', 'LinAlgException').")
    description: str = Field(..., description="Kondisi di mana error ini di-raise.")

# --- SKEMA OUTPUT UTAMA (Baru) ---
# Ini menggantikan DocstringOutput Anda sebelumnya
class NumpyDocstring(BaseModel):
    """
    Skema terstruktur yang MENCERMINKAN standar NumPyDoc.
    LLM bertugas mengisi field-field ini, BUKAN menulis reST.
    """
    
    # 1. Summary
    short_summary: str = Field(..., description="Ringkasan satu baris, imperatif untuk fungsi, deskriptif untuk kelas.") 
    
    # 2. Deprecation (Opsional)
    deprecation_warning: Optional[str] = Field(None, description="Jika terdepresiasi, berikan pesan peringatan (misal: 'Deprecated since 1.6.0. Use new_func instead.').") 

    # 3. Extended Summary (Opsional)
    extended_summary: Optional[str] = Field(None, description="Paragraf deskripsi yang lebih panjang.") 
    
    # 4. Parameters (Untuk Fungsi/Metode)
    parameters: Optional[List[DocstringParameter]] = Field(None, description="Daftar parameter fungsi/metode.") 

    # --- Bagian Khusus Class ---
    attributes: Optional[List[DocstringParameter]] = Field(None, description="KHUSUS KELAS: Daftar atribut publik kelas.") 
    methods: Optional[List[Dict[str, str]]] = Field(None, description="KHUSUS KELAS: Daftar metode publik yang relevan (misal: [{'name': 'my_method(arg1)', 'description': '...'}])") 
    # ---------------------------

    # 5. Returns (Untuk Fungsi)
    returns: Optional[List[DocstringReturn]] = Field(None, description="Daftar nilai yang dikembalikan (untuk fungsi normal).") 
    
    # 6. Yields (Untuk Generator)
    yields: Optional[List[DocstringReturn]] = Field(None, description="Daftar nilai yang di-yield (untuk generator).") 

    # 7. Receives (Untuk Generator) (Opsional)
    receives: Optional[List[DocstringParameter]] = Field(None, description="Parameter yang diterima oleh metode .send() generator.") 

    # 8. Other Parameters (Opsional)
    other_parameters: Optional[List[DocstringParameter]] = Field(None, description="Daftar parameter yang jarang digunakan.") 

    # 9. Raises (Opsional)
    raises: Optional[List[DocstringRaise]] = Field(None, description="Daftar error yang mungkin di-raise.") 

    # 10. Warns (Opsional)
    warns: Optional[List[Dict[str, str]]] = Field(None, description="Daftar peringatan (misal: [{'warning': 'UserWarning', 'description': '...'}])") 

    # 11. Warnings (Opsional)
    warnings_section: Optional[str] = Field(None, description="Teks bebas untuk peringatan umum kepada pengguna.") 

    # 12. See Also (Opsional)
    see_also: Optional[List[Dict[str, str]]] = Field(None, description="Daftar fungsi/kelas terkait (misal: [{'name': 'numpy.mean', 'description': 'Weighted average.'}]).") 

    # 13. Notes (Opsional)
    notes: Optional[str] = Field(None, description="Teks bebas untuk catatan implementasi, algoritma, atau teori.") 

    # 14. References (Opsional)
    references: Optional[str] = Field(None, description="Teks bebas untuk sitasi literatur.") 

    # 15. Examples (Opsional)
    examples: Optional[str] = Field(None, description="Contoh kode penggunaan dalam format doctest (termasuk '>>> ').") 

    # Metadata Tambahan (dari skema Anda sebelumnya, ini bagus)
    keywords: List[str] = Field(..., description="A list of relevant keywords or tags for this component.")