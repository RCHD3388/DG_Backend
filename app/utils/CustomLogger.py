from pathlib import Path
import datetime

PROCESS_LOGS_DIRECTORY = Path(__file__).resolve().parent.parent / "process_outputs" / "process_logs"

class CustomLogger:
    def __init__(self, nama):
        self.nama = nama
        today_str = datetime.datetime.now().strftime("%d_%m_%Y_%H_%M")
        log_filename = f"PLogs_{today_str}.txt"
        
        # Gabungkan direktori dan nama file
        self.log_file = PROCESS_LOGS_DIRECTORY / log_filename
        
        # Panggil setup untuk memastikan folder ada
        self._setup_log_file()

    def _setup_log_file(self):
      """Memastikan direktori untuk file log ada."""
      try:
          log_dir = self.log_file.parent
          log_dir.mkdir(parents=True, exist_ok=True)
      except Exception as e:
          print(f"ERROR LOGGER: Gagal membuat direktori log di {log_dir}. Error: {e}")
          
    def _log_message(self, text: str):
      try:
          with open(self.log_file, 'a', encoding='utf-8') as f:
              f.write(text + '\n')
      except Exception as e:
          print(f"CRITICAL LOGGING FAILURE: Gagal menulis ke file {self.log_file}. Error: {e}")

    def info_print(self, text):
      print(f"IO-[{self.nama}]: {text}")
      self._log_message(f"IO-[{self.nama}]: {text}")
    
    def warning_print(self, text):
      print(f"WR-[{self.nama}]: {text}")
      self._log_message(f"WR-[{self.nama}]: {text}")
    
    def error_print(self, text):
      print(f"ER-[{self.nama}]: {text}")
      self._log_message(f"ER-[{self.nama}]: {text}")
