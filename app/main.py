# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import router dari file yang sudah kita buat
from app.api import main_router
# Import konfigurasi
from app.core.config import UPLOAD_DIRECTORY, GRAPH_VISUALIZATION_DIRECTORY
from contextlib import asynccontextmanager
from app.core.redis_client import get_redis_client
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.schemas.response_schema import StandardResponse, ErrorDetail
from app.core.mongo_client import connect_to_mongo, close_mongo_connection
from fastapi.staticfiles import StaticFiles

import redis
from app.core.config import initialize_output_directories
from app.core.redis_client import get_redis_client, redis_pool

# --- LIFESPAN EVENT MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Mengelola event saat startup dan shutdown aplikasi.
    """
    # --- Kode yang dijalankan SEBELUM aplikasi mulai menerima request (Startup) ---
    initialize_output_directories()
    
    print("--- Checking Redis connection... ---")
    redis_client = get_redis_client()
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    try:
        # Kirim perintah PING untuk memvalidasi koneksi
        await redis_client.ping()
        print("✅ Redis connection successful!")
    except redis.exceptions.ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
        
    try:
        connect_to_mongo()
        print("✅ MongoDB connection successful!")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
    
    yield # Aplikasi sekarang siap dan akan berjalan

    # --- Kode yang dijalankan SETELAH aplikasi berhenti (Shutdown) ---
    print("--- Closing ... ---")
    await redis_pool.disconnect()
    close_mongo_connection()
    print("🔌 Closed.")

# Inisialisasi aplikasi FastAPI
app = FastAPI(
    title="Automated Python Documentation Generator",
    version="0.1.0",
    lifespan=lifespan
)

# --- ERROR HANDLING ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    error_response = StandardResponse(
        success=False,
        error=ErrorDetail(
            code=exc.status_code,
            type=exc.__class__.__name__, # Misal: 'HTTPException', 'NotFoundException'
            message=str(exc.detail)
        )
    )
    return JSONResponse(
        status_code=exc.status_code,
        # model_dump() mengubah Pydantic model menjadi dictionary
        # exclude_none=True agar field 'data' yang kosong tidak dikirim
        content=error_response.model_dump(exclude_none=True)
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

# Mount files graph
app.mount("/graphs", StaticFiles(directory=GRAPH_VISUALIZATION_DIRECTORY), name="graphs")

# --- MENYERTAKAN ROUTER DARI MODUL LAIN ---
# Ini adalah bagian kunci yang menghubungkan endpoint kita ke aplikasi utama
app.include_router(main_router.router)


# --- ENDPOINT ROOT (OPSIONAL) ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to the Documentation Generator API!"}