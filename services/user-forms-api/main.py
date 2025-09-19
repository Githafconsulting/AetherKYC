from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid
import os
import aiofiles
from pathlib import Path
import logging
from datetime import datetime, date
import json
from confluent_kafka import Producer
import httpx
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="User Forms & Document Upload API",
    description="Handle user form submissions with document uploads and processing",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enums and Models
class DocumentType(str, Enum):
    PASSPORT = "passport"
    ID_CARD = "id_card"
    DRIVER_LICENSE = "driver_license"
    BIRTH_CERTIFICATE = "birth_certificate"
    UTILITY_BILL = "utility_bill"

class ApplicationStatus(str, Enum):
    SUBMITTED = "submitted"
    DOCUMENTS_UPLOADED = "documents_uploaded"
    PROCESSING = "processing"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"

class PersonalInfo(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    date_of_birth: date
    nationality: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state_province: str
    postal_code: str
    country: str

    @validator('phone')
    def validate_phone(cls, v):
        # Basic phone validation
        if not v.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValueError('Invalid phone number format')
        return v

class DocumentInfo(BaseModel):
    document_type: DocumentType
    document_number: str
    issuing_country: str
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None

class ApplicationForm(BaseModel):
    personal_info: PersonalInfo
    documents: List[DocumentInfo]
    application_type: str = "kyc_verification"
    additional_notes: Optional[str] = None

class ApplicationResponse(BaseModel):
    application_id: str
    status: ApplicationStatus
    submission_timestamp: datetime
    estimated_processing_time: str
    next_steps: List[str]
    upload_urls: Dict[str, str]

# Kafka configuration
KAFKA_CONFIG = {
    'bootstrap.servers': os.getenv('KAFKA_BROKER', 'localhost:9092'),
    'client.id': 'user-forms-api'
}

producer = Producer(KAFKA_CONFIG)

# File upload configuration
UPLOAD_DIR = Path("./uploads/user-submissions")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}

class ApplicationManager:
    def __init__(self):
        self.applications: Dict[str, dict] = {}

    def create_application(self, form_data: ApplicationForm) -> str:
        """Create a new application"""
        application_id = str(uuid.uuid4())

        application = {
            "application_id": application_id,
            "personal_info": form_data.personal_info.dict(),
            "documents": [doc.dict() for doc in form_data.documents],
            "application_type": form_data.application_type,
            "additional_notes": form_data.additional_notes,
            "status": ApplicationStatus.SUBMITTED,
            "submission_timestamp": datetime.utcnow(),
            "document_uploads": {},
            "processing_history": [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": ApplicationStatus.SUBMITTED,
                    "message": "Application submitted successfully"
                }
            ]
        }

        self.applications[application_id] = application
        return application_id

    def get_application(self, application_id: str) -> Optional[dict]:
        """Get application by ID"""
        return self.applications.get(application_id)

    def update_status(self, application_id: str, status: ApplicationStatus, message: str = ""):
        """Update application status"""
        if application_id in self.applications:
            self.applications[application_id]["status"] = status
            self.applications[application_id]["processing_history"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "message": message
            })

    def add_document_upload(self, application_id: str, document_type: str, file_path: str, file_info: dict):
        """Add document upload information"""
        if application_id in self.applications:
            self.applications[application_id]["document_uploads"][document_type] = {
                "file_path": file_path,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "file_info": file_info
            }

# Global application manager
app_manager = ApplicationManager()

async def send_to_kafka(topic: str, key: str, value: dict):
    """Send message to Kafka topic"""
    try:
        producer.produce(
            topic=topic,
            key=key,
            value=json.dumps(value, default=str),
            callback=lambda err, msg: logger.info(f"Message sent to {msg.topic()}" if not err else f"Error: {err}")
        )
        producer.flush()
    except Exception as e:
        logger.error(f"Error sending to Kafka: {e}")

async def process_document_upload(application_id: str, document_type: str, file_path: str):
    """Process uploaded document through OCR pipeline"""
    try:
        application = app_manager.get_application(application_id)
        if not application:
            logger.error(f"Application {application_id} not found")
            return

        # Send to document processor for OCR
        async with httpx.AsyncClient() as client:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {
                    'language': 'eng',
                    'application_id': application_id,
                    'document_type': document_type,
                    'customer_id': application['personal_info']['email']
                }

                response = await client.post(
                    'http://document-processor:8001/ocr/process',
                    files=files,
                    data=data,
                    timeout=30.0
                )

                if response.status_code == 200:
                    ocr_result = response.json()
                    logger.info(f"OCR completed for {application_id} - {document_type}")

                    # Send notification to Kafka
                    await send_to_kafka(
                        'user-application-updates',
                        application_id,
                        {
                            'application_id': application_id,
                            'document_type': document_type,
                            'status': 'ocr_completed',
                            'ocr_result': ocr_result,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    )
                else:
                    logger.error(f"OCR failed for {application_id}: {response.text}")

    except Exception as e:
        logger.error(f"Error processing document upload: {e}")

@app.post("/submit-application", response_model=ApplicationResponse)
async def submit_application(
    background_tasks: BackgroundTasks,
    application_data: ApplicationForm
):
    """Submit a new application form"""
    try:
        # Create application
        application_id = app_manager.create_application(application_data)

        # Create upload URLs for each required document
        upload_urls = {}
        for doc in application_data.documents:
            upload_urls[doc.document_type] = f"/upload-document/{application_id}/{doc.document_type}"

        # Send notification to Kafka
        background_tasks.add_task(
            send_to_kafka,
            'user-applications',
            application_id,
            {
                'application_id': application_id,
                'customer_email': application_data.personal_info.email,
                'status': 'submitted',
                'application_type': application_data.application_type,
                'documents_required': [doc.document_type for doc in application_data.documents],
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        return ApplicationResponse(
            application_id=application_id,
            status=ApplicationStatus.SUBMITTED,
            submission_timestamp=datetime.utcnow(),
            estimated_processing_time="2-3 business days",
            next_steps=[
                "Upload required documents using the provided URLs",
                "Wait for document processing and verification",
                "Check application status regularly"
            ],
            upload_urls=upload_urls
        )

    except Exception as e:
        logger.error(f"Error submitting application: {e}")
        raise HTTPException(status_code=500, detail="Error processing application")

@app.post("/upload-document/{application_id}/{document_type}")
async def upload_document(
    application_id: str,
    document_type: DocumentType,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None)
):
    """Upload a document for an existing application"""
    try:
        # Validate application exists
        application = app_manager.get_application(application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # Validate file
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")

        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Invalid file format")

        # Save file
        file_dir = UPLOAD_DIR / application_id
        file_dir.mkdir(exist_ok=True)

        filename = f"{document_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{file_extension}"
        file_path = file_dir / filename

        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        # Update application
        file_info = {
            "original_filename": file.filename,
            "size": len(content),
            "content_type": file.content_type,
            "notes": notes
        }

        app_manager.add_document_upload(application_id, document_type, str(file_path), file_info)
        app_manager.update_status(application_id, ApplicationStatus.DOCUMENTS_UPLOADED, f"Document {document_type} uploaded")

        # Process document in background
        background_tasks.add_task(process_document_upload, application_id, document_type, str(file_path))

        # Send notification
        background_tasks.add_task(
            send_to_kafka,
            'user-application-updates',
            application_id,
            {
                'application_id': application_id,
                'document_type': document_type,
                'status': 'document_uploaded',
                'file_info': file_info,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        return {
            "message": "Document uploaded successfully",
            "application_id": application_id,
            "document_type": document_type,
            "filename": filename,
            "status": "processing"
        }

    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail="Error uploading document")

@app.get("/application/{application_id}")
async def get_application_status(application_id: str):
    """Get application status and details"""
    application = app_manager.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Remove sensitive information
    safe_application = application.copy()
    safe_application["personal_info"] = {
        "email": application["personal_info"]["email"],
        "first_name": application["personal_info"]["first_name"],
        "last_name": application["personal_info"]["last_name"]
    }

    return safe_application

@app.get("/applications")
async def list_applications(
    status: Optional[ApplicationStatus] = None,
    limit: int = 50,
    offset: int = 0
):
    """List applications with optional filtering"""
    applications = list(app_manager.applications.values())

    if status:
        applications = [app for app in applications if app["status"] == status]

    # Sort by submission time (newest first)
    applications.sort(key=lambda x: x["submission_timestamp"], reverse=True)

    # Apply pagination
    total = len(applications)
    applications = applications[offset:offset + limit]

    # Remove sensitive information
    safe_applications = []
    for app in applications:
        safe_app = {
            "application_id": app["application_id"],
            "status": app["status"],
            "submission_timestamp": app["submission_timestamp"],
            "application_type": app["application_type"],
            "customer_name": f"{app['personal_info']['first_name']} {app['personal_info']['last_name']}",
            "customer_email": app["personal_info"]["email"],
            "documents_count": len(app["document_uploads"])
        }
        safe_applications.append(safe_app)

    return {
        "applications": safe_applications,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.post("/webhook/processing-update")
async def processing_update_webhook(update_data: dict):
    """Webhook endpoint for processing updates from other services"""
    try:
        application_id = update_data.get("application_id")
        if not application_id:
            raise HTTPException(status_code=400, detail="Missing application_id")

        application = app_manager.get_application(application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        # Update application based on webhook data
        status = update_data.get("status")
        message = update_data.get("message", "")

        if status:
            app_manager.update_status(application_id, status, message)

        return {"message": "Update processed successfully"}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Error processing update")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "user-forms-api",
        "total_applications": len(app_manager.applications),
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)