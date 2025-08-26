# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import router dari file yang sudah kita buat
from app.api import main_router
# Import konfigurasi
from app.core.config import UPLOAD_DIRECTORY
from contextlib import asynccontextmanager
from app.core.redis_client import get_redis_client

import redis
from app.core.redis_client import get_redis_client, redis_pool

# --- LIFESPAN EVENT MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Mengelola event saat startup dan shutdown aplikasi.
    """
    # --- Kode yang dijalankan SEBELUM aplikasi mulai menerima request (Startup) ---
    print("--- Memeriksa koneksi ke Redis... ---")
    redis_client = get_redis_client()
    try:
        # Kirim perintah PING untuk memvalidasi koneksi
        await redis_client.ping()
        print("✅ Redis connection successful!")
    except redis.exceptions.ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
    
    yield # Aplikasi sekarang siap dan akan berjalan

    # --- Kode yang dijalankan SETELAH aplikasi berhenti (Shutdown) ---
    print("--- Closing Redis connection... ---")
    await redis_pool.disconnect()
    print("🔌 Redis connection closed.")

# Inisialisasi aplikasi FastAPI
app = FastAPI(
    title="Automated Python Documentation Generator",
    version="0.1.0",
    lifespan=lifespan
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
    """Memastikan direktori upload ada saat aplikasi dimulai. Pastikan direktori ini ada sebelum memulai aplikasi."""
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    print(f"Uploaded Files Directory : '{UPLOAD_DIRECTORY}' created.")


# --- MENYERTAKAN ROUTER DARI MODUL LAIN ---
# Ini adalah bagian kunci yang menghubungkan endpoint kita ke aplikasi utama
app.include_router(main_router.router)


# --- ENDPOINT ROOT (OPSIONAL) ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Documentation Generator API!"}