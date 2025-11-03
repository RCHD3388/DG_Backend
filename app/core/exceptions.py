# app/core/exceptions.py

"""
Definisi custom exception untuk aplikasi.
"""

class FileServiceError(Exception):
    """Base exception untuk error terkait FileService."""
    pass

class FileNotFound(FileServiceError):
    """Dilemparkan saat file yang diharapkan tidak ditemukan."""
    def __init__(self, file_name: str):
        self.file_name = file_name
        super().__init__(f"File '{file_name}' not found.")

class FileOperationError(FileServiceError):
    """Dilemparkan saat operasi file gagal (e.g., save, delete)."""
    def __init__(self, operation: str, file_name: str, message: str):
        self.operation = operation
        self.file_name = file_name
        super().__init__(f"Failed to {operation} file '{file_name}': {message}")

class InvalidFileNameError(FileServiceError):
    """Dilemparkan saat nama file tidak valid atau berpotensi bahaya."""
    def __init__(self, file_name: str):
        self.file_name = file_name
        super().__init__(f"Invalid or insecure file name: '{file_name}'.")