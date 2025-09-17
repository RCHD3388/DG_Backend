from typing import Dict, Set, Any, List
import networkx as nx

def build_graph_from_components(components: Dict[str, Any]) -> Dict[str, Set[str]]:
    graph = {}
    
    for comp_id, component in components.items():
        # Initialize the node's adjacency list
        if comp_id not in graph:
            graph[comp_id] = set()
        
        # Add dependencies
        for dep_id in component.depends_on:
            # Only include dependencies that are actual components in our repository
            if dep_id in components:
                graph[comp_id].add(dep_id)
    
    return graph 

def get_topological_sort_from_dependencies(dependency_dict: Dict[str, List[str]]) -> List[str]:
    # Langkah 1 & 2: Buat daftar edges dari dictionary
    edges = []
    all_nodes = set(dependency_dict.keys())

    for source_node, target_nodes in dependency_dict.items():
        if not target_nodes:
            continue
        for target_node in target_nodes:
            # Di networkx, edge (A, B) berarti A -> B (A menunjuk ke B).
            # Dalam konteks dependensi, "A bergantung pada B" berarti kita perlu
            # memproses B SEBELUM A. Jadi, edge harus dari B ke A (B -> A).
            edges.append((target_node, source_node))
            all_nodes.add(target_node)

    # Langkah 3: Buat grafik berarah (DiGraph)
    DG = nx.DiGraph()
    DG.add_nodes_from(all_nodes) # Tambahkan semua node, termasuk yang terisolasi
    DG.add_edges_from(edges)
    
    # Langkah 4: Periksa apakah ada siklus dependensi (cyclic dependency)
    # print(list(nx.simple_cycles(DG)))

    try:
        sorted_nodes = list(nx.topological_sort(DG))
        return sorted_nodes
    except nx.NetworkXUnfeasible:
        # Ini terjadi jika ada siklus dependensi (misal: A -> B -> A)
        print("Error: A cyclic dependency was detected in the graph.")
        # Anda bisa menangani ini dengan cara lain, misal mengembalikan list kosong
        return []