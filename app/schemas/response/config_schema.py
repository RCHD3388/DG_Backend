from pydantic import BaseModel
from typing import List

class ConfigListEntry(BaseModel):
    """Skema untuk satu entri dalam daftar konfigurasi."""
    name: str
    filename: str

class ConfigContent(BaseModel):
    """Skema untuk mengembalikan konten file YAML."""
    content: str

class ConfigUploadSuccess(BaseModel):
    """Skema respons sukses untuk upload."""
    filename: str
    message: str

class ConfigDeleteSuccess(BaseModel):
    """Skema respons sukses untuk delete."""
    filename: str
    message: str
