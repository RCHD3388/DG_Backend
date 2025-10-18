# app/core/websocket_manager.py

from fastapi import WebSocket
from typing import Dict
from flask import json
import redis.asyncio as redis

# --- IMPOR MODEL UTAMA KITA ---
from app.schemas.models.task_schema import Task
from app.core.redis_client import get_redis_client

class ConnectionManager:
    _instance = None
    active_connections: Dict[str, WebSocket]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConnectionManager, cls).__new__(cls)
            cls._instance.active_connections = {}
        return cls._instance

    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[task_id] = websocket
        print(f"WebSocket connected for task_id: {task_id}")

    def disconnect(self, task_id: str):
        if task_id in self.active_connections:
            del self.active_connections[task_id]
            print(f"WebSocket disconnected for task_id: {task_id}")

    # --- FUNGSI INI ADALAH KUNCI KONSISTENSI ---
    async def broadcast_task_update(self, task_id: str):
        """
        Mengambil status terbaru dari Redis, memvalidasinya dengan model 'Task',
        dan mengirimkan objek lengkap ke klien yang terhubung.
        """
        if task_id not in self.active_connections:
            return # Tidak ada yang mendengarkan, jadi tidak perlu melakukan apa-apa

        redis_client = get_redis_client()
        try:
            task_data_raw = await redis_client.hgetall(f"task:{task_id}")
            if task_data_raw:
                # 1. Validasi dan parse data mentah dari Redis menggunakan model Task
                task_data_raw['discovered_files'] = json.loads(task_data_raw['discovered_files'])
                task_data_raw['components'] = json.loads(task_data_raw['components'])
                task_data = Task(**task_data_raw)
                
                # 2. Kirim seluruh objek Task yang sudah divalidasi dan terstruktur
                await self.active_connections[task_id].send_json(
                    task_data.model_dump(mode='json')
                )
        except Exception as e:
            print(f"Error broadcasting update for {task_id}: {e}")
            # Opsional: Kirim pesan error melalui WebSocket
            error_payload = {"error": "Failed to retrieve task status."}
            await self.active_connections[task_id].send_json(error_payload)
        finally:
            await redis_client.close()

    async def send_update(self, task_id: str, message: dict):
        """Mengirim pesan update (JSON) ke klien yang terhubung."""
        if task_id in self.active_connections:
            websocket = self.active_connections[task_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                # Tangani error jika koneksi sudah ditutup oleh klien secara tiba-tiba
                print(f"Error sending WebSocket update to {task_id}: {e}")
                self.disconnect(task_id)

websocket_manager = ConnectionManager()