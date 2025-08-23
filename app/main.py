# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import router dari file yang sudah kita buat
from app.api import documentation_router
# Import konfigurasi
from app.core.config import UPLOAD_DIRECTORY

# Inisialisasi aplikasi FastAPI
app = FastAPI(
    title="Automated Python Documentation Generator",
    version="0.1.0"
)

# --- KONFIGURASI CORS ---
origins = [
    "http://localhost",
    "http://localhost:5173", # URL default Vite/React dev server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- LOGIKA STARTUP ---
@app.on_event("startup")
async def startup_event():
    """Memastikan direktori upload ada saat aplikasi dimulai."""
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    print(f"Direktori upload '{UPLOAD_DIRECTORY}' siap.")


# --- MENYERTAKAN ROUTER DARI MODUL LAIN ---
# Ini adalah bagian kunci yang menghubungkan endpoint kita ke aplikasi utama
app.include_router(documentation_router.router)


# --- ENDPOINT ROOT (OPSIONAL) ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Documentation Generator API!"}