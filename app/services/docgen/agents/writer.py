# agents/writer.py
import json
from typing import Optional, Dict, Any, List
import random
import traceback
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable, RunnablePassthrough, RunnableLambda, RunnableWithFallbacks
from langchain_core.exceptions import OutputParserException
from app.core.config import DUMMY_TESTING_DIRECTORY
from app.utils.file_utils import save_docgen_component_process
from app.services.docgen.agents.agent_output_schema import NumpyDocstring, DocstringParameter, DocstringReturn, DocstringRaise

from ..base import BaseAgent
from ..state import AgentState

from app.utils.CustomLogger import CustomLogger

logger = CustomLogger("Writer")

class Writer(BaseAgent):
      
      def __init__(self, llm_config: Dict[str, Any]):
         """Inisialisasi Writer, memuat semua template prompt."""
         super().__init__("writer", llm_config=llm_config)
         
         # Base prompt dan prompt spesifik dimuat sekali saat inisialisasi
         self.system_prompt_template: str = """You are a precise "Documentation Content Generator" AI. Your task is to generate a structured JSON object containing documentation content for a given Python code component.

   **PRIMARY DIRECTIVES:**
   1.  **Language:** All descriptive text MUST be in professional Bahasa Indonesia. Technical terms, code names, and types MUST remain in English.
   2.  **Output Format:** Your ENTIRE output MUST be a single, valid JSON object that strictly adheres to the provided schema. Do not output any text outside of the JSON structure.
   3.  **Content Focus:** Provide factual, concise content. Do not add formatting like indentation or quotes; the system will render the final documentation.

   The required JSON schema is provided in the user prompt under `OUTPUT FORMAT INSTRUCTIONS`.
   
   **TECHNICAL WRITING DIRECTIVES:**
   Selain tiga arahan utama di atas, seluruh konten deskriptif (dalam Bahasa Indonesia) HARUS mematuhi prinsip inti *Technical Writing* gaya Google:

   1.  **Gunakan Present Tense:** HARUS menggunakan **Present Tense** (Bentuk Waktu Sekarang Sederhana) untuk mendeskripsikan fakta atau perilaku kode yang konsisten. (Contoh: "Metode ini **memvalidasi** kredensial," bukan "Metode ini **akan memvalidasi** kredensial.")
   2.  **Gunakan Active Voice & Bahasa Jelas:**
      * Prioritaskan **Active Voice** (Kalimat Aktif) agar lebih jelas dan langsung. (Contoh: "Fungsi **memproses** data," lebih baik daripada "Data **diproses** oleh fungsi.")
      * HINDARI jargon, *slang*, bahasa *ableist*, kalimat yang terputus-putus (*choppy*), atau kalimat yang terlalu panjang dan bertele-tele (*long-winded*).
   3.  **Buat Dokumentasi Timeless:** HINDARI kata atau frasa yang mengikat dokumentasi pada waktu tertentu (misalnya: "saat ini", "sekarang", "segera"). Deskripsikan fungsionalitas sebagaimana adanya secara permanen.
   4.  **Jelas, Ringkas, Tidak Ambigu:** Konten HARUS jelas, padat, dan tidak ambigu (*unambiguous*). Fokus pada fakta. Jangan bertele-tele.
   5.  **Patuhi Aturan Konten Lainnya:** Perhatikan juga semua aturan penulisan konten, tata bahasa, dan ejaan standar lainnya untuk menjaga profesionalisme.
"""
         
         self.rules_for_function_template: str = """**TASK: Generate Documentation Content for a Function/Method**

You MUST analyze the code and context to fill all relevant fields in the JSON schema based on the following rules:

-   **`short_summary`**: (WAJIB) Tulis satu kalimat imperatif (perintah) ringkas.
    -   Fokus pada **APA** yang dilakukan atau dihasilkan fungsi.
    -   Tekankan pada **hasil atau efek utamanya**.
    -   **HINDARI** pengulangan nama fungsi.
    -   (Contoh: "Menvalidasi kredensial pengguna terhadap database.")
    
-   **`extended_summary`**: (WAJIB) Tulis paragraf deskriptif yang komprehensif.
    -   Paragraf ini HARUS mengalir secara naratif (bukan poin-poin).
    -   Informasi HARUS faktual berdasarkan kode dan konteks, jangan berhalusinasi.
    -   **ATURAN UTAMA**: Fokus pada **mengklarifikasi fungsionalitas** (apa yang dilakukan kode). **HINDARI** detail implementasi atau teori dasar (simpan untuk bagian `notes` jika dibutuhkan). Boleh *menyebut* nama parameter, tapi **JANGAN** menjelaskannya (simpan untuk bagian 'parameters`).
    -   Secara faktual jelaskan:
        1.  **MENGAPA** (Purpose/Use Case): Apa tujuan dan kasus penggunaan utama fungsi ini?
        2.  **KAPAN** (When to Use): Kapan situasi ideal untuk menggunakan fungsi ini?
        3.  **DI MANA** (Workflow Fit): Bagaimana posisinya dalam alur kerja sistem yang lebih besar?
        
-   **`parameters`**: (PENTING) Deteksi SEMUA parameter dari signatur. 
    -  Untuk setiap parameter, sediakan 'name', 'type', dan 'description'. Deskripsi HARUS mendalam dan mencakup:
    -   **ATURAN WAJIB (PENTING):**
        1.  **`name`**: (WAJIB IDENTIK) Salin NAMA parameter **secara identik** dari signatur kode. HARUS *case-sensitive* dan menyertakan awalan `*` atau `**` jika ada (misal: `*args`, `**kwargs`).
        2.  **`type`**: (WAJIB IDENTIK) Salin TIPE DATA (type hint) **secara identik** dari signatur kode. HARUS *case-sensitive* dan menyertakan semua karakter (misal: `Optional[str]`, `Dict[str, Any]`).
        3.  **`type` (JIKA KOSONG)**: **JIKA TIDAK ADA TIPE DATA** (type hint) secara eksplisit di signatur kode, Anda **WAJIB** mengisi *field* `type` dengan *string* `"None"`.
        4.  **`default`**: (WAJIB IDENTIK) JIKA parameter memiliki nilai *default* yang **tertulis eksplisit** di signatur kode (misal: `param: int = 5`), Anda **WAJIB** mendeteksi nilai tersebut dan menempatkannya **secara identik** (misal: `5`, `'test'`, `True`, `[{"A": "B"}]`) di *field* `default`. Jika tidak ada *default* eksplisit, *field* ini HARUS `null`.
    -   **ATURAN KONTEN (PENTING):**
        1.  **`description`**: Deskripsi HARUS mendalam dan mencakup:
            -  **Signifikansi**: Mengapa parameter ini penting?
            -  **Batasan**: Apa rentang nilai yang valid atau *constraints*?
            -  **Interdependensi**: Apakah nilainya bergantung atau memengaruhi parameter lain? 
            
-   **`returns`**: (PENTING) Analisis nilai yang dikembalikan oleh fungsi.
    -   **ATURAN UTAMA (PENTING):**
        1.  **`type` (JIKA ADA HINT)**: (WAJIB IDENTIK) Salin TIPE DATA (return hint) **secara identik** dari signatur kode. HARUS *case-sensitive* (misal: `Optional[str]`, `Dict[str, Any]`).
        2.  **`type` (JIKA KOSONG)**: JIKA **TIDAK ADA** TIPE DATA (return hint) secara eksplisit di signatur kode, TAPI fungsi/metode tersebut memiliki `return` statement dengan nilai tertentu (misal: `return data`), Anda **WAJIB** mengisi *field* `type` dengan *string* `"None"` (sedangkan penjelasan nilai yang dikembalikan dapat disertakan pada *field* `description`).
        3.  **`returns: null` (JIKA VOID)**: JIKA fungsi **TIDAK MENGEMBALIKAN NILAI EKSPLISIT** (misal: `return` saja, atau tidak ada `return`), Anda **WAJIB** menyetel *field* `returns` di JSON utama menjadi `null`.
    -   **ATURAN KONTEN (PENTING):**
        1.  **`description`**: Deskripsi HARUS mendalam dan menjelaskan:
            -  **Representasi**: Apa arti atau yang direpresentasikan oleh nilai ini?
            -  **Kemungkinan Nilai**: Apa kemungkinan nilai atau rentang spesifik yang dikembalikan?
            -  **Kondisi**: Apakah ada kondisi yang memengaruhi nilai kembalian?
    
-   **`yields`**: (KHUSUS GENERATOR) JIKA fungsi ini adalah generator (MENGGUNAKAN `yield`), analisis nilai yang di-*yield*.
    -   **ATURAN UTAMA (PENTING):**
        1.  **`type` (JIKA ADA HINT)**: (WAJIB IDENTIK) Salin TIPE DATA yang di-*yield* **secara identik**. (misal: dari `Generator[int, ...]` tipenya adalah `int`).
        2.  **`type` (JIKA KOSONG)**: JIKA **TIDAK ADA** TIPE DATA (return hint) yang ditulis secara eksplisit pada kode, TAPI fungsi memiliki `yield` statement, Anda **WAJIB** mengisi *field* `type` dengan *string* `"None"` (sedangkan penjelasan nilai yang dikembalikan dapat disertakan pada *field* `description`).
    -   **ATURAN KONTEN:**
        1.  **`description`**: Deskripsi HARUS mendalam dan menjelaskan **Representasi**, **Kemungkinan Nilai**, dan **Kondisi** dari nilai yang di-*yield*.

-   **`receives`**: (OPTIONAL PADA GENERATOR) JIKA fungsi ini adalah generator DAN dirancang untuk menerima nilai melalui `.send()`, deteksi parameter yang diterima.
    -   **ATURAN WAJIB (PENTING):**
        1.  **`name`**: (WAJIB IDENTIK) Salin NAMA secara identik dan wajib case-sensitive sesuai yang terdapat pada code.
        2.  **`type`**: (WAJIB IDENTIK) Salin TIPE DATA secara identik dan wajib case-sensitive sesuai yang terdapat pada code.
        3.  **`type` (JIKA KOSONG)**: **JIKA TIDAK ADA TIPE DATA** (type hint) di signatur kode, Anda **WAJIB** mengisi *field* `type` dengan nilai `"None"`.
    -   **ATURAN KONTEN:**
        1.  **`description`**: Deskripsi HARUS mendalam dan mencakup **Signifikansi**, **Batasan**, dan **Interdependensi**.

-   **`raises` dan `warns` (Opsional):**
    -   **`raises`**: (WAJIB JIKA ADA) Deteksi `raise` statement eksplisit PADA kode yang SEDANG didokumentasi.
        -   **`error`**: (WAJIB IDENTIK) Salin tipe *error* **secara identik** dari kode. HARUS *case-sensitive* (misal: 'ValueError', 'TypeError', ...).
        -   **`description`**: Jelaskan **kondisi dan keadaan** yang memicu *error* ini.
    -   **`warns`**: (WAJIB JIKA ADA) DETEKSI PEMANGGILAN `warnings.warn()` secara eksplisit PADA kode yang SEDANG didokumentasi.
        -   **`warning`**: (WAJIB IDENTIK) Salin tipe *warning* **secara identik** dari kode. HARUS *case-sensitive* (misal: 'RuntimeWarning', 'DeprecationWarning', ...).
        -   **`description`**: Jelaskan **kondisi dan keadaan** yang memicu *warning* ini.        

-   **`examples`**: (PENTING).
    -   **ATURAN STATUS (TEGAS):** `examples` **WAJIB** anda berikan jika pengecualian dibawah tidak terjadi.
    -   **PENGECUALIAN :** `examples` menjadi **OPSIONAL** (biarkan `null` jika tidak krusial) HANYA JIKA kondisi ini **TERTULIS EKSPLISIT** di kode:
        1.  Nama function diawali dengan `_` (misal: `_private_function`).
        2.  Metode memiliki decorator `@abstractmethod`.
    -   **PERINGATAN UTAMA (ANTI-HALUSINASI)**: Contoh HARUS 100% FAKTUAL dan JELAS. **Lebih baik mengembalikan `null`** daripada mengarang (berhalusinasi) skenario yang tidak faktual atau tidak jelas.
    -   **ATURAN KONTEKS (WAJIB)**: Fokus HANYA pada baris kode yang memanggil komponen tersebut. **WAJIB ASUMSIKAN** semua dependensi (modul, *instance* kelas) sudah ada. **DILARANG KERAS** mendefinisikan ulang kelas/fungsi/method atau menyertakan `import` yang tidak perlu.
    -   **FOKUS KONTEN (Ringkas)**: Fokus untuk **mengilustrasikan penggunaan** (bukan *testing*). Tunjukkan **Skenario Praktis**, **Kombinasi Parameter** umum, atau (jika relevan) pemanggilan yang memicu **Exception**.
    -   **ATURAN FORMAT (WAJIB):**
        1.  Gunakan format **doctest** (dimulai dengan `>>> `).
        2.  Pisahkan **beberapa** contoh dengan **baris kosong**.
        3.  Sertakan **komentar ringkas dan to-the-point** (diawali `#`) untuk menjelaskan setiap contoh.

-   **Bagian Lain (`notes`, `see_also`, `warnings_section` - OPSIONAL):**
    -   **PERINGATAN KETAT:** HANYA isi *field-field* ini jika informasi yang relevan 100% FAKTUAL, jelas dari konteks/kode, DAN penting/krusial untuk diketahui pembaca.
    -   **Jika terdapat sedikit keraguan mengenai akurasi atau kepentingannya, JANGAN DITULIS** (biarkan *field* tersebut `null`).
"""

         self.rules_for_class_template: str = """**TASK: Generate Documentation Content for a Class**

You MUST analyze the code and context to fill all relevant fields in the JSON schema based on the following rules (standar NumPyDoc):

-   **`short_summary`**: (WAJIB) Tulis satu kalimat deskriptif yang ringkas.
    -   Fokus pada **APA** yang direpresentasikan oleh kelas ini (misal: "Sebuah model...", "Sebuah konfigurasi...").
    -   Tekankan pada **tujuan atau peran utamanya** dalam sistem.
    -   **HINDARI** pengulangan nama kelas.
    -   (Contoh: "Mengelola konfigurasi database dan koneksi pool.")
    
-   **`extended_summary`**: (WAJIB) Tulis paragraf deskriptif yang komprehensif.
    -   Paragraf ini HARUS mengalir secara naratif (bukan poin-poin).
    -   Informasi HARUS FAKTUAL berdasarkan kode dan konteks, jangan berhalusinasi.
    -   **ATURAN UTAMA**: Fokus pada **mengklarifikasi fungsionalitas** (apa yang dilakukan kode). **HINDARI** detail implementasi atau teori dasar (simpan untuk bagian `notes` jika dibutuhkan). Boleh *menyebut* nama parameter, tapi **JANGAN** menjelaskannya (simpan untuk bagian 'parameters`).
    -   Secara faktual jelaskan:
        1.  **DI MANA** (Architecture): Bagaimana posisinya dalam arsitektur sistem yang lebih besar? (misal: "Bertindak sebagai...")
        2.  **MENGAPA** (Motivation): Apa motivasi dan tujuan utama di balik pembuatan kelas ini?
        3.  **KAPAN** (Scenarios): Kapan skenario atau kondisi ideal untuk menggunakan (membuat instance) kelas ini?
        
-   **`parameters`**: (PENTING) Deteksi parameter dari constructor (`__init__`). 
    -   **ATURAN UTAMA (PENTING):** Periksa apakah ada metode `def __init__(self, ...)` yang **tertulis secara eksplisit (manual)** di dalam kode kelas.
        1.  **JIKA `__init__` MANUAL TIDAK DITEMUKAN:** (Misalnya, ini adalah `@dataclass` standar, `pydantic.BaseModel`, *class* kosong yang tidak memiliki `__init__`), Anda **WAJIB** menyetel *kunci* `parameters` di JSON utama menjadi `null`.
        2.  **JIKA `__init__` MANUAL DITEMUKAN:** Anda **WAJIB** mendokumentasikan SEMUA parameter dari `__init__` manual tersebut di sini, dengan mengikuti "Aturan Wajib" dan "Aturan Konten" di bawah.
            -   **ATURAN WAJIB (PENTING):**
                1.  **`name`**: (WAJIB IDENTIK) Salin NAMA parameter **secara identik** dari signatur `__init__`. HARUS *case-sensitive* dan menyertakan awalan `*` atau `**` jika ada. (Abaikan `self`).
                2.  **`type`**: (WAJIB IDENTIK) Salin TIPE DATA (type hint) **secara identik** dari signatur `__init__`. HARUS *case-sensitive* (misal: `Optional[str]`).
                3.  **`type` (JIKA KOSONG)**: **JIKA TIDAK ADA TIPE DATA** (type hint) yang ditulis secara eksplisit di signatur `__init__`, Anda **WAJIB** mengisi *field* `type` dengan *string* `"None"`.
                4.  **`default`**: (WAJIB IDENTIK) JIKA parameter memiliki nilai *default* yang **tertulis eksplisit** di signatur kode (misal: `param: int = 5`), Anda **WAJIB** mendeteksi nilai tersebut dan menempatkannya **secara identik** (misal: `5`, `'test'`, `True`, `[{"A": "B"}]`) di *field* `default`. Jika tidak ada *default* eksplisit, *field* ini HARUS `null`.
            -   **ATURAN KONTEN:**
                1.  **`description`**: (dalam Bahasa Indonesia) Deskripsi HARUS mendalam dan mencakup:
                    -  **Signifikansi**: Mengapa parameter ini penting untuk inisialisasi? Apa pengaruhnya terhadap *instance*?
                    -  **Batasan**: Apa rentang nilai yang valid atau *constraints* ?
                    -  **Relasi**: Apakah nilainya bergantung atau memengaruhi parameter lain saat inisialisasi?
            
-   **`attributes`**: (PENTING) Deteksi **atribut publik non-metode (non-method attributes)** yang relevan.
    -    **ATURAN PENDETEKSIAN (PENTING):** Anda WAJIB mencari atribut di dua tempat utama:
            1.  ***Field* Level Kelas:** Atribut yang didefinisikan langsung di *class body*. (Ini termasuk *field* dari `@dataclass`, `pydantic.BaseModel`, atau variabel kelas standar).
            2.  ***Field* `__init__`:** Atribut yang didefinisikan di dalam `__init__` manual (misal: `self.nama_atribut = ...`).
    -   Untuk setiap atribut, Anda HARUS menyediakan 'name', 'type', dan 'description'.
    -   **ATURAN WAJIB (PENTING):**
        1.  **`name`**: (WAJIB IDENTIK) Tulis NAMA atribut **tanpa** awalan `self.` (misal: deteksi `self.my_attr`, tulis `my_attr`). HARUS *case-sensitive*.
        2.  **`type`**: (WAJIB IDENTIK) Salin TIPE DATA (type hint) **secara identik** dari kode (misal: dari `self.my_attr: int`). HARUS *case-sensitive*.
        3.  **`type` (JIKA KOSONG)**: **JIKA TIDAK ADA TIPE DATA** (type hint) yang terdeteksi untuk atribut, Anda **WAJIB** mengisi *field* `type` dengan *string* `"None"`.
        4.  **`default`**: (WAJIB IDENTIK) JIKA atribut memiliki nilai *default* yang **tertulis eksplisit**, Anda **WAJIB** mendeteksi nilai tersebut dan menempatkannya **secara identik** di *field* `default`. Jika tidak ada *default*, maka *field* ini HARUS `null`.
    -   **ATURAN KONTEN:**
        1.  **`description`**: (dalam Bahasa Indonesia) Deskripsi HARUS mendalam dan menjelaskan:
            -  **Tujuan/Signifikansi**: Apa tujuan atribut ini dan mengapa ia disimpan/diekspos?
            -  **Batasan Nilai**: (Opsional) Jelaskan batasan nilai yang valid jika *type hint* tidak cukup (misal: "Harus integer positif").
            -  **Dependensi**: Apakah nilainya bergantung pada atribut atau `parameter` constructor lain?

-   **`examples`**: (PENTING).
    -   **ATURAN STATUS (TEGAS):** `examples` **WAJIB** anda berikan jika pengecualian dibawah tidak terjadi.
    -   **PENGECUALIAN :** `examples` menjadi **OPSIONAL** (biarkan `null` jika tidak krusial) HANYA JIKA kondisi ini **TERTULIS EKSPLISIT** di kode:
        1.  Nama kelas diawali dengan `_` (misal: `_PrivateClass`).
    -   **PERINGATAN UTAMA (ANTI-HALUSINASI)**: Contoh HARUS 100% FAKTUAL dan JELAS. **Lebih baik mengembalikan `null`** daripada mengarang (berhalusinasi) skenario yang tidak faktual atau tidak jelas.
    -   **ATURAN KONTEKS (WAJIB)**: Fokus HANYA pada baris kode yang memanggil komponen tersebut. **WAJIB ASUMSIKAN** semua dependensi (modul, *instance* kelas) sudah ada. **DILARANG KERAS** mendefinisikan ulang kelas/fungsi/method atau menyertakan `import` yang tidak perlu.
    -   **FOKUS KONTEN (Ringkas)**: Fokus untuk **mengilustrasikan penggunaan** (bukan *testing*). Tunjukkan **Skenario Praktis**, **Kombinasi Parameter** umum, atau (jika relevan) pemanggilan yang memicu **Exception**.
    -   **ATURAN FORMAT (WAJIB):**
        1.  Gunakan format **doctest** (dimulai dengan `>>> `).
        2.  Pisahkan **beberapa** contoh dengan **baris kosong**.
        3.  Sertakan **komentar ringkas dan to-the-point** (diawali `#`) untuk menjelaskan setiap contoh.

-   **Bagian Lain (`notes`, `see_also`, `warnings_section` - OPSIONAL):**
    -   **PERINGATAN KETAT:** HANYA isi *field-field* ini jika informasi yang relevan 100% faktual, jelas dari konteks/kode, DAN penting/krusial untuk diketahui pembaca.
    -   **Jika terdapat sedikit keraguan mengenai akurasi atau kepentingannya, JANGAN DITULIS** (biarkan *field* tersebut `null`).
"""
         
         self.json_parser = PydanticOutputParser(pydantic_object=NumpyDocstring)
         self.main_llm = self.llm 
         
         # Chain akan dibuat saat inisialisasi atau sebelum pemanggilan pertama
         self.full_writer_chain: Optional[Runnable] = self._setup_writer_chain() # Poin 2
         
         
      def _get_specific_prompt(self, type: str) -> str:
         """Memilih prompt yang sesuai (kelas atau fungsi/metode)."""
         is_class = type.lower() == "class"
         return self.rules_for_class_template if is_class else self.rules_for_function_template


      def _build_human_prompt(self, state: AgentState) -> str:
         """Menyusun prompt utama Writer."""
         
         # Cek apakah ini panggilan pertama (hanya ada System message di memori)
         # Asumsi self.memory adalah List[BaseMessage]
         is_first_attempt = len(self.memory) <= 1 

         # Ambil bagian yang mungkin dibutuhkan di kedua skenario
         specific_rules = self._get_specific_prompt(state["component"].component_type)
         focal_component = state["focal_component"]
         
         if is_first_attempt:
            # --- PANGGILAN PERTAMA: PROMPT LENGKAP ---
            logger.info_print("Building FULL prompt (First attempt)")
            
            context = state.get("context", "No context was gathered.")
            
            human_prompt_string = f"""
Available Context: {context}

{specific_rules}

Sekarang, hasilkan dokumentasi JSON berkualitas tinggi untuk 'Code Component' berikut berdasarkan 'Available Context'.
Anda WAJIB hanya menghasilkan output berupa object JSON.
```python
{focal_component}
```
""" 
            return human_prompt_string

         else:
            # --- PANGGILAN KOREKSI: PROMPT HYBRID (HEMAT TOKEN) ---
            logger.info_print("Building HYBRID prompt (Correction cycle)")
            
            return f"""Anda telah menerima umpan balik (feedback) pada output JSON Anda sebelumnya (yang ada di 'chat history'). Harap buat ulang (re-generate) seluruh objek JSON yang telah dikoreksi berdasarkan *feedback* tersebut.

PENTING:
1. Rujuk ke instruksi PERTAMA Anda untuk 'Available Context' yang lengkap.
2. Gunakan 'Specific Rules' dan 'Code Component' yang diberikan KEMBALI di bawah ini.

Anda WAJIB hanya mengeluarkan objek JSON baru yang valid. Jangan tambahkan teks percakapan (conversational text) apa pun.
{specific_rules}

Code Component:
```Python
{focal_component}
```
"""

      def _setup_writer_chain(self) -> Runnable:
         """Membangun LCEL chain dengan mekanisme Koreksi Diri (2-tingkat)."""

         # 1. Dapatkan format instructions
         format_instructions = self.json_parser.get_format_instructions()
         
         # 2. Buat Prompt Template Konversasional
         prompt = ChatPromptTemplate.from_messages([
               ("system", self.system_prompt_template + \
                        "\n\nOUTPUT FORMAT INSTRUCTIONS (JSON):\n---\n{format_instructions}\n---"),
               
               # Ini adalah placeholder untuk SEMUA riwayat obrolan
               MessagesPlaceholder(variable_name="chat_history")
         ])
         
         # 3. "Panggang" format_instructions ke dalam prompt
         prompt = prompt.partial(format_instructions=format_instructions)
         
         def print_prompt_and_pass(prompt_value):
            """Mengambil PromptValue, mencetaknya, dan meneruskannya."""
            folder_path = DUMMY_TESTING_DIRECTORY / f"component_{self.current_component_id}" if self.current_component_id else DUMMY_TESTING_DIRECTORY
            
            save_docgen_component_process(
                file_path= folder_path / f"Writer_Prompt_{len(self.memory)}_{datetime.now().strftime("%H_%M_%S")}.txt",
                content = prompt_value.to_string(),
                type = "json"
            )
            
            return prompt_value # PENTING: Meneruskan PromptValue ke LLM
         
         # 4. Bangun chain (Prompt -> LLM -> Parser)
         chain = prompt | RunnableLambda(print_prompt_and_pass) | self.main_llm.with_config({"tags": [self.name]}) | self.json_parser.with_config({"tags": [self.name]})
         
         return chain
         

      def process(self, state: AgentState) -> AgentState:
         
         # Untuk simpen process perlu component id
         self.current_component_id = state["component"].id
         logger.info_print("Run - Generating docstring ...")

         # Pastikan chain sudah di-setup
         if not self.full_writer_chain:
            self.full_writer_chain = self._setup_writer_chain()

         config = {"tags": [self.name], "callbacks": state["callbacks"]}
         
         # 1. Bangun prompt manusia (Lengkap atau Hibrida)
         human_task_prompt = self._build_human_prompt(state)
         
         # 2. Tambahkan prompt tugas ini ke memori
         # Memori sekarang berisi: [..., (feedback_v1), human_task_v2]
         self.add_to_memory("user", human_task_prompt)
         
         # 3. Siapkan input untuk chain konversasional
         llm_input = {
               "chat_history": self.memory 
         }
         
         parsed_output: Optional[NumpyDocstring] = None
         try:
            # Invocation
            # Input ke chain adalah dictionary state
            parsed_output = self.full_writer_chain.invoke(llm_input, config=config)
            
            # with open(DUMMY_TESTING_DIRECTORY / f"DocJSONResponse_{datetime.now().strftime("%H_%M_%S")}.json", "w", encoding="utf-8") as f:
            #    json.dump(parsed_output.model_dump(), f, indent=4, ensure_ascii=False)
            
            self.add_to_memory("assistant", parsed_output.model_dump_json())

            # Format output (Poin 4: Berhasil)
            state["documentation_json"] = parsed_output
            
         except (OutputParserException, Exception) as e: 
            # Kegagalan Total (Setelah 2 upaya gagal)
            logger.error_print(f"[CRITICAL FAILURE]: Writer Agent failed after all retries. Error: {str(e)}")
            logger.error_print(traceback.format_exc())
            
            # FINAL FALLBACK (Poin 4: Gagal)
            # Kita menggunakan string kesalahan sebagai formatted_documentation
            error_docstring = f"""
   !!! DOCSTRING GENERATION FAILED !!!
   The Writer Agent failed to produce valid structured output after all correction attempts.
   Error Type: {type(e).__name__}
   Manual Review is required for component: {state['component'].id}
            """
            
            error_msg = f'{{"error": "Generation failed", "details": "{str(e)}"}}'
            self.add_to_memory("assistant", error_msg)
            
            state['documentation_json'] = None

         return state

# # VERSION 01 EXMPLE PROMPT 
# -   **`examples`**: (Sangat dianjurkan) Tulis contoh kode singkat dalam format **doctest** (dimulai dengan `>>> `).
#     -   **ATURAN KETAT**: Fokus untuk **mengilustrasikan penggunaan**, BUKAN untuk *testing*. Contoh HARUS RINGKAS, JELAS, dan FAKTUAL.
#     -   **ANTI-HALUSINASI**: **Lebih baik mengembalikan `null` ** daripada mengarang (berhalusinasi) skenario yang tidak faktual atau tidak jelas.
#     -   **FOKUS KONTEN**: Tunjukkan **Skenario Praktis**, **Kombinasi Parameter** umum, atau (jika relevan) pemanggilan yang memicu **Exception**.
#     -   **ATURAN FORMAT (WAJIB):**
#         1.  Jika ada **beberapa** contoh, pisahkan dengan **baris kosong**.
#         2.  Sangat dianjurkan untuk menyertakan **komentar ringkas dan to-the-point** (diawali `#`) di atas setiap contoh untuk menjelaskannya.

# VERSION V1 FORMATING NUMPY OUTPUT
# Ganti implementasi get_formatted_documentation Anda:
      # def get_formatted_documentation(self, doc: NumpyDocstring) -> str:
      #    """
      #    Merender objek NumpyDocstring yang terstruktur menjadi string
      #    docstring berformat NumPyDoc yang valid.
      #    """
         
      #    # Helper untuk memformat satu parameter
      #    def format_param(p: DocstringParameter) -> str:
      #       # Mengurus tipe dan default
      #       type_str = f" : {p.type}" if p.type else ""
      #       default_str = f", default={p.default}" if p.default is not None else ""
      #       return f"{p.name}{type_str}{default_str}\n    {p.description}"

      #    # Helper untuk memformat nilai kembali
      #    def format_return(r: DocstringReturn) -> str:
      #       name_str = f"{r.name} : " if r.name else ""
      #       return f"{name_str}{r.type}\n    {r.description}"

      #    # Helper untuk memformat bagian (section)
      #    def build_section(title: str, items: Optional[List[Any]], formatter_func) -> List[str]:
      #       if not items:
      #          return []
      #       lines = [f"\n{title}", "-" * len(title)]
      #       lines.extend([formatter_func(item) for item in items])
      #       return lines

      #    # Helper untuk bagian teks bebas
      #    def build_text_section(title: str, content: Optional[str]) -> List[str]:
      #       if not content:
      #          return []
      #       return [f"\n{title}", "-" * len(title), content]
         
      #    # --- Mulai Membangun Docstring ---
      #    docstring_lines = []
         
      #    # 1. Short Summary
      #    docstring_lines.append(doc.short_summary) 

      #    # 3. Extended Summary
      #    if doc.extended_summary:
      #       docstring_lines.append(f"\n{doc.extended_summary}") 

      #    # 4. Parameters
      #    docstring_lines.extend(build_section("Parameters", doc.parameters, format_param)) 

      #    # Bagian Khusus Kelas
      #    docstring_lines.extend(build_section("Attributes", doc.attributes, format_param)) 
      #    if doc.methods:
      #       method_lines = [f"{m['name']}\n    {m['description']}" for m in doc.methods]
      #       docstring_lines.extend(["\nMethods", "-------", *method_lines]) 

      #    # 5. Returns
      #    docstring_lines.extend(build_section("Returns", doc.returns, format_return)) 
         
      #    # 6. Yields
      #    docstring_lines.extend(build_section("Yields", doc.yields, format_return)) 

      #    # 7. Receives
      #    docstring_lines.extend(build_section("Receives", doc.receives, format_param)) 

      #    # 9. Raises
      #    if doc.raises:
      #       raise_lines = [f"{r.error}\n    {r.description}" for r in doc.raises]
      #       docstring_lines.extend(["\nRaises", "------", *raise_lines]) 

      #    # 12. See Also
      #    if doc.see_also:
      #       see_also_lines = [f"{s['name']} : {s['description']}" for s in doc.see_also]
      #       docstring_lines.extend(["\nSee Also", "--------", *see_also_lines]) 

      #    # 13. Notes
      #    docstring_lines.extend(build_text_section("Notes", doc.notes)) 

      #    # 15. Examples
      #    docstring_lines.extend(build_text_section("Examples", doc.examples)) 

      #    # (Saya melewatkan beberapa bagian opsional seperti Warns, Other Params untuk keringkasan,
      #    # tetapi Anda dapat menambahkannya dengan pola yang sama)

      #    # --- Gabungkan semuanya ---
      #    # Ini adalah docstring_content yang SEKARANG DI-RENDER, bukan di-generate
      #    final_docstring_content = "\n".join(docstring_lines)
         
      #    # Mengembalikan format akhir Anda (yang juga bisa Anda sesuaikan)
      #    return final_docstring_content.strip()



# V1 VERSION WRITER COMPONENT 
# class Writer(BaseAgent):
      
#       def __init__(self, config_path: Optional[str] = None):
#          """Inisialisasi Writer, memuat semua template prompt."""
#          super().__init__("Writer", config_path=config_path)
         
#          # Base prompt dan prompt spesifik dimuat sekali saat inisialisasi
#          self.system_prompt_template: str = """You are a precise "Documentation Content Generator" AI. Your task is to generate a structured JSON object containing documentation content for a given Python component.
# """
         
#          self.rules_for_function_template: str = """**TASK: Generate Documentation Content for a Function/Method**
# """

#          self.rules_for_class_template: str = """**TASK: Generate Documentation Content for a Class**
# """
         
#          # Prompt Koreksi (Poin 3)
#          self.correction_prompt_template: ChatPromptTemplate = ChatPromptTemplate.from_messages([
#             ("system", 
#                "You are a JSON correction expert. A previous AI's attempt to generate a valid JSON object failed. "
#                "Your task is to fix the provided malformed JSON based on the given parsing error. "
#                "You MUST ONLY output the corrected, VALID JSON object based on the Pydantic schema. Do not add any other text or explanations."),
#             ("human", 
#                "CORRECTION TASK:\n\n"
#                "PARSING ERROR:\n---\n{error_message}\n---\n\n"
#                "MALFORMED JSON:\n---\n{bad_output}\n---")
#          ])
         
#          self.json_parser = PydanticOutputParser(pydantic_object=NumpyDocstring)
#          self.main_llm = self.llm 
#          self.corrector_llm = self.llm 
         
#          # Chain akan dibuat saat inisialisasi atau sebelum pemanggilan pertama
#          self.full_writer_chain: Optional[Runnable] = self._setup_writer_chain() # Poin 2
         
         
#       def _get_specific_prompt(self, type: str) -> str:
#          """Memilih prompt yang sesuai (kelas atau fungsi/metode)."""
#          is_class = type.lower() == "class"
#          return self.rules_for_class_template if is_class else self.rules_for_function_template


#       def _get_main_prompt(self) -> ChatPromptTemplate:
#          """Menyusun prompt utama Writer."""
         
#          # Template utama akan membutuhkan input dari state:
#          # 1. focal_component, 2. context, 3. specific_rules, 4. format_instructions
         
#          system_msg = self.system_prompt_template + (
#             "\n\nOUTPUT FORMAT INSTRUCTIONS (JSON):\n---\n{format_instructions}\n---"
#          )
         
#          human_msg = """Available Context: {context}

# {specific_rules}

# Now, generate a high-quality JSON documentation for the following Code Component based on the Available Context.
# You MUST only output the JSON object.
# ```python
# {focal_component}
# ```
#          """
         
#          return ChatPromptTemplate.from_messages([
#             ("system", system_msg),
#             ("human", human_msg),
#          ])

#       def _setup_writer_chain(self) -> Runnable:
#          """Membangun LCEL chain dengan mekanisme Koreksi Diri (2-tingkat)."""
         
#          # --- Chain Koreksi Diri ---
#          # Chain ini dijalankan jika parsing gagal. Outputnya harus JSON yang valid.
#          # Input: dict{'bad_output': str, 'error_message': str, 'context': str}
         
#          correction_chain = (
#             self.correction_prompt_template
#             | self.corrector_llm
#             | self.json_parser # Coba parse lagi setelah dikoreksi
#          )
         
#          # --- Chain Utama ---
         
#          main_prompt = self._get_main_prompt()
         
#          # Langkah Parsing Awal dengan Fallback (total 2 upaya parsing)
#          parsing_step_with_fallback = (
#             # Panggil LLM utama
#             self.main_llm 
#             | self.json_parser.with_fallbacks([correction_chain])
#          )

#          format_instructions = self.json_parser.get_format_instructions()
#          # Langkah Pre-processing: Mengumpulkan semua input yang diperlukan
#          pre_process_step = RunnablePassthrough.assign(
#             specific_rules=lambda x: self._get_specific_prompt(x["component"].component_type),
#             context=lambda x: x.get("context", "No context was gathered."),
#             format_instructions=lambda x: format_instructions,
#             # focal_component sudah ada di state
#          )
         
#          def print_prompt_and_pass(prompt_value):
#             """Mengambil PromptValue, mencetaknya, dan meneruskannya."""
#             with open(DUMMY_TESTING_DIRECTORY / f"DocPrompt_{random.randint(1, 1000)}.txt", "w", encoding="utf-8") as f:
#                json.dump(prompt_value.to_string(), f, indent=4, ensure_ascii=False)
#             return prompt_value # PENTING: Meneruskan PromptValue ke LLM
         
#          # Full Chain (Input: state | Output: DocstringOutput object)
#          full_chain = (
#             pre_process_step 
#             | main_prompt         # Prompt siap dengan semua variabel
#             | RunnableLambda(print_prompt_and_pass)
#             | parsing_step_with_fallback
#          )
         
#          return full_chain
         
      
#       # Ganti implementasi get_formatted_documentation Anda:
#       def get_formatted_documentation(self, doc: NumpyDocstring) -> str:
#          ...

#       def process(self, state: AgentState) -> AgentState:

#          print("[Writer]: Run - Generating docstring ...")

#          # Pastikan chain sudah di-setup
#          if not self.full_writer_chain:
#             self.full_writer_chain = self._setup_writer_chain()

#          config = {"tags": [self.name], "callbacks": state["callbacks"]}
         
#          # Hapus pesan user/assistant yang mungkin ada dari Reader atau langkah sebelumnya
#          self._memory = []
         
#          parsed_output: Optional[NumpyDocstring] = None
#          try:
#             # Invocation
#             # Input ke chain adalah dictionary state
#             parsed_output = self.full_writer_chain.invoke(state, config=config)
            
#             with open(DUMMY_TESTING_DIRECTORY / f"DocJSONResponse_{random.randint(1, 1000)}.json", "w", encoding="utf-8") as f:
#                json.dump(parsed_output.model_dump(), f, indent=4, ensure_ascii=False)
            
            
#             # Format output (Poin 4: Berhasil)
#             state["documentation_json"] = parsed_output
#             state['docstring'] = self.get_formatted_documentation(parsed_output)
            
#          except (OutputParserException, Exception) as e: 
#             # Kegagalan Total (Setelah 2 upaya gagal)
#             print(f"[CRITICAL FAILURE]: Writer Agent failed after all retries. Error: {str(e)}")
#             print(traceback.format_exc())
            
#             # FINAL FALLBACK (Poin 4: Gagal)
#             # Kita menggunakan string kesalahan sebagai formatted_documentation
#             error_docstring = f"""
#    !!! DOCSTRING GENERATION FAILED !!!
#    The Writer Agent failed to produce valid structured output after all correction attempts.
#    Error Type: {type(e).__name__}
#    Manual Review is required for component: {state['component'].id}
#             """
            
#             state['docstring'] = error_docstring

#          return state


# BASE VERSION WRITER
# class Writer(BaseAgent):
#     """
#     Agen Writer yang menghasilkan docstring berkualitas tinggi berdasarkan
#     kode dan konteks yang disediakan dalam AgentState.
#     """
    
#     def __init__(self, config_path: Optional[str] = None):
#          """Inisialisasi Writer, memuat semua template prompt."""
#          super().__init__("Writer", config_path=config_path)
         
#          # Base prompt dan prompt spesifik dimuat sekali saat inisialisasi
#          self.base_prompt = """You are a Writer agent responsible for generating high-quality 
#          docstrings that are both complete and helpful. Accessible context is provided to you for 
#          generating the docstring.
         
#          General Guidelines:
#          1. Make docstrings actionable and specific:
#             - Focus on practical usage
#             - Highlight important considerations
#             - Include warnings or gotchas
         
#          2. Use clear, concise language:
#             - Avoid jargon unless necessary
#             - Use active voice
#             - Be direct and specific
         
#          3. Type Information:
#             - Include precise type hints
#             - Note any type constraints
#             - Document generic type parameters
         
#          4. Context and Integration: 
#             - Explain component relationships
#             - Note any dependencies
#             - Describe side effects
         
#          5. Follow Google docstring format:
#             - Use consistent indentation
#             - Maintain clear section separation
#             - Keep related information grouped"""
         
#          self.class_prompt = """You are documenting a CLASS. Focus on describing the object it represents 
#          and its role in the system.

#          Required sections:
#          1. Summary: 
#             - One-line description focusing on WHAT the class represents
#             - Avoid repeating the class name or obvious terms
#             - Focus on the core purpose or responsibility
         
#          2. Description: 
#             - WHY: Explain the motivation and purpose behind this class
#             - WHEN: Describe scenarios or conditions where this class should be used
#             - WHERE: Explain how it fits into the larger system architecture
#             - HOW: Provide a high-level overview of how it achieves its purpose
         
#          3. Example: 
#             - Show a practical, real-world usage scenario
#             - Include initialization and common method calls
#             - Demonstrate typical workflow

#          Conditional sections:
#          1. Parameters (if class's __init__ has parameters):
#             - Focus on explaining the significance of each parameter
#             - Include valid value ranges or constraints
#             - Explain parameter relationships if they exist
         
#          2. Attributes:
#             - Explain the purpose and significance of each attribute
#             - Include type information and valid values
#             - Note any dependencies between attributes"""
         
#          self.function_prompt = """You are documenting a FUNCTION or METHOD. Focus on describing 
#          the action it performs and its effects.

#          Required sections:
#          1. Summary:
#             - One-line description focusing on WHAT the function does
#             - Avoid repeating the function name
#             - Emphasize the outcome or effect
         
#          2. Description:
#             - WHY: Explain the purpose and use cases
#             - WHEN: Describe when to use this function
#             - WHERE: Explain how it fits into the workflow
#             - HOW: Provide high-level implementation approach

#          Conditional sections:
#          1. Args (if present):
#             - Explain the significance of each parameter
#             - Include valid value ranges or constraints
#             - Note any parameter interdependencies
         
#          2. Returns:
#             - Explain what the return value represents
#             - Include possible return values or ranges
#             - Note any conditions affecting the return value
         
#          3. Raises:
#             - List specific conditions triggering each exception
#             - Explain how to prevent or handle exceptions
         
#          4. Examples (if not abstract):
#             - Show practical usage scenarios
#             - Include common parameter combinations
#             - Demonstrate error handling if relevant"""
         
#          # Inisialisasi memori dengan prompt sistem dasar
#          self.add_to_memory("system", self.base_prompt)
#          self.start_tag = "<DOCSTRING>"
#          self.end_tag = "</DOCSTRING>"

#     def _is_class_component(self, code: str) -> bool:
#         """Menentukan apakah komponen kode adalah sebuah kelas."""

#         return code.strip().startswith("class ")

#     def _get_specific_prompt(self, code: str) -> str:
#         """Memilih prompt yang sesuai (kelas atau fungsi/metode)."""

#         is_class = self._is_class_component(code)
#         additional_prompt = self.class_prompt if is_class else self.function_prompt
#         return additional_prompt

#     def _extract_docstring(self, response: str) -> str:
#          """Mengekstrak docstring dari tag XML di dalam respons LLM."""

#          print(response)
#          match = re.search(rf'{self.start_tag}(.*?){self.end_tag}', response, re.DOTALL)
#          if match:
#                return match.group(1).strip()
#          else:
#                # Fallback jika tag tidak ditemukan, kembalikan seluruh respons
#                print("[Writer]: Docstring tags not found, returning full response.")
#                return response.strip()

#     def process(self, state: AgentState) -> AgentState:
#          """
#          Menjalankan proses pembuatan docstring dan memperbarui state.
#          """
#          print("[Writer]: Run - Generating docstring ...")
         
#          focal_component = state["focal_component"]
#          context = state["context"]
         
#          # 1. Susun pesan user dengan menggabungkan konteks, prompt spesifik, dan kode
#          task_description = f"""
#          Available context:
#          {context if context else "No context was gathered."}

#          {self._get_specific_prompt(focal_component)}

#          Now, generate a high-quality documentation for the following Code Component based on the Available context:
         
#          <FOCAL_CODE_COMPONENT>
#          {focal_component}
#          </FOCAL_CODE_COMPONENT>

#          Keep in mind:
#          1. Generate docstring between XML tag: <DOCSTRING> and </DOCSTRING>
#          2. Do not add triple quotes (\"\"\") to your generated docstring.
#          3. Always double check if the generated docstring is within the XML tags.
#          """
         
#          # 2. Kelola memori: hapus pesan user sebelumnya, lalu tambahkan yang baru
#          self._memory = [msg for msg in self._memory if msg.type != "human"]
#          self.add_to_memory("user", task_description)
         
#          # 3. Hasilkan respons menggunakan LLM LangChain
#          config = {"tags": [self.name], "callbacks": state["callbacks"]}
#          full_response = self.llm.invoke(self.memory, config=config)
         
#          # 4. Ekstrak docstring bersih dari respons
#          generated_docstring = self._extract_docstring(full_response.content)
         
#          # 5. Perbarui state global dengan docstring yang dihasilkan
#          state["docstring"] = generated_docstring

#          # Tambahkan respons AI ke memori untuk konsistensi (opsional, tapi praktik yang baik)
#          self.add_to_memory("assistant", generated_docstring)
         
#          return state