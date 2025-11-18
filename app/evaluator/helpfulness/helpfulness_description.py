import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple

from app.evaluator.helpfulness.helpfulness_common import ScoreLevel
from app.schemas.models.code_component_schema import CodeComponent
# --- Helper Class/Enum (Agar kode lengkap dan sudah diterjemahkan) ---

class ScoreLevel(Enum):
    """Mendefinisikan level skor (1-5)."""
    POOR = 1
    FAIR = 2
    GOOD = 3
    VERY_GOOD = 4
    EXCELLENT = 5

class DescriptionAspect(Enum):
    """Mendefinisikan empat aspek evaluasi deskripsi."""
    MOTIVATION = "Motivasi"
    USAGE_SCENARIOS = "Skenario Penggunaan"
    INTEGRATION = "Integrasi"
    FUNCTIONALITY = "Fungsionalitas"

@dataclass
class AspectCriteria:
    """Menyimpan rubrik penilaian untuk satu aspek."""
    description: str
    score_criteria: Dict[ScoreLevel, str]
    example_good: str
    example_poor: str

# --- Implementasi Evaluator Deskripsi (Sudah Direvisi) ---

class EvaluatorDeskripsiDokumentasi: # <-- REVISI NAMA
    """
    Mengevaluasi kualitas deskripsi dokumentasi kode Python 
    berdasarkan beberapa aspek.
    
    Evaluator ini menganalisis deskripsi dokumentasi kode berdasarkan 
    empat aspek utama:
    1. Penjelasan Motivasi/Tujuan
    2. Skenario dan kondisi penggunaan
    3. Integrasi dan interaksi sistem
    4. Gambaran fungsionalitas
    
    Setiap aspek dinilai secara independen pada skala 1-5.
    """

    def __init__(self):
        """Inisialisasi evaluator dengan kriteria yang telah ditentukan."""
        self.criteria = self._initialize_criteria()

    def _initialize_criteria(self) -> Dict[DescriptionAspect, AspectCriteria]:
        """
        Menyiapkan kriteria evaluasi untuk setiap aspek deskripsi.
        """
        return {
            DescriptionAspect.MOTIVATION: AspectCriteria(
                description="Seberapa baik deskripsi menjelaskan alasan atau motivasi di balik kode?",
                score_criteria={
                    ScoreLevel.POOR: "Tidak ada penjelasan mengapa kode itu ada atau tujuannya.",
                    ScoreLevel.FAIR: "Tujuan dasar disebutkan tetapi tanpa konteks atau alasan.",
                    ScoreLevel.GOOD: "Penjelasan tujuan yang jelas dengan beberapa konteks.",
                    ScoreLevel.VERY_GOOD: "Penjelasan tujuan yang mendalam dengan konteks teknis.",
                    ScoreLevel.EXCELLENT: "Penjelasan komprehensif tentang tujuan, konteks, dan proposisi nilai (value proposition)."
                },
                example_good=(
                    "Manajer cache ini mengatasi bottleneck kinerja dalam "
                    "respons API kami dengan mengurangi beban database "
                    "selama jam sibuk, sambil memastikan kesegaran data "
                    "untuk operasi kritis."
                ),
                example_poor="Ini adalah manajer cache untuk menyimpan data."
            ),
            
            DescriptionAspect.USAGE_SCENARIOS: AspectCriteria(
                description="Seberapa efektif deskripsi menjelaskan kapan dan bagaimana menggunakan kode?",
                score_criteria={
                    ScoreLevel.POOR: "Tidak ada informasi tentang skenario penggunaan.",
                    ScoreLevel.FAIR: "Informasi penggunaan dasar tanpa skenario spesifik.",
                    ScoreLevel.GOOD: "Beberapa skenario penggunaan utama dijelaskan.",
                    ScoreLevel.VERY_GOOD: "Skenario penggunaan jelas dengan kasus-kasus umum.",
                    ScoreLevel.EXCELLENT: "Cakupan kasus penggunaan yang baik, termasuk kasus-kasus khusus (edge cases)."
                },
                example_good=(
                    "Gunakan validator ini saat memproses data yang dikirimkan "
                    "pengguna, terutama untuk operasi berisiko tinggi seperti "
                    "transaksi keuangan. Ini menangani berbagai kasus khusus "
                    "termasuk pengiriman parsial dan format lama."
                ),
                example_poor="Memvalidasi data sesuai aturan."
            ),
            
            DescriptionAspect.INTEGRATION: AspectCriteria(
                description="Seberapa baik deskripsi menjelaskan integrasi dengan komponen sistem lain?",
                score_criteria={
                    ScoreLevel.POOR: "Tidak menyebutkan integrasi sistem.",
                    ScoreLevel.FAIR: "Referensi minimal ke komponen lain.",
                    ScoreLevel.GOOD: "Penjelasan dasar tentang interaksi utama.",
                    ScoreLevel.VERY_GOOD: "Deskripsi yang jelas tentang titik integrasi dan dependensi.",
                    ScoreLevel.EXCELLENT: "Gambaran komprehensif tentang interaksi sistem dan aliran data."
                },
                example_good=(
                    "Layanan ini terhubung dengan sistem UserAuth untuk validasi, "
                    "menulis log ke CloudWatch, dan memicu notifikasi melalui SNS. "
                    "Ini berfungsi sebagai penghubung penting antara frontend dan "
                    "prosesor pembayaran."
                ),
                example_poor="Memproses data dan mengirimkannya ke layanan lain."
            ),
            
            DescriptionAspect.FUNCTIONALITY: AspectCriteria(
                description="Seberapa jelas deskripsi menjelaskan fungsionalitas tanpa detail teknis yang berlebihan?",
                score_criteria={
                    ScoreLevel.POOR: "Tidak ada penjelasan fungsionalitas.",
                    ScoreLevel.FAIR: "Penjelasan yang terlalu teknis atau samar.",
                    ScoreLevel.GOOD: "Penjelasan dasar tentang fungsionalitas utama.",
                    ScoreLevel.VERY_GOOD: "Penjelasan fungsionalitas yang jelas dan seimbang.",
                    ScoreLevel.EXCELLENT: "Keseimbangan antara kejelasan dan detail teknis."
                },
                example_good=(
                    "Memproses data pelanggan yang masuk dengan terlebih dahulu "
                    "memvalidasi format dan bidang yang diperlukan, kemudian "
                    "memperkaya dengan data historis yang relevan, dan akhirnya "
                    "menghasilkan skor risiko menggunakan kriteria yang dapat dikonfigurasi."
                ),
                example_poor="Memproses data menggunakan berbagai fungsi dan algoritma."
            )
        }

    def get_evaluation_prompt(self, code_component: CodeComponent, documentation: str) -> str:
        """
        Menghasilkan prompt untuk evaluasi LLM dari deskripsi dokumentasi kode.
        
        Args:
            code_component: Implementasi fungsi atau kelas
            documentation: Teks dokumentasi kode untuk dievaluasi
            eval_type: Tipe komponen kode (class, function, method). 
        
        Returns:
            Prompt untuk evaluasi LLM
        """
        
        # Ekstrak deskripsi dari dokumentasi
        description = documentation
        
        if not description:
            return "Dokumentasi kode ini tidak memiliki bagian deskripsi untuk dievaluasi."
        
        prompt = ["# Evaluasi Deskripsi Dokumentasi Kode", ""]
        
        prompt.extend([
            "## Komponen Kode",
            f"```python",
            f"{code_component.source_code}",
            f"```",
            "",
        ])
        
        prompt.extend([
            "## Deskripsi Dokumentasi Kode untuk Dievaluasi",
            f"```",
            f"{description}",
            f"```",
            "",
        ])
        
        # Tambahkan kriteria evaluasi
        prompt.extend([
            "## Kriteria Evaluasi",
            "Mohon evaluasi deskripsi dokumentasi kode di atas berdasarkan empat aspek berikut:",
            ""
        ])
        
        for aspect in DescriptionAspect:
            criteria = self.criteria[aspect]
            prompt.extend([
                f"### {aspect.value}", # (Mengambil dari Enum yg sudah diterjemahkan)
                f"{criteria.description}",
                "",
                "Level Skor:",
                "",
            ])
            
            for level in ScoreLevel:
                prompt.append(f"{level.value}. {criteria.score_criteria[level]}")
            
            prompt.extend([
                "",
                "Contoh:",
                f"Baik: \"{criteria.example_good}\"",
                f"Buruk: \"{criteria.example_poor}\"",
                "",
            ])
        
        # Tambahkan instruksi format output
        prompt.extend([
            "## Format Output",
            "Mohon evaluasi deskripsi dan berikan penilaian Anda dalam format ini:",
            "",
            "```",
            f"{DescriptionAspect.MOTIVATION.value}: [skor 1-5]",
            f"{DescriptionAspect.USAGE_SCENARIOS.value}: [skor 1-5]",
            f"{DescriptionAspect.INTEGRATION.value}: [skor 1-5]",
            f"{DescriptionAspect.FUNCTIONALITY.value}: [skor 1-5]",
            "",
            "Keseluruhan: [rata-rata skor, dibulatkan ke bilangan bulat terdekat]",
            "",
            "Saran: [2-3 saran perbaikan konkret yang berfokus pada aspek terlemah]",
            "```",
        ])
        
        return "\n".join(prompt)

    def parse_llm_response(self, response: str) -> Tuple[int, str]:
        """
        Mengekstrak skor dan saran dari respons LLM.
        """
        default_score = 3
        
        if "tidak memiliki bagian deskripsi" in response.lower():
            return default_score, "Tambahkan bagian deskripsi ke dokumentasi kode."
        
        # Coba ekstrak skor keseluruhan
        overall_pattern = r"Keseluruhan:\s*\[?(\d)\.?\d*\]?"
        overall_matches = re.findall(overall_pattern, response, re.IGNORECASE)
        
        if overall_matches:
            overall_score = int(overall_matches[0])
        else:
            overall_score = default_score
        
        # Ekstrak saran
        suggestion_patterns = [
            r"Saran:\s*(.+?)(?:\n\n|\Z)", # Format Indonesia
            r"<saran>(.*?)</saran>", # Tag Indonesia
            r"Suggestions:\s*(.+?)(?:\n\n|\Z)", # Fallback
        ]
        
        suggestion = ""
        for pattern in suggestion_patterns:
            suggestion_matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if suggestion_matches:
                suggestion = suggestion_matches[0].strip()
                break
        
        if not suggestion:
            suggestion = "Pertimbangkan untuk menambahkan lebih banyak detail ke bagian deskripsi."
        
        return overall_score, suggestion
