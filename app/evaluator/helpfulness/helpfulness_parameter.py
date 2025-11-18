import re
from enum import Enum
from dataclasses import dataclass

from app.evaluator.helpfulness.helpfulness_common import ScoreLevel, ParameterEvaluationExample
from app.schemas.models.code_component_schema import CodeComponent

from typing import Dict, Any, List, Tuple
from decimal import Decimal, ROUND_HALF_UP
def round_int(nilai):
    # Konversi ke Decimal dulu, lalu bulatkan
    return int(Decimal(str(nilai)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

class EvaluatorParameterDokumentasi: 
    """
    Mengevaluasi kualitas deskripsi parameter pada dokumentasi kode Python 
    menggunakan kriteria yang telah ditentukan.
    
    Kelas ini menilai seberapa baik deskripsi parameter menyampaikan tujuan, 
    batasan, dan konteks penggunaan, lebih dari sekadar informasi tipe data.
    """

    def __init__(self):
        """Inisialisasi evaluator dengan kriteria dan contoh."""
        self.criteria = self._initialize_criteria()
        self.examples = self._initialize_examples()

    def _initialize_criteria(self) -> Dict[str, Any]:
        """
        Menyiapkan kriteria evaluasi untuk deskripsi parameter.
        
        Kriteria mendefinisikan lima tingkat kualitas, dari sekadar 
        pengulangan tipe (1) hingga panduan penggunaan yang sangat baik (5).
        
        Returns:
            Dict berisi kriteria evaluasi dan deskripsi untuk setiap level skor.
        """
        return {
            'description': (
                'Evaluasi seberapa efektif deskripsi parameter menyampaikan tujuan, '
                'batasan (constraints), dan konteks penggunaan parameter inisialisasi kelas/fungsi. '
                'Deskripsi berkualitas tinggi harus melampaui informasi tipe data untuk memberikan '
                'panduan bermakna tentang penggunaan parameter, nilai yang valid, dan dampaknya '
                'terhadap perilaku kode.'
            ),
            'score_criteria': {
                ScoreLevel.POOR: (
                    'Deskripsi parameter hanya mengulang tipe parameter atau '
                    'mengubah type hints menjadi bahasa alami tanpa menambahkan '
                    'informasi bermakna tentang penggunaan atau tujuan.'
                ),
                ScoreLevel.FAIR: (
                    'Deskripsi memberikan informasi dasar tentang tujuan parameter '
                    'tetapi tidak memiliki detail tentang batasan, nilai yang valid, atau konteks penggunaan. '
                    'Mungkin menggunakan bahasa yang samar atau melewatkan detail penting.'
                ),
                ScoreLevel.GOOD: (
                    'Deskripsi menjelaskan tujuan parameter dan mencakup beberapa '
                    'batasan utama atau rentang nilai yang valid, tetapi mungkin melewatkan '
                    'kasus khusus (edge cases) atau kurang contoh jika diperlukan.'
                ),
                ScoreLevel.VERY_GOOD: (
                    'Deskripsi menjelaskan tujuan, batasan, dan pola penggunaan umum '
                    'dengan jelas. Mungkin menyertakan contoh untuk parameter yang kompleks '
                    'dan mencatat kasus khusus yang penting atau perilaku default.'
                ),
                ScoreLevel.EXCELLENT: (
                    'Deskripsi memberikan panduan komprehensif termasuk tujuan, '
                    'batasan, contoh, kasus khusus, dan dampak pada perilaku kelas/fungsi. '
                    'Tetapi tetap ringkas dan fokus pada informasi terpenting. '
                    'Ini membantu pengguna membuat keputusan yang tepat tentang nilai parameter.'
                )
            }
        }
    
    def _initialize_examples(self) -> List[ParameterEvaluationExample]:
        """
        Menyiapkan contoh konkret deskripsi parameter pada berbagai tingkat kualitas.
        (Diterjemahkan ke Bahasa Indonesia untuk konteks LLM).
        """
        return [
            ParameterEvaluationExample(
                parameters={
                    # Nama parameter biarkan inggris (sesuai kode), deskripsi diterjemahkan
                    "Model_entity_id": "Pengenal numerik untuk entitas model",
                    "Dist_pg": "Grup proses terdistribusi untuk koordinasi",
                    "Checkpoint_config": "Mendefinisikan interval penyimpanan checkpoint dan retensi",
                    "Runtime_config": "Menentukan batasan sumber daya atau lingkungan",
                    "Train_module": "Mengatur langkah pelatihan dan antarmuka dengan checkpoint"
                },
                quality_examples={
                    ScoreLevel.POOR: {
                        "Model_entity_id": "ID entitas model",
                        "Dist_pg": "Grup Proses",
                        "Checkpoint_config": "Konfigurasi checkpoint",
                        "Runtime_config": "Konfigurasi Runtime",
                        "Train_module": "Modul Pelatihan"
                    },
                    ScoreLevel.FAIR: {
                        "Model_entity_id": "Angka yang mengidentifikasi model",
                        "Dist_pg": "Grup proses untuk operasi terdistribusi",
                        "Checkpoint_config": "Pengaturan untuk manajemen checkpoint",
                        "Runtime_config": "Konfigurasi untuk perilaku runtime",
                        "Train_module": "Modul yang mengelola proses pelatihan"
                    },
                    ScoreLevel.GOOD: {
                        "Model_entity_id": "identifier untuk entitas model.",
                        "Dist_pg": "Grup proses terdistribusi PyTorch yang menangani komunikasi antar proses",
                        "Checkpoint_config": "Konfigurasi yang menentukan kapan checkpoint disimpan dan berapa banyak yang disimpan",
                        "Runtime_config": "Menentukan parameter runtime seperti batas memori dan pengaturan timeout",
                        "Train_module": "Modul yang mengimplementasikan logika pelatihan dan berinteraksi dengan sistem checkpoint"
                    },
                    ScoreLevel.VERY_GOOD: {
                        "Model_entity_id": "Pengenal numerik unik untuk entitas model di registry. Harus berupa ID model terdaftar yang valid",
                        "Dist_pg": "Grup proses terdistribusi PyTorch yang mengoordinasikan operasi di seluruh GPU/node selama pelatihan. Harus sesuai dengan setup terdistribusi Anda",
                        "Checkpoint_config": "Mengontrol frekuensi checkpoint, lokasi penyimpanan, dan kebijakan retensi. Penting untuk menyeimbangkan penggunaan disk dengan kemampuan pemulihan",
                        "Runtime_config": "Mendefinisikan batasan sumber daya dan parameter operasional. Harus dikonfigurasi dengan tepat untuk perangkat keras Anda guna menghindari masalah kinerja",
                        "Train_module": "Mengatur alur kerja pelatihan, mengelola transisi status, dan mendefinisikan komponen model apa yang di-checkpoint"
                    },
                    ScoreLevel.EXCELLENT: {
                        "Model_entity_id": "ID integer unik untuk entitas model (cth: 1014925). Harus selalu berupa angka 7 digit. Harus ada di registry model sebelum checkpointing, jika tidak akan memicu CheckpointNotFoundError.",
                        "Dist_pg": "Grup proses terdistribusi yang menangani operasi kolektif untuk setup multi-GPU atau multi-node. Setup ini harus konsisten dengan konfigurasi pelatihan 'distributed_training_config'.",
                        "Checkpoint_config": "Menentukan interval penyimpanan, format penamaan, dan retensi. Mendukung fitur lanjutan seperti checkpointing asinkron. Lihat contoh di dokumentasi internal.",
                        "Runtime_config": "Berisi batasan lingkungan (cth: memori, I/O disk) dan kebijakan konkurensi. Memastikan checkpointing tidak menunda pelatihan di bawah sumber daya terbatas, jika tidak akan memicu CheckpointAccessError.",
                        "Train_module": "Mengelola alur pelatihan end-to-end, memicu penyimpanan checkpoint pada interval yang tepat, dan memberikan konteks tentang status/parameter apa yang harus disimpan."
                    },
                },
                explanations={
                    ScoreLevel.POOR: "Deskripsi hanya mengulang info tipe minimal, kurang penggunaan atau batasan.",
                    ScoreLevel.FAIR: "Memberikan gambaran dasar tentang tujuan setiap parameter, tetapi kurang detail.",
                    ScoreLevel.GOOD: "Mencakup batasan inti dan sedikit konteks, tetapi beberapa detail penggunaan masih hilang.",
                    ScoreLevel.VERY_GOOD: "Menjelaskan pola penggunaan yang relevan, batasan, dan kebutuhan lingkungan.",
                    ScoreLevel.EXCELLENT: "Cakupan komprehensif termasuk dampak sumber daya, skenario penggunaan lanjutan, dan batasan spesifik."
                }
            )
        ]

    def get_evaluation_prompt(self, code_component: CodeComponent, documentation: str) -> str:
        """
        Menghasilkan prompt untuk evaluasi LLM dari deskripsi parameter.

        Args:
            code_component: Implementasi kode (kelas atau fungsi/metode)
            documentation: Dokumentasi kode yang akan dievaluasi (khususnya bagian parameter)
            eval_type: Tipe komponen kode (class, function, method).
            
        Returns:
            Prompt untuk evaluasi LLM
        """
        # Tentukan eval_type jika tidak disediakan
        eval_type = code_component.component_type

        example = self.examples[0]  # Gunakan contoh pertama sebagai referensi

        # --- Prompt dalam Bahasa Indonesia ---
        prompt = [
            f"Mohon evaluasi bagian deskripsi parameter untuk dokumentasi kode dari sebuah {eval_type} berdasarkan kriteria ini:"
        ]

        # Bagian kedua, kriteria evaluasi
        prompt.extend([
            "",
            "<kriteria_evaluasi>",
            "Kriteria evaluasi:",
            self.criteria['description'],
            "",
            "Level Skor:",
        ])
        
        # Tambahkan kriteria untuk setiap level skor
        for level in ScoreLevel:
            prompt.append(f"{level.value}. {self.criteria['score_criteria'][level]}")
        prompt.append("</kriteria_evaluasi>")
        
        # Tambahkan contoh referensi
        prompt.extend([
            "",
            "<contoh_referensi>",
            "Deskripsi parameter pada tingkat kualitas yang berbeda:",
        ])
        
        for level in ScoreLevel:
            prompt.extend([
                f"Level {level.value}:",
                *[f"{param}: {desc}" for param, desc in example.quality_examples[level].items()],
                f"Penjelasan: {example.explanations[level]}",
                ""
            ])
        prompt.append("</contoh_referensi>")
        

        # Tambahkan komponen kode fokus dan dokumentasi
        prompt.extend([
            "",
            "<komponen_kode_asli>",
            f"{code_component.source_code}",
            "</komponen_kode_asli>",
            "",
            "<parameter_untuk_dievaluasi>",
            "Deskripsi parameter untuk dievaluasi:",
            f"{documentation}",
            "</parameter_untuk_dievaluasi>"
        ])

        prompt.extend([
            "",
            "<instruksi_analisis>",
            "INSTRUKSI PENTING UNTUK ANALISIS:",
            "1. Analisis seberapa baik setiap deskripsi parameter memberikan informasi bermakna di luar petunjuk tipe (type hints).",
            "2. Pertimbangkan kelengkapan dokumentasi mengenai batasan dan nilai yang valid.",
            "3. Cari konteks yang membantu tentang dampak parameter terhadap perilaku komponen kode.",
            "4. Periksa contoh yang jelas atau panduan jika sesuai.",
            "</instruksi_analisis>",
            "",
            "<format_respons>",
            "Mohon struktur respons Anda sebagai berikut:",
            "1. Bandingkan terhadap kriteria dan level kualitas contoh.",
            "2. Sarankan perbaikan spesifik untuk deskripsi yang lemah. Sertakan saran Anda dalam tag <saran></saran>. Tidak perlu memberikan saran untuk deskripsi yang sudah sangat baik (excellent).",
            "3. Berikan skor Anda (1-5) di dalam tag <skor></skor>.",
            "</format_respons>",
            "",
            "Ingat: Jangan terburu-buru memberikan skor. Luangkan waktu untuk menganalisis secara menyeluruh dan membenarkan penalaran Anda.",
            "Skor harus mencerminkan analisis Anda yang cermat dan harus menjadi bagian terakhir dari respons Anda.",
        ])
        
        return "\n".join(prompt)
    
    def parse_llm_response(self, response: str) -> Tuple[int, str]:
        """
        Mengekstrak skor numerik dan saran dari respons LLM.
        """
        # Ekstrak skor dari tag XML (disesuaikan dengan prompt ID)
        score_patterns = [
            r'<skor>\s*(\d)\s*</skor>', 
            r'<score>\s*(\d)\s*</score>',
            r'skor:\s*(\d)', 
            r'skor\s*=\s*(\d)', 
            r'(\d)\s*/\s*5', 
        ]
        
        score = 3 # Default
        for pattern in score_patterns:
            score_matches = re.findall(pattern, response, re.IGNORECASE)
            if score_matches:
                total_score = 0
                for score_match in score_matches:
                    total_score += int(score_match)
                total_score /= len(score_matches)
                cand_score = round_int(total_score)
                if 1 <= cand_score <= 5:
                    score = cand_score
                    break
        
        # Ekstrak saran
        suggestion_patterns = [
            r'<saran>(.*?)</saran>', # XML tag Indonesia
            r'<suggestions>(.*?)</suggestions>', 
            r'saran:\s*(.+?)(?:\n\n|\Z)',
            r'perbaikan:?\s*(.+?)(?:\n\n|\Z)', 
        ]
        
        suggestion = ""
        for pattern in suggestion_patterns:
            suggestion_matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if suggestion_matches:
                suggestion = suggestion_matches[0].strip()
                break
        
        if not suggestion:
            # Fallback: cari kalimat yang terlihat seperti saran
            lines = response.split('\n')
            for i, line in enumerate(lines):
                if any(word in line.lower() for word in ["saran", "sarankan", "sebaiknya", "perbaiki"]) and i < len(lines) - 1:
                    suggestion = lines[i+1].strip()
                    break
            else:
                suggestion = "Pertimbangkan untuk menambahkan deskripsi parameter yang lebih rinci."
        
        return score, suggestion

    def get_criteria_description(self) -> str:
        """Mengembalikan deskripsi kriteria utama."""
        return self.criteria['description']

    def get_score_criteria(self, level: ScoreLevel) -> str:
        """Mengembalikan deskripsi kriteria untuk level skor tertentu."""
        return self.criteria['score_criteria'][level]

    def get_examples(self) -> List[ParameterEvaluationExample]:
        """Mengembalikan semua contoh evaluasi."""
        return self.examples