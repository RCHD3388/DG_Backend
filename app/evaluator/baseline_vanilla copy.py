hasil_gemini_fewshot = {
    "zmapsdk.api.APIServer" : """
**Summary**
Kelas server yang membungkus aplikasi FastAPI untuk menyediakan antarmuka REST API ke fungsionalitas ZMap SDK.

**Description**
`APIServer` menyederhanakan proses menjalankan server web yang mengekspos kemampuan ZMap SDK melalui HTTP. Ini menginisialisasi server Uvicorn dengan aplikasi FastAPI yang telah dikonfigurasi (`app`). Pengembang dapat membuat instance dari kelas ini dan memanggil metode `run()` untuk memulai server API dengan cepat. Kelas ini menangani konfigurasi dasar seperti host dan port, menjadikannya komponen yang mudah digunakan untuk mendeploy SDK sebagai layanan mikro.

**Parameters**
- **__init__(host: str = "127.0.0.1", port: int = 8000)**: Menginisialisasi server.
  - `host` (`str`): Alamat host untuk mengikat server.
  - `port` (`int`): Nomor port untuk mengikat server.
    """,
    "zmapsdk.core.ZMap" : """
**Summary**
Kelas utama dan titik masuk utama (*facade*) untuk berinteraksi dengan ZMap SDK.

**Description**
Kelas `ZMap` menyatukan semua komponen lain dari SDK (`ZMapRunner`, `ZMapScanConfig`, `ZMapInput`, `ZMapOutput`, `ZMapParser`) ke dalam satu antarmuka yang kohesif dan mudah digunakan. Ini mengabstraksi detail tingkat rendah dari pembangunan perintah dan eksekusi subproses, menyediakan metode tingkat tinggi seperti `scan()` untuk melakukan pemindaian dengan mudah. Selain itu, ia menyediakan metode utilitas untuk berinteraksi dengan ZMap, seperti mengambil daftar modul probe yang tersedia (`get_probe_modules`), mengurai file hasil (`parse_results`), atau membuat file blocklist (`create_blocklist_file`). Pengembang harus membuat instance dari kelas ini sebagai langkah pertama untuk menggunakan SDK.

**Parameters**
- **__init__(zmap_path: str = "zmap")**: Menginisialisasi SDK.
  - `zmap_path` (`str`): Jalur ke *executable* `zmap`.

**Examples**
```python
# Inisialisasi SDK
zmap = ZMap()

# Jalankan pemindaian sederhana pada port 80 untuk subnet tertentu
results = zmap.scan(target_port=80, subnets=["192.168.1.0/24"], output_file="scan_results.csv")
print(f"Ditemukan {len(results)} host yang responsif.")

# Dapatkan versi ZMap yang terinstal
version = zmap.get_version()
print(f"Versi ZMap: {version}")

# Urai hasil dari file yang ada
parsed_data = zmap.parse_results("scan_results.csv")
print(parsed_data[0]) # Cetak hasil pertama
```
    """,
    "zmapsdk.input.ZMapInput" : """
**Summary**
Kelas yang mengelola semua aspek input untuk pemindaian ZMap, termasuk daftar target, *blocklists*, dan *allowlists*.

**Description**
Kelas `ZMapInput` mengabstraksi penanganan sumber target dan batasan pemindaian. Ini menyediakan metode untuk menentukan target baik secara langsung (melalui daftar subnet) maupun tidak langsung (melalui file input). Selain itu, kelas ini memungkinkan pembuatan dan pengelolaan file *blocklist* dan *allowlist* secara terprogram, yang sangat penting untuk memastikan pemindaian hanya menargetkan ruang jaringan yang diizinkan dan menghindari area sensitif. Metode seperti `generate_standard_blocklist` menawarkan kemudahan dengan secara otomatis membuat file yang mengecualikan rentang jaringan pribadi dan yang telah dipesan. Kelas ini digunakan untuk mempersiapkan konfigurasi input sebelum meneruskannya ke `ZMapRunner`.

**Attributes**
- **blocklist_file** (`str | None`): Jalur ke file yang berisi daftar CIDR yang akan dikecualikan dari pemindaian.
- **allowlist_file** (`str | None`): Jalur ke file yang berisi daftar CIDR yang hanya boleh dipindai.
- **input_file** (`str | None`): Jalur ke file yang berisi daftar target spesifik (IP atau subnet).
- **target_subnets** (`list[str]`): Daftar subnet target dalam notasi CIDR yang ditentukan secara langsung.
- **ignore_blocklist** (`bool`): Jika `True`, abaikan file blocklist default ZMap.
- **ignore_invalid_hosts** (`bool`): Jika `True`, abaikan entri yang tidak valid dalam file input.

**Raises**
- **ZMapInputError**: Dikeluarkan jika file yang ditentukan tidak ada, tidak dapat dibaca, atau jika format subnet/IP yang diberikan tidak valid.

    """,
    "zmapsdk.runner.ZMapRunner" : """
**Summary**
Kelas tingkat rendah yang bertanggung jawab untuk membangun dan mengeksekusi perintah `zmap` sebagai proses sub-sistem.

**Description**
`ZMapRunner` adalah jembatan antara SDK Python dan *executable* `zmap` di baris perintah. Tugas utamanya adalah mengambil objek konfigurasi Python (`ZMapScanConfig`, `ZMapInput`, `ZMapOutput`) dan menerjemahkannya menjadi argumen baris perintah yang valid untuk `zmap`. Metode `_build_command` secara dinamis membuat daftar argumen ini. Metode `run_command` menangani eksekusi subproses, menangkap `stdout` dan `stderr`, dan melaporkan kode keluar. Ini adalah komponen inti yang memungkinkan SDK untuk benar-benar menjalankan ZMap. Kelas `ZMap` yang lebih tinggi tingkatnya menggunakan `ZMapRunner` untuk melakukan semua operasi pemindaian.

**Parameters**
- **__init__(zmap_path: str = "zmap")**: Menginisialisasi *runner*.
  - `zmap_path` (`str`): Jalur ke *executable* `zmap`. Defaultnya adalah "zmap", dengan asumsi itu ada di PATH sistem.

**Raises**
- **ZMapCommandError**: Dikeluarkan jika *executable* `zmap` tidak dapat ditemukan saat inisialisasi, atau jika perintah `zmap` gagal dieksekusi (misalnya, kode keluar non-nol atau kesalahan subproses).
    """,
    "zmapsdk.core.ZMap.scan" : """
**Summary**
Melakukan pemindaian ZMap dengan parameter yang ditentukan dan mengembalikan hasilnya sebagai daftar alamat IP.

**Description**
Metode ini adalah antarmuka tingkat tinggi utama untuk memulai pemindaian. Metode ini menyederhanakan proses dengan membuat instance sementara dari `ZMapScanConfig`, `ZMapInput`, dan `ZMapOutput` untuk setiap pemindaian. Parameter yang umum digunakan seperti `target_port`, `subnets`, dan `output_file` diterima secara langsung, sementara parameter ZMap lainnya dapat diteruskan sebagai argumen kata kunci (`**kwargs`). Metode ini kemudian menggunakan `_process_scan_options` untuk mendistribusikan argumen-argumen ini ke objek konfigurasi yang sesuai sebelum mendelegasikannya ke `self.runner.scan` untuk eksekusi yang sebenarnya.

**Parameters**
- **target_port** (`int | None`): Nomor port yang akan dipindai.
- **subnets** (`list[str] | None`): Daftar subnet dalam notasi CIDR yang akan dipindai. Jika `None`, ZMap akan memindai seluruh internet (perilaku default).
- **output_file** (`str | None`): Jalur file untuk menyimpan hasil mentah. Jika tidak ditentukan, file sementara akan digunakan.
- **callback** (`Callable[[str], None] | None`): Fungsi *callback* opsional yang akan dipanggil untuk setiap baris output `stdout` secara *real-time*.
- ****kwargs** (`Any`): Parameter tambahan yang akan diteruskan langsung ke ZMap. Nama parameter harus cocok dengan opsi baris perintah ZMap (misalnya, `bandwidth="10M"`, `rate=1000`).

**Returns**
- **list[str]**: Daftar alamat IP yang merespons probe pemindaian.

**See Also**
- `zmapsdk.runner.ZMapRunner.scan`: Metode yang mendasari yang benar-benar menjalankan perintah.
- `zmapsdk.core.ZMap._process_scan_options`: Metode internal yang digunakan untuk memilah `**kwargs`.
    """,
    "zmapsdk.runner.ZMapRunner.run_command" : """
**Summary**
Mengeksekusi perintah `zmap` dengan parameter gabungan dari objek konfigurasi dan argumen kata kunci, mengembalikan output mentah.

**Description**
Ini adalah metode inti untuk mengeksekusi *executable* `zmap`. Metode ini pertama-tama menggabungkan semua parameter dari objek `config`, `input_config`, `output_config`, dan `kwargs` tambahan ke dalam satu kamus. Kamus ini kemudian digunakan oleh `_build_command` untuk membuat perintah baris perintah yang sebenarnya. Metode ini menangani dua mode eksekusi: jika `callback` disediakan, metode ini menggunakan `subprocess.Popen` untuk melakukan *streaming* output `stdout` secara *real-time`; jika tidak, metode ini menggunakan `subprocess.run` untuk mengeksekusi perintah dan menangkap semua output setelah selesai.

**Parameters**
- **config** (`ZMapScanConfig | None`): Objek konfigurasi pemindaian.
- **input_config** (`ZMapInput | None`): Objek konfigurasi input.
- **output_config** (`ZMapOutput | None`): Objek konfigurasi output.
- **capture_output** (`bool`): Jika `True`, `stdout` dan `stderr` akan ditangkap dan dikembalikan.
- **callback** (`Callable[[str], None] | None`): Fungsi *callback* untuk pemrosesan output `stdout` secara *real-time*.
- ****kwargs**: Argumen kata kunci tambahan untuk perintah `zmap`.

**Returns**
- **tuple[int, str, str]**: Sebuah tuple yang berisi (kode keluar, output standar, output error).

**Raises**
- **ZMapCommandError**: Jika terjadi kesalahan `SubprocessError` selama eksekusi.
    """,
    "zmapsdk.parser.ZMapParser.parse_csv_results" : """
**Summary**
Mem-parsing file hasil ZMap berformat CSV dan mengembalikannya sebagai daftar kamus.

**Description**
Metode statis ini dirancang untuk menangani berbagai format CSV yang dapat dihasilkan ZMap. Jika file berisi baris header, metode ini secara otomatis menggunakannya untuk kunci kamus. Jika tidak ada header tetapi parameter `fields` disediakan, parameter tersebut akan digunakan sebagai nama kolom. Jika file hanya berisi satu kolom (biasanya hanya alamat IP), metode ini akan memperlakukannya sebagai bidang `saddr`. Logika ini membuatnya fleksibel untuk menangani berbagai output ZMap.

**Parameters**
- **file_path** (`str`): Jalur ke file CSV hasil.
- **fields** (`list[str] | None`): Daftar nama bidang yang akan digunakan jika file tidak memiliki header.

**Returns**
- **list[dict[str, str]]**: Daftar kamus, di mana setiap kamus mewakili satu baris dari file hasil.

**Raises**
- **ZMapParserError**: Jika file tidak ditemukan, tidak dapat dibaca, atau jika terjadi ketidakcocokan antara jumlah kolom dan bidang yang disediakan. 
    """,
    "zmapsdk.parser.ZMapParser.stream_results" : """
**Summary**
Melakukan *streaming* hasil dari file CSV baris demi baris tanpa memuat seluruh file ke dalam memori.

**Description**
Metode ini sangat penting untuk menangani file hasil yang sangat besar yang mungkin tidak muat di RAM. Metode ini berfungsi sebagai *generator*, membuka file dan menghasilkan (`yield`) setiap baris sebagai kamus satu per satu. Logika untuk menentukan header atau menggunakan bidang yang disediakan identik dengan `parse_csv_results`, tetapi implementasinya dirancang untuk efisiensi memori.

**Parameters**
- **file_path** (`str`): Jalur ke file CSV hasil.
- **fields** (`list[str] | None`): Daftar nama bidang yang akan digunakan jika file tidak memiliki header.

**Returns**
- **Iterator[dict[str, str]]**: Sebuah iterator yang menghasilkan satu kamus untuk setiap baris dalam file hasil.

**Raises**
- **ZMapParserError**: Jika file tidak ditemukan atau tidak dapat dibaca.
    """,
}

hasil_chatgpt_fewshot = {
    "zmapsdk.api.APIServer" : """
## **Graph Ketergantungan**

* **Digunakan oleh:**

  * `cli.py` saat menjalankan server API.
* **Bergantung pada:**

  * `FastAPI`
  * `ZMap`
  * `ZMapParser`
  * `ZMapInput`, `ZMapScanConfig`, `ZMapOutput`
  * Pydantic models (schemas.py)

Diagram:

```
CLI → APIServer → FastAPI → ZMap → ZMapRunner / ZMapParser / ZMapInput / Output / Config
```

---
## **Summary**

Wrapper yang membuat server FastAPI untuk mengekspos fungsi ZMap sebagai REST API.

---

## **Description**

`APIServer` mengelola:

* inisialisasi aplikasi FastAPI,
* pendaftaran seluruh endpoint (root, probe modules, output modules, scan, metadata parsing, dll.),
* penyimpanan satu instance ZMap di `app.state.zmap`,
* menjalankan server pada host/port tertentu.

Ini memungkinkan ZMap dijalankan sebagai layanan scanning network berbasis API.

    """,
    "zmapsdk.core.ZMap" : """
### Graph Ketergantungan

* **Bergantung pada:**

  * `ZMapRunner` → eksekusi perintah `zmap` di sistem.
  * `ZMapScanConfig` → konfigurasi inti (rate, bandwidth, target_port, dsb.).
  * `ZMapInput` → konfigurasi input (blocklist, allowlist, target_subnets, dsb.).
  * `ZMapOutput` → konfigurasi output (file hasil, log, metadata).
  * `ZMapParser` → parsing hasil scan (CSV/JSON) & metadata.
* **Digunakan oleh:**

  * `zmapsdk.api` → endpoint FastAPI menyimpan instance `ZMap` pada `app.state.zmap`.
  * `zmapsdk.cli` → `print_version()` dan fitur lain dapat membuat instance `ZMap`.

Diagram singkat:

`APIServer / CLI` → **ZMap**
**ZMap** → `ZMapRunner`, `ZMapScanConfig`, `ZMapInput`, `ZMapOutput`, `ZMapParser`

Summary
Kelas utama SDK yang menyajikan antarmuka tingkat tinggi untuk menjalankan ZMap, mengelola konfigurasi input/output, serta memparsing hasil scan.

Description
ZMap adalah façade/entry point utama bagi developer yang ingin berinteraksi dengan zmap melalui Python. Kelas ini menyatukan:
- konfigurasi scan (ZMapScanConfig),
- konfigurasi input (ZMapInput),
- konfigurasi output (ZMapOutput),
- eksekusi perintah zmap (ZMapRunner),
- parsing output & metadata (ZMapParser).
Dengan memanfaatkan ZMap, pengguna dapat:
- menjalankan scan cepat via scan(),
- mengeksekusi perintah ZMap bebas melalui run(),
- membuat file blocklist/allowlist/target,
- mengambil daftar probe modules, output modules, output fields, dan interfaces,
- memproses hasil scan dari file.
- ZMap cocok digunakan baik di kode aplikasi Python, CLI, maupun API (FastAPI) karena menyembunyikan detail pemanggilan subprocess dan manipulasi file.

Attributes
runner (ZMapRunner)
Objek eksekutor ZMap yang menjalankan perintah zmap di OS.

config (ZMapScanConfig)
Konfigurasi default untuk scan (dapat digunakan ulang atau diabaikan saat scan membuat konfigurasi baru).

input (ZMapInput)
Handler default untuk konfigurasi input (blocklist, allowlist, target file).

output (ZMapOutput)
Handler default untuk konfigurasi output (file hasil, log, metadata).
    """,
    "zmapsdk.input.ZMapInput" : """
## **Graph Ketergantungan**

* **Digunakan oleh:**

  * `ZMap._process_scan_options`
  * `ZMap.blocklist_from_file`
  * `ZMap.allowlist_from_file`
  * `ZMap.create_blocklist_file`
  * `ZMap.create_allowlist_file`
  * `ZMap.create_target_file`
  * `ZMapRunner.build_scan_command`
* **Bergantung pada:**

  * `ipaddress`
  * `ZMapInputError`

Diagram:

```
ZMap → ZMapInput → File Handling / IP Validation → ZMapRunner
```

---

## **Summary**

Mengelola konfigurasi input ZMap seperti target subnet, blocklist, allowlist, dan input file.

---

## **Description**

`ZMapInput` bertanggung jawab untuk:

* validasi file blocklist/allowlist,
* validasi subnet dan IP,
* pembuatan file blocklist/allowlist/target,
* menyediakan path file kepada ZMapRunner.

Semua parameter input seperti:

* `--blocklist-file`,
* `--allowlist-file`,
* `--input-file`,

diterjemahkan oleh kelas ini ke dalam struktur yang siap digunakan oleh ZMap.

    """,
    "zmapsdk.runner.ZMapRunner" : """
## **Graph Ketergantungan**

* **Digunakan oleh:**

  * `ZMap.scan()`
  * `ZMap.run()`
  * `ZMap.get_probe_modules()`
  * `ZMap.get_output_modules()`
  * `ZMap.get_output_fields()`
  * `ZMap.get_interfaces()`
  * `ZMap.get_version()`

* **Bergantung pada:**

  * `subprocess`
  * `ZMapScanConfig`
  * `ZMapInput`
  * `ZMapOutput`
  * `ZMapParser`
  * `ZMapCommandError`, `ZMapParserError`

Diagram relasi:

```
ZMap → ZMapRunner → (Subprocess: zmap)
                  → ZMapParser
                  → ZMapScanConfig / ZMapInput / ZMapOutput
```
---

## **Summary**

Executor utama yang membangun perintah ZMap, menjalankannya melalui subprocess, melakukan streaming output, serta memproses file hasil scan dan metadata.

---

## **Description**

`ZMapRunner` merupakan kelas inti yang menghubungkan SDK Python dengan executable `zmap` di sistem operasi. Tugas utama kelas ini:

1. **Membangun command line ZMap** berdasarkan konfigurasi yang diberikan.
2. **Menjalankan proses ZMap** menggunakan `subprocess.Popen`.
3. **Streaming output** secara real-time ke callback.
4. **Mengisi file metadata, logging, dan output** sesuai konfigurasi.
5. **Mem-parse hasil scan** dan mengembalikan daftar alamat IP.
6. Memberikan utilitas untuk:

   * mengambil daftar modul probe,
   * daftar modul output,
   * field output,
   * versi ZMap,
   * daftar interface jaringan.

Kelas ini menyembunyikan seluruh detail eksekusi sistem (subprocess, file handling) dari developer.

    """,
    "zmapsdk.core.ZMap.scan" : """
### Graph Ketergantungan

* Menggunakan:

  * `ZMapScanConfig`, `ZMapInput`, `ZMapOutput` (instance baru per pemanggilan).
  * `ZMap._process_scan_options()` untuk mendistribusikan `**kwargs`.
  * `ZMapRunner.scan()` untuk eksekusi scan dan pembacaan hasil.
* Relasi alur:

`ZMap.scan()` → `_process_scan_options()` → `scan_config / scan_input / scan_output`
`ZMap.scan()` → `ZMapRunner.scan(config, input_config, output_config, callback)` → daftar IP.
### Summary

Menjalankan scan ZMap dengan konfigurasi yang diberikan dan mengembalikan daftar IP yang merespons.

### Description

Metode ini merupakan cara utama untuk melakukan scan jaringan melalui SDK. Ia:

1. Membuat objek konfigurasi lokal (`scan_config`, `scan_input`, `scan_output`).
2. Mengisi parameter inti: `target_port`, `subnets`, `output_file`.
3. Mengirim `**kwargs` ke `_process_scan_options()` untuk diarahkan ke konfigurasi yang tepat.
4. Memanggil `self.runner.scan(...)` yang:

   * membangun command line ZMap,
   * menjalankan perintah,
   * membaca file output,
   * mengembalikan daftar IP.

Dengan pendekatan ini, setiap pemanggilan `scan()` tidak bergantung pada state `self.config/self.input/self.output`, sehingga aman untuk penggunaan berulang dan paralel (selama `output_file` dipisah).

### Parameters

* **target_port (int | None)**
  Port tujuan yang akan discan. Jika `None`, ZMap akan menggunakan default modul/probe yang ditentukan oleh konfigurasi di `kwargs`.

* **subnets (list[str] | None)**
  Daftar subnet (CIDR) target, misalnya `["192.168.0.0/24"]`. Jika `None`, ZMap akan mengikuti default (bisa jadi “internet luas” tergantung konfigurasi ZMap).

* **output_file (str | None)**
  Path file hasil scan. Jika `None`, `ZMapRunner.scan()` akan membuat file sementara dan menghapusnya setelah selesai.

* **callback (Callable[[str], None] | None)**
  Fungsi *callback* opsional yang dipanggil setiap kali ada output baru dari ZMap selama proses scan. Cocok untuk update progres real time.

* **kwargs (Any)**
  Argumen tambahan untuk ZMap, misalnya:

  * `bandwidth`, `rate`, `max_targets`, `blocklist_file`, `output_fields`, dll.
    Penempatan argumen ini akan dipetakan otomatis oleh `_process_scan_options()`.

### Returns

* **list[str]**
  Daftar alamat IP (string) yang terdeteksi merespons scan, biasanya berdasarkan field `saddr`.

### Raises

* Dapat melempar:

  * `ZMapCommandError` dari `ZMapRunner.scan()` jika perintah `zmap` gagal.
  * `ZMapConfigError`, `ZMapInputError`, `ZMapOutputError` secara tidak langsung apabila konfigurasi yang dibuat tidak valid (tergantung nilai `kwargs` dan path file).

### Example

```python
from zmapsdk import ZMap

zmap = ZMap()

ips = zmap.scan(
    target_port=80,
    subnets=["192.168.1.0/24"],
    bandwidth="10M",
    rate=1000,
)

print(f"Total IP terbuka di port 80: {len(ips)}")
for ip in ips[:10]:
    print(ip)
```
    """,
    "zmapsdk.runner.ZMapRunner.run_command" : """
### **Summary**

Menjalankan ZMap dengan parameter mentah (mirip CLI manual).

### **Returns**

* `(returncode, stdout, stderr)`
    """,
    "zmapsdk.parser.ZMapParser.parse_csv_results" : """
### **Summary**

Memparsing file hasil ZMap CSV menjadi list dictionary.

### **Description**

Metode ini:

1. Membuka file hasil (biasanya `results.csv`).
2. Mendeteksi apakah ada header:

   * Jika header ada, nama kolom otomatis dipakai.
   * Jika tidak ada header dan `fields` diberikan → gunakan `fields`.
   * Jika hanya satu kolom → diasumsikan berisi IP (`saddr`).
3. Mengembalikan list of dict, 1 dict per baris.

### **Parameters**

* `file_path (str)`
  Lokasi file CSV hasil scan.
* `fields (list[str] | None)`
  Nama field manual jika file tidak memiliki header.

### **Returns**

* `list[dict[str, str]]`

### **Raises**

* `ZMapParserError` jika format file tidak valid.

### **Example**

```python
parser = ZMapParser()
rows = parser.parse_csv_results("results.csv")
print(rows[0]["saddr"])
```
    """,
    "zmapsdk.parser.ZMapParser.stream_results" : """
### **Summary**

Melakukan streaming hasil CSV tanpa memuat seluruhnya ke memori.

### **Description**

Metode ini menghasilkan generator yang:

* Membaca file baris demi baris,
* Mengubah baris menjadi dict,
* Menggunakan header atau `fields` sesuai kebutuhan.

Cocok untuk file CSV sangat besar (puluhan GB).

### **Returns**

* `Iterator[dict[str, str]]`

### **Example**

```python
for row in ZMapParser().stream_results("results.csv"):
    print(row)
```
    """,
}


hasil_gemini_zs = {
    "zmapsdk.api.APIServer" : """
### Class `APIServer`

**Graph Ketergantungan**
- `uvicorn`
- `fastapi.FastAPI` (melalui variabel `app` global)

**Penjelasan Kode**
- **Ringkasan Singkat:** Class pembungkus (wrapper) untuk menjalankan server API.
- **Deskripsi:** Class ini menyederhanakan proses memulai server Uvicorn yang melayani aplikasi FastAPI.
    """,
    "zmapsdk.core.ZMap" : """
### Class `ZMap`

**Graph Ketergantungan**
- `zmapsdk.runner.ZMapRunner`
- `zmapsdk.config.ZMapScanConfig`
- `zmapsdk.input.ZMapInput`
- `zmapsdk.output.ZMapOutput`
- `zmapsdk.parser.ZMapParser`
- `ZMap._process_scan_options`

**Penjelasan Kode**
- **Ringkasan Singkat:** Class utama dari ZMap SDK yang berfungsi sebagai antarmuka tingkat tinggi untuk menjalankan scan dan mengelola fungsionalitas ZMap.
- **Deskripsi:** Class `ZMap` mengabstraksi interaksi langsung dengan executable ZMap. Ini menyediakan metode yang mudah digunakan untuk melakukan scan, mendapatkan informasi tentang ZMap (seperti versi, modul yang tersedia), mengelola file input (blocklist, allowlist), dan mem-parsing hasil output.
    """,
    "zmapsdk.input.ZMapInput" : """
### Class `ZMapInput`

**Graph Ketergantungan**
- `ipaddress`
- `os`
- `zmapsdk.exceptions.ZMapInputError`

**Penjelasan Kode**
- **Ringkasan Singkat:** Mengelola semua opsi dan file yang berhubungan dengan input ZMap.
- **Deskripsi:** Class ini bertanggung jawab untuk menangani target scan, baik dalam bentuk subnet yang ditambahkan secara programatik maupun dari file. Ia juga mengelola file blocklist dan allowlist, termasuk validasi file dan pembuatan file baru dari daftar subnet/IP.
    """,
    "zmapsdk.runner.ZMapRunner" : """
### Class `ZMapRunner`

**Graph Ketergantungan**
- `os`
- `subprocess`
- `tempfile`
- `psutil` (opsional, sebagai fallback)
- `socket`, `platform` (opsional, sebagai fallback)
- `zmapsdk.config.ZMapScanConfig`
- `zmapsdk.input.ZMapInput`
- `zmapsdk.output.ZMapOutput`
- `zmapsdk.exceptions.ZMapCommandError`

**Penjelasan Kode**
- **Ringkasan Singkat:** Class inti yang bertanggung jawab untuk membangun dan mengeksekusi perintah `zmap` menggunakan modul `subprocess`.
- **Deskripsi:** `ZMapRunner` adalah jembatan antara Python SDK dan executable ZMap. Ia menangani penerjemahan objek konfigurasi Python menjadi argumen command-line, menjalankan proses ZMap, menangkap outputnya, dan menangani error eksekusi.
    """,
    "zmapsdk.core.ZMap.scan" : """
#### Method `scan`
**Graph Ketergantungan**
- `zmapsdk.config.ZMapScanConfig`
- `zmapsdk.input.ZMapInput`
- `zmapsdk.output.ZMapOutput`
- `self._process_scan_options`
- `self.runner.scan`

**Penjelasan Kode**
- **Ringkasan Singkat:** Melakukan scan ZMap dengan konfigurasi yang ditentukan dan mengembalikan hasilnya.
- **Deskripsi:** Metode ini adalah cara utama untuk menjalankan scan. Metode ini membuat objek konfigurasi sementara untuk scan saat ini, menetapkan parameter inti seperti port target dan subnet, memproses opsi tambahan melalui `_process_scan_options`, dan akhirnya mendelegasikan eksekusi scan ke `ZMapRunner`.

**Parameters**
- `target_port` (`int | None`, optional): Nomor port yang akan di-scan.
- `subnets` (`list[str] | None`, optional): Daftar subnet yang akan di-scan. Jika tidak disediakan, ZMap akan men-scan seluruh internet.
- `output_file` (`str | None`, optional): File untuk menyimpan hasil output. Jika tidak disediakan, file sementara akan digunakan.
- `callback` (`Callable[[str], None] | None`, optional): Fungsi callback yang akan dipanggil untuk setiap baris output secara real-time.
- `**kwargs` (`Any`): Parameter tambahan yang akan diteruskan ke ZMap sebagai opsi command-line.

**Return Value**
- `list[str]`: Daftar alamat IP yang merespons scan.
    """,
    "zmapsdk.runner.ZMapRunner.run_command" : """
**Graph Ketergantungan**
- `self._build_command`
- `subprocess.Popen`, `subprocess.run`
- `zmapsdk.exceptions.ZMapCommandError`
**Penjelasan Kode**
- **Ringkasan Singkat:** Metode utama untuk mengeksekusi perintah ZMap.
- **Deskripsi:** Metode ini mengumpulkan semua parameter dari objek-objek konfigurasi dan `kwargs` tambahan, membangun perintah menggunakan `_build_command`, dan kemudian menjalankannya. Jika `callback` disediakan, ia menggunakan `subprocess.Popen` untuk memproses output secara real-time. Jika tidak, ia menggunakan `subprocess.run` yang lebih sederhana untuk menunggu proses selesai dan menangkap semua output sekaligus.
    """,
    "zmapsdk.parser.ZMapParser.parse_csv_results" : """
#### Method `parse_csv_results`
**Graph Ketergantungan**
- `os.path.isfile`
- `csv.DictReader`, `csv.reader`
- `zmapsdk.exceptions.ZMapParserError`
**Penjelasan Kode**
- **Ringkasan Singkat:** Mem-parsing file hasil ZMap berformat CSV.
- **Deskripsi:** Metode ini dapat menangani beberapa skenario:
    1. Jika `fields` tidak disediakan dan file memiliki header, ia akan menggunakan `csv.DictReader` untuk secara otomatis membuat dictionary.
    2. Jika `fields` disediakan, ia akan menggunakan `csv.reader` dan memetakan setiap kolom ke nama field yang sesuai.
    3. Jika file hanya berisi satu kolom (biasanya hanya alamat IP), ia akan mengasumsikan field tersebut adalah `saddr`.
    Jika terjadi kesalahan parsing, `ZMapParserError` akan dilemparkan.
    """,
    "zmapsdk.parser.ZMapParser.stream_results" : """
#### Method `stream_results`
**Graph Ketergantungan**
- `os.path.isfile`
- `csv.DictReader`, `csv.reader`
- `zmapsdk.exceptions.ZMapParserError`
**Penjelasan Kode**
- **Ringkasan Singkat:** Membaca dan menghasilkan (yield) hasil dari file CSV baris per baris.
- **Deskripsi:** Metode ini sangat berguna untuk file hasil yang sangat besar karena tidak memuat seluruh file ke dalam memori. Ia berfungsi sebagai generator, membaca file CSV baris per baris dan menghasilkan dictionary untuk setiap baris. Logikanya mirip dengan `parse_csv_results` tetapi menggunakan `yield` alih-alih membangun daftar di memori.
    """,
}

hasil_chatgpt_zs = {
    "zmapsdk.api.APIServer" : """
class APIServer:
    \"\"\"
    Server class for running the ZMap SDK API
    \"\"\"
```

Kelas pembungkus server API untuk menjalankan aplikasi FastAPI menggunakan Uvicorn.

### Dependency Graph

Memanggil:

* `uvicorn.run(app, host, port)`
* Menggunakan global: `app` FastAPI instance
    """,
    "zmapsdk.core.ZMap" : """
Kelas utama yang menyediakan antarmuka pemakaian ZMap melalui Python.
Mengelola runner, konfigurasi, input, output, serta fungsi komposit untuk scanning, parsing, dan utilitas metadata.
Dependency Graph
Memanggil komponen:
ZMapRunner
ZMapScanConfig
ZMapInput
ZMapOutput
ZMapOptionCategories
ZMapParser.parse_csv_results
ZMapParser.parse_metadata
ZMapParser.extract_ips
ZMapParser.stream_results
ZMapParser.count_results
ZMapRunner.run_command
ZMapRunner.scan
    """,
    "zmapsdk.input.ZMapInput" : """
Summary
Kelas untuk menangani input ZMap seperti subnets, blocklist, allowlist, dan file target.

Extended Summary
Kelas ini menyediakan method untuk memvalidasi subnet/IP, membuat file daftar target, dan menghasilkan konfigurasi input dalam bentuk dictionary yang siap dikirim ke runner ZMap.

Dependency Graph
Memanggil:
ipaddress.ip_network
ipaddress.ip_address
open(...)
os.path.isfile
os.access
ZMapInputError

Digunakan oleh:
ZMap.scan
ZMapRunner.run_command
ZMapRunner.scan
    """,
    "zmapsdk.runner.ZMapRunner" : """
Summary
Kelas yang mengeksekusi command ZMap dan mengelola seluruh operasi eksekusi proses.

Extended Summary
Runner ini bertanggung jawab membangun parameter eksplisit CLI, menjalankan subprocess ZMap, menangani callback streaming output, serta memproses file hasil scan.

Dependency Graph
Memanggil:
subprocess.run
subprocess.Popen
tempfile.mkstemp
os.unlink
ZMapScanConfig.to_dict
ZMapInput.to_dict
ZMapOutput.to_dict
ZMapCommandError bila gagal

Digunakan oleh:
ZMap
ZMap.api
CLI
    """,
    "zmapsdk.core.ZMap.scan" : """
## 2.2. `ZMap.scan`

```python
def scan(self, target_port=None, subnets=None, output_file=None, callback=None, **kwargs):
```

### Summary

Menjalankan pemindaian ZMap dan mengembalikan daftar IP hasil.

### Extended Summary

Metode ini membangun tiga komponen konfigurasi (config, input, output), mendistribusikan parameter tambahan ke objek konfigurasi yang tepat, lalu memanggil `ZMapRunner.scan()` untuk mengeksekusi proses scan. Hasil akhirnya berupa daftar alamat IP.

### Dependency Graph

Memanggil:

* `ZMapScanConfig()`
* `ZMapInput()`
* `ZMapOutput()`
* `ZMap._process_scan_options()`
* `ZMapRunner.scan()`

### Parameters

* **target_port** : `int | None`
* **subnets** : `list[str] | None`
* **output_file** : `str | None`
* **callback** : `Callable[[str], None] | None`
* **kwargs** : `Any`
  Parameter ekstra untuk konfigurasi ZMap.

### Returns

* `list[str]`
  Daftar IP yang merespons.

### Raises

* `ZMapCommandError` jika proses scan gagal.

---

    """,
    "zmapsdk.runner.ZMapRunner.run_command" : """
Summary
Menjalankan perintah ZMap dengan parameter yang diberikan.

Extended Summary
Mendukung callback untuk real-time output, mode capture output, dan eksekusi langsung.

Parameters
config
input_config
output_config
capture_output
callback
kwargs

Returns
tuple[int,str,str]

Raises
ZMapCommandError
    """,
    "zmapsdk.parser.ZMapParser.parse_csv_results" : """
Summary
Mem-parse file hasil CSV dari ZMap ke bentuk list dictionary.

Extended Summary
Mendeteksi apakah file memiliki header, apakah hanya 1 kolom (saddr), atau menerima field custom.

Parameters
file_path : str
fields : list[str] | None

Returns
list[dict[str,str]]

Raises
ZMapParserError
    """,
    "zmapsdk.parser.ZMapParser.stream_results" : """
Summary
Streaming hasil CSV tanpa perlu load seluruh file.

Parameters
file_path : str
fields : list[str] | None

Yields
dict[str,str]
    """,
}