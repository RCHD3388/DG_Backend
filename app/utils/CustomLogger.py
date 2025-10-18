class CustomLogger:
    def __init__(self, nama):
        self.nama = nama

    def info_print(self, text):
      print(f"IO-[{self.nama}]: {text}")
    
    def warning_print(self, text):
      print(f"WR-[{self.nama}]: {text}")
    
    def error_print(self, text):
      print(f"ER-[{self.nama}]: {text}")
