from typing import Dict, Any, List, Optional, Tuple
import re
from dataclasses import dataclass
from enum import Enum

from app.evaluator.helpfulness.helpfulness_common import ScoreLevel, SummaryEvaluationExample
from app.schemas.models.code_component_schema import CodeComponent

from typing import Dict, Any, List, Tuple
from decimal import Decimal, ROUND_HALF_UP
def round_int(nilai):
    # Konversi ke Decimal dulu, lalu bulatkan
    return int(Decimal(str(nilai)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

class EvaluatorSummaryDokumentasi: 
    """
    Mengevaluasi kualitas ringkasan (summary) dokumentasi kode Python 
    menggunakan kriteria dan contoh yang telah ditentukan.
    """

    def __init__(self):
        """Inisialisasi evaluator dengan kriteria dan contoh."""
        self.criteria = self._initialize_criteria()
        self.examples = self._initialize_examples()

    def _initialize_criteria(self) -> Dict[str, Any]:
        """
        Menyiapkan kriteria evaluasi untuk ringkasan dokumentasi kode.
        
        Kriteria ini mendefinisikan lima tingkat kualitas, dari sekadar 
        pengulangan signatur (1) hingga penjelasan konteks dan tujuan 
        yang sangat baik (5).
        
        Returns:
            Dict berisi kriteria evaluasi.
        """
        return {
            'description': (
                'Evaluasi seberapa efektif ringkasan satu baris dalam '
                'menyampaikan tujuan dan nilai dari fungsi/kelas. '
                'Ringkasan berkualitas tinggi harus ringkas namun informatif, '
                'menghindari pengulangan signatur, dan menambahkan '
                'konteks yang bermakna tentang "mengapa" (purpose) '
                'atau tujuan yang lebih tinggi.'
            ),
            'score_criteria': {
                ScoreLevel.POOR: (
                    'Ringkasan tidak relevan, menyesatkan, sangat generik '
                    '(misalnya "Melakukan fungsi"), atau struktur kalimatnya '
                    'rusak sehingga tidak menyampaikan makna apa pun tentang kode.'
                ),
                ScoreLevel.FAIR: (
                    'Ringkasan hanya menyatakan ulang signatur fungsi dalam '
                    'bahasa biasa (tautologi) tanpa memberikan informasi tambahan '
                    'selain yang sudah jelas dari nama dan parameter fungsi.'
                ),
                ScoreLevel.GOOD: (
                    'Ringkasan memberikan beberapa konteks tentang tujuan, '
                    'signatur, menyentuh kasus penggunaan utama, '
                    'tetapi bisa lebih spesifik. Ini memberi gambaran umum '
                    'tetapi mungkin melewatkan konteks penting.'
                ),
                ScoreLevel.VERY_GOOD: (
                    'Ringkasan secara efektif mengkomunikasikan apa yang '
                    'dilakukan fungsi dan tujuan tingkat tingginya, '
                    'menggunakan bahasa yang jelas yang membantu pembaca '
                    'memahami kapan/mengapa menggunakannya.'
                ),
                ScoreLevel.EXCELLENT: (
                    'Ringkasan secara sempurna menyeimbangkan keringkasan '
                    'dengan informasi, dengan jelas menyampaikan tujuan, '
                    'nilai, dan konteks fungsi secara praktis. '
                    'Ini membantu pembaca segera memahami apa yang dilakukan '
                    'fungsi dan mengapa itu penting.'
                )
            }
        }

    def _initialize_examples(self) -> List[SummaryEvaluationExample]:
        """
        Menyiapkan contoh konkret ringkasan pada berbagai tingkat kualitas.
        
        Returns:
            List berisi objek SummaryEvaluationExample.
        """
        return [
            SummaryEvaluationExample(
                function_signature=(
                    "def calculate_user_metrics(user_id: str, start_date: datetime, "
                    "end_date: datetime) -> Dict[str, float]"
                ),
                summaries={
                    ScoreLevel.POOR: "kalkulasi metrik pengguna.",
                    ScoreLevel.FAIR: "Menghitung metrik untuk pengguna di antara dua tanggal.",
                    ScoreLevel.GOOD: "Memproses data metrik pengguna melalui berbagai metode kalkulasi.",
                    ScoreLevel.VERY_GOOD: "Menganalisis pola keterlibatan pengguna dengan menghitung statistik interaksi harian.",
                    ScoreLevel.EXCELLENT: (
                        "Mengidentifikasi pengguna berisiko dengan "
                        "menganalisis pola keterlibatan terhadap indikator "
                        "historis."
                    )
                },
                explanations={
                    ScoreLevel.POOR: "Ringkasan ini terlalu generik dan tidak memberikan informasi spesifik tentang fungsi tersebut.",
                    ScoreLevel.FAIR: "Ringkasan ini hanya mengubah signatur fungsi menjadi kalimat, tidak memberikan nilai tambah.",
                    ScoreLevel.GOOD: "Meskipun ini menambahkan sedikit lebih banyak informasi, ringkasan ini tetap samar dan tidak membantu.",
                    ScoreLevel.VERY_GOOD: (
                        "Ini memberikan konteks tentang tujuan (analisis keterlibatan) "
                        "tetapi bisa lebih spesifik tentang mengapa kita melacak ini."
                    ),
                    ScoreLevel.EXCELLENT: (
                        "Ini dengan sangat baik menyampaikan fungsi teknis dan "
                        "tujuan bisnisnya (mencegah churn) dengan cara yang "
                        "jelas dan bermakna."
                    )
                }
            ),
            SummaryEvaluationExample(
                function_signature=(
                    "class DatasetLoader:"
                ),
                summaries={
                    ScoreLevel.POOR: "Kelas utama sistem loader.",
                    ScoreLevel.FAIR: "Sebuah kelas yang memuat dataset.",
                    ScoreLevel.GOOD: "Menangani pemuatan data dari berbagai sumber.",
                    ScoreLevel.VERY_GOOD: "Menyediakan antarmuka terpadu untuk memuat dan memvalidasi dataset dari berbagai sumber.",
                    ScoreLevel.EXCELLENT: (
                        "Memastikan kualitas dan konsistensi data dengan "
                        "menyediakan antarmuka terpadu untuk memuat, memvalidasi, "
                        "dan memproses data di berbagai format dan sumber sambil "
                        "menangani kasus-kasus khusus."
                    )
                },
                explanations={
                    ScoreLevel.POOR: "Sangat tidak jelas dan tidak mendeskripsikan fungsi spesifik kelas.",
                    ScoreLevel.FAIR: "Hanya menyatakan ulang nama kelas tanpa menambah nilai.",
                    ScoreLevel.GOOD: "Menambahkan informasi minimal, tetap samar tentang kemampuan.",
                    ScoreLevel.VERY_GOOD: (
                        "Memberikan konteks tentang fungsionalitas utama tetapi "
                        "bisa lebih baik menjelaskan manfaat dan kasus penggunaan."
                    ),
                    ScoreLevel.EXCELLENT: (
                        "Sangat baik menyeimbangkan kemampuan teknis dengan "
                        "manfaat praktis"
                    )
                }
            )
        ]

    def get_evaluation_prompt(self, code_component: CodeComponent, documentation: str) -> str:
        """
        Menghasilkan prompt untuk evaluasi LLM dari ringkasan dokumentasi kode.
        
        Args:
            code_component: Implementasi kode (kelas atau fungsi/metode)
            documentation: Teks dokumentasi kode yang akan dievaluasi
            eval_type: Tipe komponen kode (class, function, method).
            
        Returns:
            Prompt untuk evaluasi LLM
        """
        # Tentukan eval_type jika tidak disediakan
        eval_type = code_component.component_type.lower()
        is_class = eval_type == "class"
        
        # Pilih contoh yang relevan
        relevant_example = next(
            example for example in self.examples 
            if (example.function_signature.startswith('class') == is_class)
        )
        
        prompt = [
            # --- Teks Prompt yang Diterjemahkan ---
            f"Mohon HANYA evaluasi bagian ringkasan (summary) dari sebuah dokumentasi kode untuk {eval_type} berdasarkan kriteria ini:",
            "<kriteria_evaluasi>",
        ]
        
        for level in ScoreLevel:
            prompt.append(f"{level.value}. {self.criteria['score_criteria'][level]}")
        prompt.append("</kriteria_evaluasi>")
        
        prompt.extend([
            "",
            "<contoh_referensi>",
            "Ringkasan pada level yang berbeda:",
        ])
        
        for level in ScoreLevel:
            prompt.extend([
                f"Level {level.value}: {relevant_example.summaries[level]}",
                f"Penjelasan: {relevant_example.explanations[level]}",
                ""
            ])
        prompt.append("</Selesai_contoh_referensi>")

        prompt.extend([
            "",
            "<komponen_kode_asli>",
            f"{code_component.source_code}",
            "</komponen_kode_asli>",
        ])

        prompt.extend([
            "",
            "<dokumentasi_kode_untuk_dievaluasi>",
            f"{documentation}",
            "</dokumentasi_kode_untuk_dievaluasi>",
        ])
        
        prompt.extend([
            "",
            "<instruksi_analisis>",
            "INSTRUKSI PENTING UNTUK ANALISIS:",
            "1. Ambil waktu Anda untuk menganalisis hubungan antara komponen kode dan bagian ringkasan dari dokumentasi kode.",
            "2. Pertimbangkan seberapa banyak konteks dan nilai tambah yang diberikan ringkasan di luar signatur kode.",
            "3. Bandingkan ringkasan dengan kriteria setiap level skor secara metodis.",
            "4. Cari kesamaan dengan contoh yang diberikan pada setiap level kualitas.",
            "</instruksi_analisis>",
            "",
            "<format_respons>",
            "Mohon struktur respons Anda sebagai berikut:",
            "1. Pertama, jelaskan penalaran Anda dengan membandingkan terhadap kriteria.",
            "2. Jika relevan, berikan saran perbaikan spesifik. Sertakan saran Anda dalam tag <saran></saran>. Tidak perlu memberikan saran untuk ringkasan yang sudah sempurna.",
            "3. Terakhir, berikan skor Anda (1-5) di dalam tag <skor></skor>.",
            "</format_respons>",
            "",
            "Ingat: Jangan terburu-buru memberikan skor. Luangkan waktu untuk menganalisis secara menyeluruh dan membenarkan penalaran Anda.",
            "Skor harus mencerminkan analisis Anda yang cermat dan harus menjadi bagian terakhir dari respons Anda."
        ])
        
        return "\n".join(prompt)
    
    def parse_llm_response(self, response: str) -> Tuple[int, str]:
        """
        Mengekstrak skor numerik dan saran dari respons LLM.
        """
        # Pola skor (Logika tetap sama)
        score_patterns = [
            r'<skor>\s*(\d)\s*</skor>', # <-- Tag yang disesuaikan
            r'<score>\s*(\d)\s*</score>',
            r'skor:\s*(\d)',
            r'skor\s*=\s*(\d)',
            r'(\d)\s*/\s*5',
            r'level\s*(\d)',
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
        
        # Pola Saran (Logika tetap sama, tag disesuaikan)
        suggestion_patterns = [
            r'<saran>(.*?)</saran>', # <-- Tag yang disesuaikan
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
            # Fallback jika tidak ada tag yang ditemukan
            suggestion_sentences = []
            for sentence in re.split(r'[.!?]\s+', response):
                if any(word in sentence.lower() for word in ['sebaiknya', 'bisa', 'mungkin', 'pertimbangkan', 'sarankan', 'perbaiki']):
                    suggestion_sentences.append(sentence.strip())
            
            if suggestion_sentences:
                suggestion = ' '.join(suggestion_sentences) + '.'
            else:
                # Default suggestion (diterjemahkan)
                suggestion = "Pertimbangkan untuk menambahkan lebih banyak konteks dan tujuan pada ringkasan."
        
        return score, suggestion

    def get_criteria_description(self) -> str:
        """Mengembalikan deskripsi kriteria utama."""
        return self.criteria['description']

    def get_score_criteria(self, level: ScoreLevel) -> str:
        """Mengembalikan deskripsi kriteria untuk level skor tertentu."""
        return self.criteria['score_criteria'][level]

    def get_examples(self) -> List[SummaryEvaluationExample]:
        """Mengembalikan semua contoh evaluasi."""
        return self.examples