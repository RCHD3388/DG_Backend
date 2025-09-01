# app/schemas/response_schema.py

from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional
from datetime import datetime, timezone

# Tipe Generik untuk payload data, agar bisa di-reuse
DataType = TypeVar('DataType')

class ErrorDetail(BaseModel):
    """Skema detail untuk respons error."""
    code: int
    type: str
    message: str

class Meta(BaseModel):
    """Skema untuk metadata respons."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StandardResponse(BaseModel, Generic[DataType]):
    """
    Skema respons standar yang akan digunakan untuk SEMUA respons API.
    """
    success: bool = True
    data: Optional[DataType] = None
    error: Optional[ErrorDetail] = None
    meta: Meta = Field(default_factory=Meta)

class MessageResponseData(BaseModel):
    message: str