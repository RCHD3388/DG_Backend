# main.py

import os
import json
from dotenv import load_dotenv
from app.services.docgen.orchestrator import Orchestrator

# Muat environment variables, terutama GOOGLE_API_KEY
load_dotenv()

if __name__ == "__main__":
    print("="*50)
    print("Menjalankan Sistem Dokumentasi Otomatis")
    print("="*50)

    # Inisialisasi Orchestrator
    orchestrator = Orchestrator()

    # Kode yang akan didokumentasikan
    sample_code = """
def calculate_fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
"""
    # Jalankan proses
    output = orchestrator.process(focal_component=sample_code)

    print("\n\n" + "="*50)
    print("HASIL AKHIR")
    print("="*50)
    
    # print("\n--- Respons dari Reader ---")
    # print(output["final_state"]["reader_response"])

    print("\n--- Statistik Penggunaan Token ---")
    print(json.dumps(output["usage_stats"], indent=2))