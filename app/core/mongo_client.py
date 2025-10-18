from pymongo import MongoClient
from app.core.config import settings

client: MongoClient = None

def connect_to_mongo():
    """Inisialisasi koneksi MongoDB."""
    global client
    if client is None:
        client = MongoClient(settings.MONGO_URI)
        client.admin.command('ping')
        print("MongoDB: Koneksi berhasil!")

def close_mongo_connection():
    """Menutup koneksi MongoDB."""
    global client
    if client:
        client.close()
        print("MongoDB: Koneksi ditutup.")

def get_db():
    """Mengembalikan objek database."""
    return client[settings.MONGO_DATABASE]