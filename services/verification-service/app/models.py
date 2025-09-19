from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class VerificationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    VERIFIED = "verified"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"

class DocumentType(str, Enum):
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    NATIONAL_ID = "national_id"
    RESIDENCE_PERMIT = "residence_permit"
    UNKNOWN = "unknown"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class KYCRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: Optional[UUID] = None
    document_type: Optional[DocumentType] = None
    country_code: Optional[str] = Field(default="US", description="ISO country code")
    perform_face_match: Optional[bool] = Field(default=False, description="Perform face matching")
    reference_image_id: Optional[UUID] = Field(default=None, description="Reference image for face matching")

class KYCResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    document_id: UUID
    verification_status: VerificationStatus
    document_type: Optional[DocumentType] = None
    extracted_data: Optional[Dict[str, Any]] = None
    risk_score: Optional[float] = None
    risk_level: Optional[RiskLevel] = None
    verification_checks: Optional[Dict[str, bool]] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ExtractedData(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    document_number: Optional[str] = None
    expiry_date: Optional[str] = None
    issue_date: Optional[str] = None
    issuing_country: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    mrz_data: Optional[Dict[str, Any]] = None

class VerificationChecks(BaseModel):
    document_authenticity: bool = False
    data_consistency: bool = False
    expiry_check: bool = False
    age_verification: bool = False
    face_match: Optional[bool] = None
    tampering_detection: bool = False
    ocr_confidence: bool = False
    format_validation: bool = False

class RiskFactors(BaseModel):
    expired_document: bool = False
    underage: bool = False
    data_mismatch: bool = False
    poor_image_quality: bool = False
    suspected_tampering: bool = False
    blacklisted_country: bool = False
    face_mismatch: bool = False

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    service: str
    version: str
    dependencies: Dict[str, bool]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.now)

class DocumentAnalysis(BaseModel):
    document_type: DocumentType
    confidence: float
    detected_features: List[str]
    quality_score: float
    warnings: List[str] = []

class FaceMatchResult(BaseModel):
    match_score: float
    is_match: bool
    confidence: float
    face_locations: List[Dict[str, int]] = []

class BatchKYCRequest(BaseModel):
    document_ids: List[UUID]
    document_type: Optional[DocumentType] = None
    priority: Optional[str] = "normal"

class BatchKYCResponse(BaseModel):
    batch_id: UUID
    total_documents: int
    status: str
    results: List[KYCResponse] = []
    created_at: datetime

class KYCMetadata(BaseModel):
    processing_engine: str = "custom_kyc"
    algorithms_used: List[str] = []
    processing_time_ms: int
    image_dimensions: Dict[str, int] = {}
    face_detection_enabled: bool = False
    additional_checks: List[str] = []