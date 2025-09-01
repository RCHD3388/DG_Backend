from pydantic import BaseModel
class AnalysisStartSuccessData(BaseModel):
    """
    Mendefinisikan struktur 'data' untuk respons sukses saat memulai analisis.
    """
    task_id: str
    message: str