# app/core/redis_client.py

import redis.asyncio as redis
from .config import settings

# --- INI BAGIAN PENTINGNYA ---
# Buat satu instance Connection Pool saat modul ini dimuat.
# Pool ini akan digunakan oleh seluruh aplikasi.
redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    username=settings.REDIS_USERNAME,
    password=settings.REDIS_PASSWORD,
    decode_responses=True # Sangat direkomendasikan
)


def get_redis_client() -> redis.Redis:
    """
    Dependency function yang menyediakan koneksi Redis DARI connection pool.
    
    Ini sangat efisien karena tidak membuat koneksi TCP baru setiap kali dipanggil.
    """
    return redis.Redis(connection_pool=redis_pool)