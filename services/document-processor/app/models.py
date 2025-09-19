from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

# Custom JSON encoder configuration for Pydantic models
class DateTimeModel(BaseModel):
    model_config = ConfigDict(
        json_serializers={
            datetime: lambda v: v.isoformat() if v else None
        }
    )

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentType(str, Enum):
    PDF = "pdf"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"

class OCRRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: Optional[UUID] = None
    language: Optional[str] = Field(default="eng", description="Language code for OCR")
    enhance_image: Optional[bool] = Field(default=True, description="Apply image enhancement")
    return_confidence: Optional[bool] = Field(default=True, description="Return confidence scores")

class OCRResponse(DateTimeModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    document_id: UUID
    status: ProcessingStatus
    extracted_text: Optional[str] = None
    confidence_score: Optional[float] = None
    processing_time: Optional[int] = None
    language_detected: Optional[str] = None
    page_count: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class DocumentInfo(DateTimeModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    filename: str
    file_path: str
    file_size: int
    mime_type: str
    upload_status: str
    created_at: datetime

class HealthCheck(DateTimeModel):
    status: str
    timestamp: datetime
    service: str
    version: str
    dependencies: Dict[str, bool]

class ErrorResponse(DateTimeModel):
    error: str
    detail: Optional[str] = None
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.now)

class OCRMetadata(BaseModel):
    pages_processed: int
    total_characters: int
    processing_engine: str = "easyocr"
    image_preprocessing: List[str] = []
    extraction_time_ms: int
    
class BatchOCRRequest(BaseModel):
    document_ids: List[UUID]
    language: Optional[str] = "eng"
    priority: Optional[str] = "normal"

class BatchOCRResponse(DateTimeModel):
    batch_id: UUID
    total_documents: int
    status: ProcessingStatus
    results: List[OCRResponse] = []
    created_at: datetime