from typing import Dict, Any, Optional, List, Tuple
from graphviz import Digraph
import os
from pathlib import Path
from app.schemas.models.code_component_schema import CodeComponent

# Ganti '...' dengan path yang benar ke skema Anda
# from ..schemas.models.code_component_schema import CodeComponent 

class GraphVisualizer:
    """
    Membuat visualisasi gambar statis untuk SETIAP komponen kode,
    menunjukkan dependensi lokalnya, dari daftar objek CodeComponent.
    """
    
    def __init__(self, components: Optional[List[CodeComponent]] = None, formated_component: Optional[Dict[str, CodeComponent]] = None):
        """
        Inisialisasi visualizer. Menerima daftar objek CodeComponent dan
        mengubahnya menjadi dictionary untuk pencarian cepat.
        """
        if formated_component != None :
            self.components: Dict[str, CodeComponent] = formated_component
        elif components != None:
            self.components: Dict[str, CodeComponent] = {
                component.id: component for component in components
            }
        else :
            self.components: Dict[str, CodeComponent] = {}
            
        print(f"GraphVisualizer diinisialisasi dengan {len(self.components)} komponen.")

    def _create_base_digraph(self) -> Digraph:
        """
        Membuat dan mengkonfigurasi objek Digraph dasar untuk setiap graf.
        """
        dot = Digraph()
        dot.attr(rankdir='TB', splines='ortho', nodesep='0.6', ranksep='1.0')
        dot.attr('node', shape='box', style='rounded,filled', fontname='Helvetica', fontsize='12')
        dot.attr('edge', color='gray50', arrowsize='0.7')
        return dot

    def _style_node(self, dot: Digraph, component_id: str, is_focal: bool = False):
        """
        Memberi style pada sebuah node berdasarkan datanya dari self.components.
        Sekarang bekerja dengan objek CodeComponent.
        """
        component = self.components.get(component_id)
        if not component:
            # Node untuk komponen yang tidak ditemukan (misalnya, library eksternal)
            dot.node(component_id, label=component_id.split('.')[-1], shape='ellipse', style='dashed', color='gray70')
            return

        # Mengakses atribut langsung dari objek CodeComponent
        comp_type = component.component_type
        color_map = {
            "class": "#a3c4f3", "method": "#fde4a3", "function": "#b3e6c3",
        }
        fillcolor = color_map.get(comp_type, "#e0e0e0")

        border_color = "black"
        penwidth = "1.0"
        if is_focal:
            border_color = "#d9534f" # Merah
            penwidth = "2.5"

        # Create node label
        parts = component_id.split('.')
        if comp_type == 'method' and len(parts) >= 2:
            class_name = parts[-2]
            method_name = parts[-1]
            short_name = f"{class_name}.\\n{method_name}"
        else:
            short_name = parts[-1]

        # Buat label akhir menggunakan format HTML-like dari Graphviz
        # short_name sudah berisi baris baru jika diperlukan
        label = f'<{short_name.replace(".\\n", ".<BR/>")}<BR/><FONT POINT-SIZE="10" COLOR="gray30">{comp_type}</FONT>>'

        dot.node(component_id, label=label, fillcolor=fillcolor, color=border_color, penwidth=penwidth)

    def generate_component_graph(self, component_id: str, output_dir: Path) -> Optional[str]:
        """
        Membuat satu gambar graf untuk satu komponen kode spesifik.

        Args:
            component_id (str): ID dari komponen fokus.
            output_dir (Path): Direktori untuk menyimpan file gambar.

        Returns:
            Optional[str]: Path ke file gambar yang dihasilkan, atau None jika
                           tidak ada dependensi.
        """
        focal_component = self.components.get(component_id)
        if not focal_component:
            print(f"Peringatan: Komponen '{component_id}' tidak ditemukan dalam data yang dimuat.")
            return None

        # Mengakses atribut langsung dari objek CodeComponent
        depends_on = focal_component.depends_on
        used_by = focal_component.used_by
        parent_class = getattr(focal_component, 'component_parents', None)

        # Kondisi: Lewati jika tidak ada dependensi sama sekali
        if not depends_on and not used_by and not parent_class:
            return None

        dot = self._create_base_digraph()
        
        # 1. Tambahkan dan style node fokus
        self._style_node(dot, component_id, is_focal=True)

        # 2. Tambahkan edge dan node untuk 'depends_on'
        for dep_id in depends_on:
            self._style_node(dot, dep_id)
            dot.edge(component_id, dep_id, xlabel='calls', fontsize='8', fontcolor='gray50')

        # 3. Tambahkan edge dan node untuk 'used_by'
        for user_id in used_by:
            self._style_node(dot, user_id)
            dot.edge(user_id, component_id, xlabel='uses', fontsize='8', fontcolor='gray50')

        # 4. Tambahkan edge dan node untuk 'parent_class'
        parent_class = list(parent_class)
        if parent_class:
            self._style_node(dot, parent_class)
            dot.edge(parent_class, component_id, xlabel='inherits', arrowhead='empty', style='dashed', fontsize='8', fontcolor='gray50')
        
        # 5. Render dan simpan graf
        safe_filename = component_id.replace('.', '_')
        output_path_obj = output_dir / safe_filename
        
        try:
            rendered_path = dot.render(str(output_path_obj), format='png', view=False, cleanup=True)
            # print(f"Graf untuk '{component_id}' berhasil disimpan di: {rendered_path}")
            return rendered_path
        except Exception as e:
            print(f"Gagal me-render graf untuk '{component_id}'. Pastikan Graphviz terinstal. Error: {e}")
            return None

    def generate_all_graphs(self, output_dir: Path) -> Tuple[int, int, List[str]]:
        """
        Method helper untuk mengiterasi semua komponen dan menghasilkan graf untuk masing-masing.

        Args:
            output_dir (Path): Direktori utama untuk menyimpan semua gambar graf.

        Returns:
            Tuple[int, int]: Jumlah graf yang berhasil dibuat dan jumlah yang dilewati.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nMemulai pembuatan graf untuk {len(self.components)} komponen...")
        
        success_count = 0
        skipped_count = 0
        
        processed_component_ids: List[str] = []
        
        for component_id in self.components.keys():
            rendered_path = self.generate_component_graph(component_id, output_dir)
            if rendered_path:
                processed_component_ids.append(component_id)
                success_count += 1
            else:
                skipped_count += 1
        
        print("\n--- Proses Selesai ---")
        print(f"Berhasil membuat {success_count} file graf.")
        print(f"Melewatkan {skipped_count} komponen karena tidak memiliki dependensi.")
        return success_count, skipped_count, processed_component_ids