from typing import Dict, Set, Any, List
import networkx as nx
import json
from app.core.config import DEPENDENCY_GRAPHS_DIR
from app.utils.CustomLogger import CustomLogger

logger = CustomLogger("Topological")

def get_topological_sort_from_dependencies(DG: nx.DiGraph) -> List[str]:
        
    # Langkah 4: Periksa apakah ada siklus dependensi (cyclic dependency)
    # print(list(nx.simple_cycles(DG)))

    try:
        # Get Strongly Connected Components & condensate graph
        sccs = list(nx.strongly_connected_components(DG))
        condensatedDG = nx.condensation(DG, sccs)

        # Mapping node
        scc_map = {}
        for i, scc in enumerate(sccs):
            c_node_for_scc = condensatedDG.graph['mapping'][list(scc)[0]]
            scc_map[c_node_for_scc] = tuple(sorted(scc))
        
        # Topological Sorting graph
        sorted_c_nodes = list(nx.topological_sort(condensatedDG))
        final_processing_queue = []
        for c_node in sorted_c_nodes:
            # Ambil grup komponen asli dari map
            component_group = scc_map[c_node]
            
            # Tambahkan semua komponen dalam grup itu ke antrian akhir
            final_processing_queue.extend(component_group)

        data_to_save = {
            "processing_queue": final_processing_queue,
            "dependencies": list(DG.edges)
        }
        with open(DEPENDENCY_GRAPHS_DIR / "topological_sort_results.json", "w") as f:
            json.dump(data_to_save, f, indent=4)
            
        return final_processing_queue
    except nx.NetworkXUnfeasible:
        # Ini terjadi jika ada siklus dependensi (misal: A -> B -> A)
        logger.error_print("[TopoSort] Error: A cyclic dependency was detected in the graph.")
        # Anda bisa menangani ini dengan cara lain, misal mengembalikan list kosong
        return []

# def get_topological_sort_from_dependencies(dependency_dict: Dict[str, List[str]]) -> List[str]:
#     # Langkah 1 & 2: Buat daftar edges dari dictionary
#     edges = []
#     all_nodes = set(dependency_dict.keys())

#     for source_node, target_nodes in dependency_dict.items():
#         if not target_nodes:
#             continue
#         for target_node in target_nodes:
#             # Di networkx, edge (A, B) berarti A -> B (A menunjuk ke B).
#             # Dalam konteks dependensi, "A bergantung pada B" berarti kita perlu
#             # memproses B SEBELUM A. Jadi, edge harus dari B ke A (B -> A).
#             edges.append((target_node, source_node))
#             all_nodes.add(target_node)

#     # Langkah 3: Buat grafik berarah (DiGraph)
#     DG = nx.DiGraph()
#     DG.add_nodes_from(all_nodes) # Tambahkan semua node, termasuk yang terisolasi
#     DG.add_edges_from(edges)
    
#     # Langkah 4: Periksa apakah ada siklus dependensi (cyclic dependency)
#     # print(list(nx.simple_cycles(DG)))

#     try:
#         sorted_nodes = list(nx.topological_sort(DG))
#         return sorted_nodes
#     except nx.NetworkXUnfeasible:
#         # Ini terjadi jika ada siklus dependensi (misal: A -> B -> A)
#         print("Error: A cyclic dependency was detected in the graph.")
#         # Anda bisa menangani ini dengan cara lain, misal mengembalikan list kosong
#         return []