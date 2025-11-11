# app/services/file_service.py

import asyncio
import shutil
from pathlib import Path
from typing import List
import os

from fastapi import UploadFile

# Import schema DTO (Data Transfer Object) yang akan dikembalikan
from app.schemas.response.file_schema import FileMetadata
# Import custom exceptions
from app.core.exceptions import FileNotFound, FileOperationError, InvalidFileNameError
# Import utilitas yang sudah Anda miliki
from app.utils.file_utils import clear_directory_contents
from app.utils.CustomLogger import CustomLogger

logger = CustomLogger("FileService")

class FileService:
    """
    Menangani semua logika bisnis terkait operasi file.
    Dirancang untuk 'dependency injection' dan 'separation of concerns'.
    """

    def __init__(self, upload_dir: Path, extracted_dir: Path):
        self.upload_dir = upload_dir
        self.extracted_dir = extracted_dir
        
        # Pastikan direktori utama ada saat service diinisialisasi
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _is_secure_filename(self, file_name: str) -> bool:
        """
        Memvalidasi nama file untuk mencegah path traversal.
        """
        if not file_name:
            return False
        if ".." in Path(file_name).parts:
            return False
        if Path(file_name).name != file_name:
            return False
        return True

    def _save_file_sync(self, file: UploadFile, destination: Path) -> None:
        """
        [SINKRON] Worker untuk menyimpan file. Dijalankan di thread pool.
        """
        try:
            with destination.open("wb") as file_object:
                shutil.copyfileobj(file.file, file_object)
        except Exception as e:
            raise FileOperationError("save", destination.name, str(e))
        finally:
            file.file.close()

    async def upload_files(self, files: List[UploadFile]) -> List[Path]:
        """
        [ASINKRON] Menyimpan daftar UploadFile ke disk.
        Menjalankan I/O blocking di thread pool.
        """
        saved_paths = []
        tasks = []
        for file in files:
            if not file.filename or not self._is_secure_filename(file.filename):
                logger.info_print(f"Skipping invalid or insecure file: {file.filename}")
                continue
                
            file_location = self.upload_dir / file.filename
            
            # Menjalankan fungsi I/O blocking di thread terpisah
            tasks.append(
                asyncio.to_thread(self._save_file_sync, file, file_location)
            )
            saved_paths.append(file_location)
        
        # Menunggu semua operasi simpan file selesai
        await asyncio.gather(*tasks)
        return saved_paths

    def _get_files_sync(self) -> List[FileMetadata]:
        """
        [SINKRON] Worker untuk mendaftar file di UPLOAD_DIRECTORY.
        """
        file_list = []
        if not self.upload_dir.exists():
            return []
            
        for file_path in self.upload_dir.iterdir():
            if file_path.is_file():
                try:
                    stat_info = file_path.stat()
                    file_list.append(
                        FileMetadata(
                            id=file_path.name,
                            name=file_path.name,
                            size=stat_info.st_size,
                        )
                    )
                except Exception as e:
                    # Log error tapi tetap lanjut
                    logger.info_print(f"Warning: Failed to get info for file '{file_path.name}': {e}")
        return file_list

    async def get_all_uploaded_files(self) -> List[FileMetadata]:
        """
        [ASINKRON] Mengambil metadata semua file yang diunggah.
        """
        return await asyncio.to_thread(self._get_files_sync)

    def _delete_file_sync(self, file_name: str) -> Path:
        """
        [SINKRON] Worker untuk menghapus file.
        """
        if not self._is_secure_filename(file_name):
            raise InvalidFileNameError(file_name)

        file_path = self.upload_dir / file_name

        if not file_path.exists():
            raise FileNotFound(file_name)
        
        if not file_path.is_file():
            # Jika ada file 'foo' dan direktori 'foo', ini mencegah penghapusan direktori
            raise InvalidFileNameError(f"'{file_name}' is not a valid file.")

        try:
            file_path.unlink()
            return file_path
        except Exception as e:
            raise FileOperationError("delete", file_name, str(e))

    async def delete_uploaded_file(self, file_name: str) -> Path:
        """
        [ASINKRON] Menghapus satu file yang diunggah.
        """
        return await asyncio.to_thread(self._delete_file_sync, file_name)

    def _clear_dir_sync(self, dir_path: Path) -> int:
        """
        [SINKRON] Worker untuk membersihkan direktori.
        """
        if not dir_path.exists():
            logger.error_print(f"Directory {dir_path} not found, nothing to clear.")
            return 0
        # Menggunakan utilitas 'clear_directory_contents' yang Anda sediakan
        return clear_directory_contents(dir_path)

    async def clear_extracted_projects_directory(self) -> int:
        """
        [ASINKRON] Membersihkan direktori extracted_projects.
        """
        if not self.extracted_dir.exists():
             logger.error_print(f"Directory {self.extracted_dir.name} not found, nothing to clear.")
             return 0
        return await asyncio.to_thread(self._clear_dir_sync, self.extracted_dir)