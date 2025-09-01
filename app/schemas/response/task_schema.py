# In app/api/routers/tasks.py

from pydantic import BaseModel
from typing import List
from app.schemas.response_schema import StandardResponse

# ... other imports ...

# --- Schema for a successful Redis clear operation ---
class RedisClearSuccessData(BaseModel):
    message: str
    keys_deleted: int