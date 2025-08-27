# app/api/routers/files.py

from pathlib import Path
import shutil
from typing import List

from starlette.responses import JSONResponse
from fastapi import APIRouter, File, UploadFile, HTTPException
from app.core.config import UPLOAD_DIRECTORY

# Router khusus untuk fungsionalitas terkait file
router = APIRouter(
    prefix="/files",        # Prefix baru -> /api/files
    tags=["Files"]          # Tag baru untuk dokumentasi Swagger
)

@router.post("/upload", status_code=201) # Path menjadi /upload -> /api/files/upload
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Menerima satu atau lebih file proyek dan menyimpannya untuk analisis.
    """
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True) # Pastikan direktori ada
    
    uploaded_file_paths = []
    for file in files:
        if not file.filename:
            continue # Lewati jika ada file tanpa nama

        file_location = UPLOAD_DIRECTORY / file.filename
        try:
            with file_location.open("wb") as file_object:
                shutil.copyfileobj(file.file, file_object)
            uploaded_file_paths.append(str(file_location))
            print(f"File '{file.filename}' berhasil disimpan di {file_location}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan file '{file.filename}': {e}")
        finally:
            file.file.close()

    if not uploaded_file_paths:
        raise HTTPException(status_code=400, detail="Tidak ada file yang valid untuk diunggah.")

    return {
        "message": f"Berhasil mengunggah {len(uploaded_file_paths)} file.",
        "uploaded_files": [Path(p).name for p in uploaded_file_paths]
    }

@router.get("/", status_code=200) # Path menjadi / -> /api/files/
async def get_all_uploaded_files():
    """
    Mengembalikan daftar metadata untuk semua file yang sudah diunggah.
    """
    files_data = []
    if not UPLOAD_DIRECTORY.exists():
        return JSONResponse(status_code=200, content={"files": []}) # Return empty if dir doesn't exist

    for file_path in UPLOAD_DIRECTORY.iterdir():
        if file_path.is_file():
            try:
                stat_info = file_path.stat()
                files_data.append({
                    "id": file_path.name,       # Menggunakan nama file sebagai ID (sesuai frontend)
                    "name": file_path.name,     # Nama asli file
                    "size": stat_info.st_size,  # Ukuran file dalam bytes
                    # "uploadDate": stat_info.st_ctime, # Waktu pembuatan file (timestamp)
                    # Jika perlu tanggal upload, simpan di database bersama ID unik
                })
            except Exception as e:
                print(f"Peringatan: Gagal mendapatkan informasi untuk file '{file_path.name}': {e}")
                # Opsional: bisa log error dan melanjutkan, atau raise HTTPException
    
    return JSONResponse(status_code=200, content={"files": files_data})


@router.delete("/{file_name}", status_code=200) # Path menjadi /{file_name} -> /api/files/{file_name}
async def delete_uploaded_file(file_name: str):
    """
    Menghapus file yang sudah diunggah berdasarkan nama file-nya.
    """
    file_path_to_delete = UPLOAD_DIRECTORY / file_name

    if not file_path_to_delete.exists():
        raise HTTPException(status_code=404, detail=f"File '{file_name}' tidak ditemukan.")
    
    if not file_path_to_delete.is_file():
        raise HTTPException(status_code=400, detail=f"'{file_name}' bukan merupakan file yang valid.")

    try:
        file_path_to_delete.unlink() # Menghapus file
        print(f"File '{file_name}' berhasil dihapus.")
        # Jika Anda memiliki database yang mencatat file, hapus entri dari database di sini
        return JSONResponse(status_code=200, content={"message": f"File '{file_name}' berhasil dihapus."})
    except OSError as e: # Tangani error OS seperti permission denied
        raise HTTPException(status_code=500, detail=f"Gagal menghapus file '{file_name}': {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat menghapus file '{file_name}': {e}")