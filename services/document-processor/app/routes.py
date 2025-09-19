from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import os
import logging
from datetime import datetime
import io

from .models import OCRResponse, HealthCheck, ProcessingStatus
from .services.ocr_service import ocr_service
from .services.kafka_service import kafka_service
from supabase import create_client, Client
import asyncpg
import json

# Set up basic logging with colors
import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)

logger = logging.getLogger(__name__)

# Simple colored logging functions
def log_info(message, process_type="INFO"):
    colors = {
        "UPLOAD": Fore.BLUE,
        "OCR": Fore.MAGENTA,
        "STORAGE": Fore.CYAN,
        "DATABASE": Fore.YELLOW,
        "API": Fore.GREEN,
        "KAFKA": Fore.LIGHTMAGENTA_EX,
        "INFO": Fore.WHITE
    }
    color = colors.get(process_type, Fore.WHITE)
    print(f"{color}[{process_type}] {message}{Style.RESET_ALL}")

def log_error(message):
    print(f"{Fore.RED}[ERROR] {message}{Style.RESET_ALL}")

def detect_document_type(text):
    """Simple document type detection."""
    text_lower = text.lower()

    if any(keyword in text_lower for keyword in ['passport', 'nationality', 'date of birth']):
        return "passport", 85.0
    elif any(keyword in text_lower for keyword in ['bank statement', 'account', 'balance', 'transaction']):
        return "bank_statement", 80.0
    elif any(keyword in text_lower for keyword in ['photo', 'id photo', 'portrait']):
        return "id_photo", 75.0
    elif any(keyword in text_lower for keyword in ['invoice', 'bill', 'amount', 'total']):
        return "invoice", 70.0
    else:
        return "unknown", 0.0

router = APIRouter(prefix="/ocr", tags=["OCR"])

@router.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    print("=== TEST ENDPOINT HIT ===")
    return {"message": "Test endpoint working!", "status": "ok"}

# Database connection
async def get_db():
    """Get database connection."""
    try:
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
        try:
            yield conn
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        yield None

# Supabase client
def get_supabase_client() -> Client:
    """Get Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise HTTPException(
            status_code=500,
            detail="Supabase configuration missing. Set SUPABASE_URL and SUPABASE_SERVICE_KEY"
        )

    log_info(f"Creating Supabase client for URL: {url[:30]}...", "STORAGE")
    log_info(f"Using service key ending in: ...{key[-10:]}", "STORAGE")

    return create_client(url, key)

@router.post("/process", response_model=OCRResponse)
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: Optional[str] = "eng",
    enhance_image: Optional[bool] = True,
    return_confidence: Optional[bool] = True,
    user_id: Optional[str] = None,
    target_agent_url: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Process a document: Upload to Supabase, extract text using OCR, and send to another agent.
    
    - **file**: Document file (PDF, PNG, JPG, JPEG)
    - **language**: OCR language (default: eng)
    - **enhance_image**: Apply image enhancement
    - **return_confidence**: Return confidence scores
    - **target_agent_url**: URL of the agent to send results to
    """
    try:
        # Log API request
        print("=== OCR REQUEST RECEIVED ===")
        log_info("POST /ocr/process - Processing document upload", "API")

        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Check file extension
        file_extension = file.filename.split('.')[-1].lower()
        allowed_extensions = ['pdf', 'png', 'jpg', 'jpeg']
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
            )

        # Read file content once
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size
        max_size = int(os.getenv("OCR_MAX_FILE_SIZE", "10485760"))
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {max_size / 1024 / 1024}MB"
            )

        # Generate unique identifiers
        document_id = uuid4()
        ocr_result_id = uuid4()

        # Log upload start
        log_info(f"Starting upload: {file.filename} ({file_size / 1024:.2f} KB) for user {user_id or 'anonymous'}", "UPLOAD")
        
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Determine user ID
        if not user_id and db:
            # Get or create demo user
            demo_user = await db.fetchrow("SELECT id FROM users WHERE email = $1", "demo@platform.local")
            if demo_user:
                user_id = str(demo_user['id'])
            else:
                user_uuid = uuid4()
                await db.execute(
                    "INSERT INTO users (id, email) VALUES ($1, $2)",
                    user_uuid, "demo@platform.local"
                )
                user_id = str(user_uuid)
        elif not user_id:
            user_id = str(uuid4())
        
        # Upload to Supabase Storage
        bucket_name = "documents"
        file_key = f"{user_id}/{document_id}/{file.filename}"

        log_info(f"Attempting upload to bucket '{bucket_name}' with path '{file_key}'", "STORAGE")

        storage_url = None
        try:
            # Try Supabase upload first
            log_info("Checking if bucket exists...", "STORAGE")
            buckets = supabase.storage.list_buckets()
            bucket_exists = any(b.name == bucket_name for b in buckets)
            log_info(f"Bucket '{bucket_name}' exists: {bucket_exists}", "STORAGE")

            if not bucket_exists:
                log_info(f"Creating bucket '{bucket_name}'...", "STORAGE")
                supabase.storage.create_bucket(bucket_name, public=False)
                log_info(f"Created bucket: {bucket_name}", "STORAGE")

            # Upload file
            log_info(f"Starting file upload: {len(file_content)} bytes", "STORAGE")
            response = supabase.storage.from_(bucket_name).upload(
                path=file_key,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            log_info(f"Upload response: {response}", "STORAGE")
            storage_url = f"supabase://{bucket_name}/{file_key}"
            log_info(f"File uploaded successfully to {storage_url}", "STORAGE")

        except Exception as e:
            log_error(f"Supabase upload failed: {e}")
            # Fallback to local storage
            try:
                log_info("Falling back to local storage...", "STORAGE")
                local_dir = f"/tmp/uploads/{user_id}/{document_id}"
                os.makedirs(local_dir, exist_ok=True)
                local_path = f"{local_dir}/{file.filename}"

                with open(local_path, "wb") as f:
                    f.write(file_content)

                storage_url = f"local://{local_path}"
                log_info(f"File saved locally to {storage_url}", "STORAGE")

            except Exception as local_e:
                log_error(f"Local storage also failed: {local_e}")
                raise HTTPException(status_code=500, detail=f"Both Supabase and local storage failed: {str(e)}, {str(local_e)}")
        
        # Store in database if available
        if db:
            log_info(f"Storing document in database: {document_id}", "DATABASE")
            await db.execute("""
                INSERT INTO documents (id, user_id, filename, file_path, file_size, mime_type, upload_status, processing_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, document_id, UUID(user_id), file.filename, storage_url,
                file_size, file.content_type, 'uploaded', 'ocr')

            await db.execute("""
                INSERT INTO ocr_results (id, document_id, status)
                VALUES ($1, $2, $3)
            """, ocr_result_id, document_id, ProcessingStatus.PROCESSING.value)
        
        # Process document in background
        background_tasks.add_task(
            process_document_from_supabase,
            supabase,
            bucket_name,
            file_key,
            ocr_result_id,
            document_id,
            language,
            enhance_image,
            return_confidence,
            user_id,
            target_agent_url,
            file.filename,
            file.content_type
        )
        
        # Log the IDs for clarity
        log_info(f"OCR Result ID (use for /ocr/result): {ocr_result_id}", "API")
        log_info(f"Document ID: {document_id}", "API")

        # Return initial response
        return OCRResponse(
            id=ocr_result_id,
            document_id=document_id,
            status=ProcessingStatus.PROCESSING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={
                "supabase_path": f"{bucket_name}/{file_key}",
                "file_size": file_size,
                "processing": True
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def update_command_center(status, task, activity_log=None, extra_data=None):
    """Helper function to update Command Center with current status"""
    try:
        import httpx
        from datetime import datetime

        # Add timestamps to activity log entries
        if activity_log:
            timestamp = datetime.now().strftime("%H:%M:%S")
            timestamped_log = [f"[{timestamp}] {entry}" for entry in activity_log]
        else:
            timestamped_log = []

        async with httpx.AsyncClient(timeout=5.0) as client:
            agent_update = {
                "status": status,
                "currentTask": task,
                "activityLog": timestamped_log,
                **(extra_data or {})
            }
            await client.post(
                "http://command-center-connector:8006/api/agents/agent-sarah/update",
                json=agent_update
            )
            log_info(f"Command Center updated: {task}", "API")
    except Exception as e:
        log_error(f"Failed to update Command Center: {e}")

async def process_document_from_supabase(
    supabase: Client,
    bucket_name: str,
    file_key: str,
    ocr_result_id: UUID,
    document_id: UUID,
    language: str,
    enhance_image: bool,
    return_confidence: bool,
    user_id: str,
    target_agent_url: Optional[str],
    filename: str,
    content_type: str
):
    """Process document directly from Supabase storage."""
    conn = None
    try:
        # STARTED - Document processing initiated
        await update_command_center(
            "active",
            f"Document processing started for {filename}",
            [f"🆕 DOCUMENT RECEIVED: {filename} uploaded for processing"]
        )

        # Download file from Supabase
        log_info(f"Downloading file from storage: {bucket_name}/{file_key}", "STORAGE")

        # IN_PROGRESS - Downloading from storage
        await update_command_center(
            "active",
            f"Downloading {filename} from secure storage",
            [f"📥 STORAGE: Downloading {filename} from secure cloud storage", f"🆕 DOCUMENT RECEIVED: {filename} uploaded for processing"]
        )

        file_data = supabase.storage.from_(bucket_name).download(file_key)

        if not file_data:
            raise Exception("Failed to download file from Supabase")

        log_info("File downloaded successfully, starting OCR processing", "STORAGE")

        # IN_PROGRESS - Document downloaded, preparing for OCR
        await update_command_center(
            "active",
            f"Preparing {filename} for text extraction",
            [f"🔍 OCR PREP: Document downloaded, initializing AI vision engine",
             f"📥 STORAGE: Downloading {filename} from secure cloud storage",
             f"🆕 DOCUMENT RECEIVED: {filename} uploaded for processing"]
        )

        # Process with OCR service (using in-memory data)
        log_info(f"Starting OCR processing for {filename.split('.')[-1].upper()} document", "OCR")

        # IN_PROGRESS - Running OCR
        await update_command_center(
            "active",
            f"Extracting text from {filename} using AI vision",
            [f"🔤 OCR ACTIVE: Running text extraction on {filename.split('.')[-1].upper()} document",
             f"🔍 OCR PREP: Document downloaded, initializing AI vision engine",
             f"📥 STORAGE: Downloading {filename} from secure cloud storage",
             f"🆕 DOCUMENT RECEIVED: {filename} uploaded for processing"]
        )

        result = await ocr_service.process_document_from_bytes(
            file_data=file_data,
            filename=filename,
            language=language,
            enhance_image=enhance_image,
            return_confidence=return_confidence
        )

        # Simple document type detection
        doc_type, classification_confidence = detect_document_type(result.get('extracted_text', ''))

        log_info(f"Document type detected: {doc_type} (confidence: {classification_confidence:.1f}%)", "OCR")

        # Log OCR completion
        text_length = len(result.get('extracted_text', ''))
        confidence = result.get('confidence_score', 0) or 0
        processing_time = result.get('processing_time', 0)

        log_info(f"OCR completed: {text_length} characters extracted, confidence: {confidence:.1f}%, time: {processing_time}ms", "OCR")

        # IN_PROGRESS - Analyzing extracted content
        await update_command_center(
            "active",
            f"Analyzing extracted content and classifying document type",
            [f"🧠 ANALYSIS: Document classified as {doc_type} ({classification_confidence:.1f}% confidence)",
             f"✅ OCR COMPLETE: Extracted {text_length} characters ({confidence:.1f}% confidence)",
             f"🔤 OCR ACTIVE: Running text extraction on {filename.split('.')[-1].upper()} document",
             f"🔍 OCR PREP: Document downloaded, initializing AI vision engine",
             f"🆕 DOCUMENT RECEIVED: {filename} uploaded for processing"]
        )
        
        # Prepare payload for another agent
        payload = {
            "document_id": str(document_id),
            "ocr_result_id": str(ocr_result_id),
            "user_id": user_id,
            "filename": filename,
            "supabase_path": f"{bucket_name}/{file_key}",
            "extracted_text": result.get('extracted_text', ''),
            "confidence_score": result.get('confidence_score'),
            "language_detected": result.get('language_detected'),
            "page_count": result.get('page_count', 1),
            "processing_time": result.get('processing_time'),
            "document_type": doc_type,
            "classification_confidence": classification_confidence,
            "metadata": result.get('metadata', {}),
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to target agent if URL provided
        if target_agent_url:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(target_agent_url, json=payload)
                    logger.info(f"Sent OCR results to {target_agent_url}: {response.status_code}")
                    payload['agent_response'] = {
                        "status_code": response.status_code,
                        "sent_at": datetime.now().isoformat()
                    }
                except Exception as e:
                    logger.error(f"Failed to send to target agent: {e}")
                    payload['agent_response'] = {
                        "error": str(e),
                        "failed_at": datetime.now().isoformat()
                    }
        
        # Update database if available
        try:
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))

            # Update OCR results
            await conn.execute("""
                UPDATE ocr_results
                SET extracted_text = $1, confidence_score = $2, processing_time = $3,
                    language_detected = $4, page_count = $5, status = $6,
                    metadata = $7, updated_at = NOW()
                WHERE id = $8
            """,
                result['extracted_text'],
                result.get('confidence_score'),
                result.get('processing_time'),
                result.get('language_detected'),
                result.get('page_count'),
                ProcessingStatus.COMPLETED.value,
                json.dumps(payload),
                ocr_result_id
            )

            # Update documents status
            await conn.execute("""
                UPDATE documents
                SET upload_status = 'processed', updated_at = NOW()
                WHERE id = $1
            """, document_id)

            log_info(f"Database updated successfully for document {document_id}", "DATABASE")

        except Exception as e:
            log_error(f"Database update failed: {e}")

        # Set storage_url for this context (bucket_name and file_key are function parameters)
        storage_url = f"supabase://{bucket_name}/{file_key}"

        # HANDOFF - Preparing to send data to next system
        await update_command_center(
            "active",
            f"Preparing handoff to downstream agents",
            [f"📤 HANDOFF: Preparing data package for Marcus (KYC Agent)",
             f"🧠 ANALYSIS: Document classified as {doc_type} ({classification_confidence:.1f}% confidence)",
             f"✅ OCR COMPLETE: Extracted {text_length} characters ({confidence:.1f}% confidence)",
             f"🔤 OCR ACTIVE: Running text extraction on {filename.split('.')[-1].upper()} document",
             f"🆕 DOCUMENT RECEIVED: {filename} uploaded for processing"]
        )

        # Always publish OCR results to Kafka (regardless of database status)
        log_info("Publishing OCR results to Kafka topics", "KAFKA")
        kafka_success = kafka_service.publish_ocr_result(
            request_id=str(ocr_result_id),
            customer_id=user_id,
            document_type=doc_type,
            extracted_text=result.get('extracted_text', ''),
            confidence=confidence,
            storage_url=storage_url,
            metadata={
                "filename": filename,
                "content_type": content_type,
                "processing_time": processing_time,
                "page_count": result.get('page_count', 1),
                "language_detected": result.get('language_detected'),
                "classification_confidence": classification_confidence
            }
        )

        if kafka_success:
            log_info("OCR results published to Kafka successfully", "KAFKA")
        else:
            log_error("Failed to publish OCR results to Kafka")

        # COMPLETED - Final status update
        await update_command_center(
            "active",
            f"Document processing completed successfully",
            [f"🎉 COMPLETED: {doc_type} processing finished - sent to Marcus for KYC verification",
             f"✅ KAFKA: Data published to message queue (Status: {'✓' if kafka_success else '✗'})",
             f"📤 HANDOFF: Preparing data package for Marcus (KYC Agent)",
             f"🧠 ANALYSIS: Document classified as {doc_type} ({classification_confidence:.1f}% confidence)",
             f"✅ OCR COMPLETE: Extracted {text_length} characters ({confidence:.1f}% confidence)"],
            {"tasksCompleted": 1, "successRate": 100 if kafka_success else 90}
        )

        # Print processing summary
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.WHITE}PROCESSING COMPLETED")
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.GREEN}Document ID: {Fore.WHITE}{document_id}")
        print(f"{Fore.GREEN}Document Type: {Fore.WHITE}{doc_type}")
        print(f"{Fore.GREEN}Text Length: {Fore.WHITE}{text_length} characters")
        print(f"{Fore.GREEN}Confidence: {Fore.WHITE}{confidence:.1f}%")
        print(f"{Fore.GREEN}Processing Time: {Fore.WHITE}{processing_time}ms")
        print(f"{Fore.GREEN}Storage Path: {Fore.WHITE}{storage_url}")
        print(f"{Fore.GREEN}Kafka Published: {Fore.WHITE}{kafka_success}")
        print(f"{Fore.CYAN}{'='*60}\n{Style.RESET_ALL}")
        
    except Exception as e:
        log_error(f"Error processing document: {str(e)}")

        # Update status to failed if database available
        if conn or os.getenv("DATABASE_URL"):
            try:
                if not conn:
                    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))

                await conn.execute("""
                    UPDATE ocr_results
                    SET status = $1, error_message = $2, updated_at = NOW()
                    WHERE id = $3
                """, ProcessingStatus.FAILED.value, str(e), ocr_result_id)
                log_info(f"Updated failed status in database for {ocr_result_id}", "DATABASE")
            except:
                pass
    
    finally:
        if conn:
            await conn.close()

@router.get("/result/{result_id}", response_model=OCRResponse)
async def get_ocr_result(
    result_id: UUID,
    db: asyncpg.Connection = Depends(get_db)
):
    """Get OCR processing result by ID."""
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    try:
        row = await db.fetchrow("""
            SELECT * FROM ocr_results WHERE id = $1
        """, result_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Result not found")
        
        return OCRResponse(
            id=row['id'],
            document_id=row['document_id'],
            status=row['status'],
            extracted_text=row['extracted_text'],
            confidence_score=row['confidence_score'],
            processing_time=row['processing_time'],
            language_detected=row['language_detected'],
            page_count=row['page_count'],
            error_message=row['error_message'],
            metadata=row['metadata'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching result: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=HealthCheck)
async def health_check():
    """Check service health and dependencies."""
    try:
        dependencies = {}
        
        # Check database
        try:
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
            await conn.fetchval("SELECT 1")
            await conn.close()
            dependencies["database"] = True
        except:
            dependencies["database"] = False
        
        # Check Supabase
        try:
            supabase = get_supabase_client()
            buckets = supabase.storage.list_buckets()
            dependencies["supabase"] = True
            dependencies["supabase_buckets"] = len(buckets)
        except:
            dependencies["supabase"] = False
        
        # Check OCR
        try:
            import easyocr
            dependencies["easyocr"] = True
        except:
            dependencies["easyocr"] = False
        
        all_healthy = all([v for k, v in dependencies.items() if k != "supabase_buckets"])
        
        return HealthCheck(
            status="healthy" if all_healthy else "degraded",
            timestamp=datetime.now(),
            service="ocr-agent",
            version="1.0.0",
            dependencies=dependencies
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthCheck(
            status="unhealthy",
            timestamp=datetime.now(),
            service="ocr-agent",
            version="1.0.0",
            dependencies={}
        )