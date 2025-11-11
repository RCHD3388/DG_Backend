# app/core/redis_client.py

import redis.asyncio as redis
import socket
from .config import settings

# --- INI BAGIAN PENTINGNYA ---
# Buat satu instance Connection Pool saat modul ini dimuat.
# Pool ini akan digunakan oleh seluruh aplikasi.
keepalive_options = {
    socket.TCP_KEEPIDLE: 60,   # Waktu (detik) idle sebelum probe pertama dikirim.
    socket.TCP_KEEPINTVL: 30,  # Interval (detik) antar probe.
    socket.TCP_KEEPCNT: 5,     # Jumlah probe yang gagal sebelum koneksi dianggap mati.
}

redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    username=settings.REDIS_USERNAME,
    password=settings.REDIS_PASSWORD,
    decode_responses=True, 
    socket_keepalive=True,
    socket_keepalive_options=keepalive_options
)


def get_redis_client() -> redis.Redis:
    """
    Dependency function yang menyediakan koneksi Redis DARI connection pool.
    
    Ini sangat efisien karena tidak membuat koneksi TCP baru setiap kali dipanggil.
    """
    return redis.Redis(connection_pool=redis_pool)