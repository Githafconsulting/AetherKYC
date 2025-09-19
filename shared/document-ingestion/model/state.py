from typing import Optional, Dict
from pydantic import BaseModel

class IngestionState(BaseModel):
    kafka_message: dict
    ack_id: Optional[str] = None
    document_id: Optional[str] = None
    user_id: Optional[str] = None
    ocr_job_id: Optional[str] = None
    ocr_result: Optional[Dict] = None
    kyc_response: Optional[Dict] = None
    ocr_request_payload: Optional[Dict] = None