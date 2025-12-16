from dataclasses import dataclass

# Base interface (agar kita tahu apa saja yang wajib ada)
@dataclass
class PromptTemplates:
    function_rules: str
    class_rules: str

V0 = PromptTemplates(
    function_rules="""**TASK: Generate Documentation Content for a Function/Method**

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
""",
    class_rules="""**TASK: Generate Documentation Content for a Class**

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
)

# V 1
V1 = PromptTemplates(
    function_rules="""**TASK: Generate Documentation Content for a Function/Method**

You MUST analyze the code and context to fill all relevant fields in the JSON schema based on the following rules:

-   **`short_summary`**: (WAJIB) Tulis satu sampai dua kalimat deskriptif ringkas dan informatif.
    -   Fokus pada **APA** yang dilakukan atau dihasilkan fungsi.
    -   Tekankan pada **hasil atau efek utamanya**.
    -   **HINDARI** pengulangan nama fungsi.
    
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
    -   **FOKUS KONTEN (PENTING): 
        1. Fokus untuk **mengilustrasikan penggunaan** (bukan *testing*). Tunjukkan **Skenario Praktis**, **Kombinasi Parameter** umum, atau (jika relevan) pemanggilan yang memicu **Exception**.
        2. Fokus HANYA pada baris kode penggunaan komponen tersebut. **WAJIB ASUMSIKAN** semua dependensi (modul, *instance* kelas) sudah ada. **DILARANG KERAS** mendefinisikan ulang kelas/fungsi/method atau menyertakan `Mock`, `import` yang tidak perlu.
    -   **ATURAN FORMAT (WAJIB):**
        1.  Gunakan format **doctest** (dimulai dengan `>>> `).
        2.  Pisahkan **beberapa** contoh dengan **baris kosong**.
        3.  Sertakan **komentar ringkas dan to-the-point** (diawali `#`) untuk menjelaskan setiap contoh.

-   **Bagian Lain (`notes`, `see_also`, `warnings_section` - OPSIONAL):**
    -   **PERINGATAN KETAT:** HANYA isi *field-field* ini jika informasi yang relevan 100% FAKTUAL, jelas dari konteks/kode, DAN penting/krusial untuk diketahui pembaca.
    -   **Jika terdapat sedikit keraguan mengenai akurasi atau kepentingannya, JANGAN DITULIS** (biarkan *field* tersebut `null`).
""",

    class_rules="""**TASK: Generate Documentation Content for a Class**

You MUST analyze the code and context to fill all relevant fields in the JSON schema based on the following rules (standar NumPyDoc):

-   **`short_summary`**: (WAJIB) Tulis satu sampai dua kalimat deskriptif yang ringkas dan informatif.
    -   Fokus pada **APA** yang direpresentasikan oleh kelas ini (misal: "Sebuah model...", "Sebuah konfigurasi...").
    -   Tekankan pada **tujuan atau peran utamanya** dalam sistem.
    -   **HINDARI** pengulangan nama kelas.
    
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
    -   **FOKUS KONTEN (PENTING)**: 
        1. Fokus untuk **mengilustrasikan penggunaan** (bukan *testing*). Tunjukkan **Skenario Praktis**, **Kombinasi Parameter** umum, atau (jika relevan) pemanggilan yang memicu **Exception**.
        2. Fokus HANYA pada baris kode penggunaan komponen tersebut. **WAJIB ASUMSIKAN** semua dependensi (modul, *instance* kelas) sudah ada. **DILARANG KERAS** mendefinisikan ulang kelas/fungsi/method atau menyertakan `Mock`, `import` yang tidak perlu.
    -   **ATURAN FORMAT (WAJIB):**
        1.  Gunakan format **doctest** (dimulai dengan `>>> `).
        2.  Pisahkan **beberapa** contoh dengan **baris kosong**.
        3.  Sertakan **komentar ringkas dan to-the-point** (diawali `#`) untuk menjelaskan setiap contoh.

-   **Bagian Lain (`notes`, `see_also`, `warnings_section` - OPSIONAL):**
    -   **PERINGATAN KETAT:** HANYA isi *field-field* ini jika informasi yang relevan 100% faktual, jelas dari konteks/kode, DAN penting/krusial untuk diketahui pembaca.
    -   **Jika terdapat sedikit keraguan mengenai akurasi atau kepentingannya, JANGAN DITULIS** (biarkan *field* tersebut `null`).
"""
)

# V 2
V2 = PromptTemplates(
    function_rules="""**TASK: Generate Documentation Content for a Function/Method**

You MUST analyze the code and context to fill all relevant fields in the JSON schema based on the following rules:

**[ATURAN_TIPE_DATA] (Gunakan logika ini untuk semua field 'type'):**
1.  **PRIORITAS 1 (Explicit):** Salin TIPE DATA (type hint) **secara identik** dari kode. HARUS *case-sensitive* dan menyertakan semua karakter (misal: `Optional[str]`, `Dict[str, Any]`).
2.  **PRIORITAS 2 (Strict Inference):** Lakukan inferensi HANYA JIKA **100% YAKIN** berdasarkan default value atau penggunaan pada kode. Jika ragu/ambigu, **LANGSUNG LOMPAT** ke Prioritas 3.
3.  **PRIORITAS 3 (Fallback):** Gunakan "Any".

---

-   **`short_summary`**: (WAJIB) Tulis satu sampai dua kalimat deskriptif ringkas dan informatif.
    -   Fokus pada **APA** yang dilakukan atau dihasilkan fungsi.
    -   Tekankan pada **hasil atau efek utamanya**.
    -   **HINDARI** pengulangan nama fungsi.
    
-   **`extended_summary`**: (WAJIB) Tulis paragraf deskriptif yang komprehensif.
    -   Paragraf ini HARUS mengalir secara naratif (bukan poin-poin).
    -   Informasi HARUS faktual berdasarkan kode dan konteks, jangan berhalusinasi.
    -   **ATURAN UTAMA**: Fokus pada **mengklarifikasi fungsionalitas** (apa yang dilakukan kode). **HINDARI** detail implementasi atau teori dasar (simpan untuk bagian `notes` jika dibutuhkan).
    -   Secara faktual jelaskan:
        1.  **MENGAPA** (Purpose/Use Case): Apa tujuan dan kasus penggunaan utama fungsi ini?
        2.  **KAPAN** (When to Use): Kapan situasi ideal untuk menggunakan fungsi ini?
        3.  **DI MANA** (Workflow Fit): Bagaimana posisinya dalam alur kerja sistem yang lebih besar?
        
-   **`parameters`**: (PENTING) Deteksi SEMUA parameter dari signatur. 
    -  Untuk setiap parameter (JANGAN sertakan `self` atau `cls` jika merupakan method ), sediakan 'name', 'type', dan 'description'. Deskripsi HARUS mendalam dan mencakup:
    -   **ATURAN WAJIB (PENTING):**
        1.  **`name`**: (WAJIB IDENTIK) Salin NAMA parameter **secara identik** dari signatur kode. HARUS *case-sensitive* dan menyertakan awalan `*` atau `**` jika ada (misal: `*args`, `**kwargs`).
        2.  **`type`**: Terapkan **[ATURAN_TIPE_DATA]**.
        3.  **`default`**: (WAJIB IDENTIK) JIKA parameter memiliki nilai *default* yang **tertulis eksplisit** di signatur kode (misal: `param: int = 5`), Anda **WAJIB** mendeteksi nilai tersebut dan menempatkannya **secara identik** (misal: `5`, `'test'`, `True`, `[{"A": "B"}]`) di *field* `default`. Jika tidak ada *default* eksplisit, *field* ini HARUS `null`.
    -   **ATURAN KONTEN (PENTING):**
        1.  **`description`**: Deskripsi HARUS mendalam dan mencakup:
            -  **Signifikansi**: Mengapa parameter ini penting?
            -  **Batasan**: Apa rentang nilai yang valid atau *constraints*?
            -  **Interdependensi**: Apakah nilainya bergantung atau memengaruhi parameter lain? 
            
-   **`returns`**: (PENTING) Analisis nilai yang dikembalikan oleh fungsi.
    -   **ATURAN UTAMA (PENTING):**
        1.  **`type`**: Terapkan **[ATURAN_TIPE_DATA]**. Jika `void`, **TIDAK MENGEMBALIKAN NILAI**, Anda **WAJIB** menyetel *field* `returns` di JSON utama menjadi `null`.
    -   **ATURAN KONTEN (PENTING):**
        1.  **`description`**: Deskripsi HARUS mendalam dan menjelaskan:
            -  **Representasi**: Apa arti atau yang direpresentasikan oleh nilai ini?
            -  **Kemungkinan Nilai**: Apa kemungkinan nilai atau rentang spesifik yang dikembalikan?
            -  **Kondisi**: Apakah ada kondisi yang memengaruhi nilai kembalian?
    
-   **`yields`**: (KHUSUS GENERATOR) JIKA fungsi ini adalah generator (MENGGUNAKAN `yield`), analisis nilai yang di-*yield*.
    -   **ATURAN UTAMA (PENTING):**
        1.  **`type`**: Terapkan **[ATURAN_TIPE_DATA]**. 
    -   **ATURAN KONTEN:**
        1.  **`description`**: Deskripsi HARUS mendalam dan menjelaskan **Representasi**, **Kemungkinan Nilai**, dan **Kondisi** dari nilai yang di-*yield*.

-   **`receives`**: (OPTIONAL PADA GENERATOR) JIKA fungsi ini adalah generator DAN dirancang untuk menerima nilai melalui `.send()`, deteksi parameter yang diterima.
    -   **ATURAN WAJIB (PENTING):**
        1.  **`name`**: (WAJIB IDENTIK) Salin NAMA secara identik dan wajib case-sensitive sesuai yang terdapat pada code.
        2.  **`type`**: Terapkan **[ATURAN_TIPE_DATA]**.
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
    -   **FOKUS KONTEN (PENTING):** 
        1. Fokus untuk **mengilustrasikan penggunaan** (bukan *testing*). Tunjukkan **Skenario Praktis**, **Kombinasi Parameter** umum, atau (jika relevan) pemanggilan yang memicu **Exception**.
        2. Fokus HANYA pada baris kode penggunaan komponen tersebut. **WAJIB ASUMSIKAN** semua dependensi (modul, *instance* kelas) sudah ada. **DILARANG KERAS** mendefinisikan ulang kelas/fungsi/method atau menyertakan `Mock`, `import` yang tidak perlu.
    -   **ATURAN FORMAT (WAJIB):**
        1.  Gunakan format **doctest** (dimulai dengan `>>> `).
        2.  Pisahkan **beberapa** contoh dengan **baris kosong**.
        3.  Sertakan **komentar ringkas dan to-the-point** (diawali `#`) untuk menjelaskan setiap contoh.

-   **Bagian Lain (`notes`, `see_also`, `warnings_section` - OPSIONAL):**
    -   **PERINGATAN KETAT:** HANYA isi *field-field* ini jika informasi yang relevan 100% FAKTUAL, jelas dari konteks/kode, DAN penting/krusial untuk diketahui pembaca.
    -   **Jika terdapat sedikit keraguan mengenai akurasi atau kepentingannya, JANGAN DITULIS** (biarkan *field* tersebut `null`).
""",

    class_rules="""**TASK: Generate Documentation Content for a Class**

You MUST analyze the code and context to fill all relevant fields in the JSON schema based on the following rules (standar NumPyDoc):

**[ATURAN_TIPE_DATA] (Gunakan logika ini untuk semua field 'type'):**
1.  **PRIORITAS 1 (Explicit):** Salin TIPE DATA (type hint) **secara identik** dari kode. HARUS *case-sensitive* dan menyertakan semua karakter (misal: `Optional[str]`, `Dict[str, Any]`).
2.  **PRIORITAS 2 (Strict Inference):** Lakukan inferensi HANYA JIKA **100% YAKIN** berdasarkan default value atau penggunaan pada kode. Jika ragu/ambigu, **LANGSUNG LOMPAT** ke Prioritas 3.
3.  **PRIORITAS 3 (Fallback):** Gunakan "Any".

---

-   **`short_summary`**: (WAJIB) Tulis satu sampai dua kalimat deskriptif yang ringkas dan informatif.
    -   Fokus pada **APA** yang direpresentasikan oleh kelas ini (misal: "Sebuah model...", "Sebuah konfigurasi...").
    -   Tekankan pada **tujuan atau peran utamanya** dalam sistem.
    -   **HINDARI** pengulangan nama kelas.
    
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
        2.  **JIKA `__init__` MANUAL DITEMUKAN:** Anda **WAJIB** mendokumentasikan SEMUA parameter dari `__init__` manual tersebut di sini, dengan mengikuti ATURAN di bawah.
            -   **ATURAN WAJIB (PENTING):**
                1.  **`name`**: (WAJIB IDENTIK) Salin NAMA parameter **secara identik** dari signatur `__init__`. HARUS *case-sensitive* dan menyertakan awalan `*` atau `**` jika ada. (Abaikan `self`).
                2.  **`type`**: Terapkan **[ATURAN_TIPE_DATA]**.
                3.  **`default`**: (WAJIB IDENTIK) JIKA parameter memiliki nilai *default* yang **tertulis eksplisit** di signatur kode (misal: `param: int = 5`), Anda **WAJIB** mendeteksi nilai tersebut dan menempatkannya **secara identik** (misal: `5`, `'test'`, `True`, `[{"A": "B"}]`) di *field* `default`. Jika tidak ada *default* eksplisit, *field* ini HARUS `null`.
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
        2.  **`type`**: Terapkan **[ATURAN_TIPE_DATA]**.
        3.  **`default`**: (WAJIB IDENTIK) JIKA atribut memiliki nilai *default* yang **tertulis eksplisit**, Anda **WAJIB** mendeteksi nilai tersebut dan menempatkannya **secara identik** di *field* `default`. Jika tidak ada *default*, maka *field* ini HARUS `null`.
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
    -   **FOKUS KONTEN (PENTING)**: 
        1. Fokus untuk **mengilustrasikan penggunaan** (bukan *testing*). Tunjukkan **Skenario Praktis**, **Kombinasi Parameter** umum, atau (jika relevan) pemanggilan yang memicu **Exception**.
        2. Fokus HANYA pada baris kode penggunaan komponen tersebut. **WAJIB ASUMSIKAN** semua dependensi (modul, *instance* kelas) sudah ada. **DILARANG KERAS** mendefinisikan ulang kelas/fungsi/method atau menyertakan `Mock`, `import` yang tidak perlu.
    -   **ATURAN FORMAT (WAJIB):**
        1.  Gunakan format **doctest** (dimulai dengan `>>> `).
        2.  Pisahkan **beberapa** contoh dengan **baris kosong**.
        3.  Sertakan **komentar ringkas dan to-the-point** (diawali `#`) untuk menjelaskan setiap contoh.

-   **Bagian Lain (`notes`, `see_also`, `warnings_section` - OPSIONAL):**
    -   **PERINGATAN KETAT:** HANYA isi *field-field* ini jika informasi yang relevan 100% faktual, jelas dari konteks/kode, DAN penting/krusial untuk diketahui pembaca.
    -   **Jika terdapat sedikit keraguan mengenai akurasi atau kepentingannya, JANGAN DITULIS** (biarkan *field* tersebut `null`).
"""
)

AVAILABLE_VERSIONS = {
    "v0": V0,
    "v1": V1,
    "v2": V2
}