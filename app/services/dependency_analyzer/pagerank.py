from typing import Dict, Set, Any, List, Tuple
import numpy as np
import networkx as nx

def customize_pagerank_processing(
    DG: nx.DiGraph, 
    alpha: float = 0.85, 
    max_iter: int = 100, 
    tol: float = 1.0e-6
) -> Tuple[Dict[str, float], int, List[Dict[str, float]]]:
    """
    Menghitung PageRank dan mengembalikan skor akhir, jumlah iterasi, 
    dan riwayat skor di setiap iterasi.
    
    Mengembalikan: (final_scores, total_iterations, history_of_scores)
    """
    
    if not DG:
        return {}, 0, []

    # 1. Setup Awal
    # Matriks transisi probabilitas (adjacency matrix yang sudah dinormalisasi)
    W = nx.google_matrix(DG, alpha=alpha, weight=None)
    N = W.shape[0]
    
    # Vektor PageRank Awal: Distribusi seragam
    x = np.array([1.0 / N] * N)
    
    # Simpan riwayat skor
    history: List[Dict[str, float]] = []
    
    # Mapping dari indeks matriks ke nama node
    node_mapping = dict(zip(range(N), DG.nodes()))

    # 2. Loop Iterasi
    for i in range(max_iter):
        xlast = x
        
        # Hitung skor PageRank iterasi berikutnya
        # x = alpha * xlast @ W + (1 - alpha) * p
        x = alpha * xlast @ W + (1 - alpha) * (1.0 / N)
        
        # Konversi skor NumPy ke format dictionary {node: score} untuk riwayat
        current_scores_dict = {node_mapping[j]: float(x[j]) for j in range(N)}
        history.append(current_scores_dict)
        
        # 3. Cek Konvergensi
        err = np.linalg.norm(x - xlast, ord=1) # Menggunakan Norma L1 untuk mengukur perubahan
        
        if err < tol:
            print(f"🎉 **Analisis Selesai:** Konvergensi tercapai pada iterasi ke-{i + 1}.")
            print(f"Perubahan Skor (Toleransi): {err:.8f}")
            
            # Mengembalikan hasil akhir (final_scores), total iterasi, dan riwayat
            return current_scores_dict, i + 1, history

    # Jika loop selesai tanpa konvergensi (mencapai max_iter)
    print(f"⚠️ **Peringatan:** Algoritma mencapai max_iter ({max_iter}) tanpa konvergensi.")
    return current_scores_dict, max_iter, history

def get_pagerank_scores(DG: nx.DiGraph) -> Dict[str, float]:

    try:
        # analyze_pagerank_scores, max_iter, history = customize_pagerank_processing(DG)
        # print("[PageRank] Max Iterasi: ", max_iter)
        # print("[PageRank] History: ", history)
        # print("[PageRank] Result: ", analyze_pagerank_scores)
        pagerank_scores = nx.pagerank(DG)
        
        return pagerank_scores
    except Exception as e:
        # Ini terjadi jika ada siklus dependensi (misal: A -> B -> A)
        print(f"[PageRank] Error: {e}")
        # Anda bisa menangani ini dengan cara lain, misal mengembalikan list kosong
        return []