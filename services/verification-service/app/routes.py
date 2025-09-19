from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks, status
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import os
import aiofiles
from pathlib import Path
import logging
from datetime import datetime
import json

from .models import (
    KYCRequest, KYCResponse, HealthCheck, ErrorResponse,
    VerificationStatus, DocumentType, BatchKYCRequest, BatchKYCResponse
)
from .services.kyc_service import kyc_service
# Removed Ballerine service - using local KYC processing
from supabase import create_client, Client
import asyncpg
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kyc", tags=["KYC"])

# Database connection
async def get_db():
    """Get database connection."""
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        yield conn
    finally:
        await conn.close()

# Supabase client
def get_supabase_client() -> Client:
    """Get Supabase client."""
    url = os.getenv("SUPABASE_URL", "http://localhost:54321")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    return create_client(url, key)

@router.post("/verify", response_model=KYCResponse)
async def verify_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: Optional[DocumentType] = None,
    country_code: Optional[str] = "US",
    perform_face_match: Optional[bool] = False,
    reference_image: Optional[UploadFile] = None,
    user_id: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Verify a KYC document.
    
    - **file**: Document file (PDF, PNG, JPG, JPEG)
    - **document_type**: Type of document (passport, drivers_license, etc.)
    - **country_code**: ISO country code
    - **perform_face_match**: Whether to perform face matching
    - **reference_image**: Reference image for face matching
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check file extension
        file_extension = Path(file.filename).suffix.lower()
        allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Save uploaded file temporarily
        temp_file_path = Path(f"/tmp/{uuid4()}_{file.filename}")
        reference_file_path = None
        
        async with aiofiles.open(temp_file_path, 'wb') as f:
            content = await file.read()
            file_size = len(content)
            await f.write(content)
        
        # Save reference image if provided
        if perform_face_match and reference_image:
            reference_file_path = Path(f"/tmp/{uuid4()}_{reference_image.filename}")
            async with aiofiles.open(reference_file_path, 'wb') as f:
                ref_content = await reference_image.read()
                await f.write(ref_content)
        
        # Validate file size
        max_size = int(os.getenv("KYC_MAX_FILE_SIZE", "10485760"))
        if file_size > max_size:
            os.remove(temp_file_path)
            if reference_file_path:
                os.remove(reference_file_path)
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {max_size / 1024 / 1024}MB"
            )
        
        # Create document record
        document_id = uuid4()
        
        # Get or create a default demo user
        if user_id:
            user_uuid = UUID(user_id)
        else:
            # Check if demo user exists, create if not
            demo_user = await db.fetchrow("SELECT id FROM users WHERE email = $1", "demo@platform.local")
            if demo_user:
                user_uuid = demo_user['id']
            else:
                # Create demo user
                user_uuid = uuid4()
                await db.execute("""
                    INSERT INTO users (id, email) VALUES ($1, $2)
                """, user_uuid, "demo@platform.local")
        
        await db.execute("""
            INSERT INTO documents (id, user_id, filename, file_path, file_size, mime_type, upload_status, processing_agent)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, document_id, user_uuid, file.filename, str(temp_file_path), file_size, file.content_type, 'uploaded', 'kyc')
        
        # Create initial KYC result record
        kyc_result_id = uuid4()
        await db.execute("""
            INSERT INTO kyc_results (id, document_id, status)
            VALUES ($1, $2, $3)
        """, kyc_result_id, document_id, 'processing')
        
        # Process document in background using enhanced workflow
        background_tasks.add_task(
            verify_document_enhanced_workflow,
            kyc_result_id,
            document_id,
            str(temp_file_path),
            document_type.value if document_type else None,
            country_code,
            perform_face_match,
            str(reference_file_path) if reference_file_path else None,
            user_uuid
        )
        
        # Return initial response
        return KYCResponse(
            id=kyc_result_id,
            document_id=document_id,
            verification_status=VerificationStatus.PROCESSING,
            status='processing',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def verify_document_enhanced_workflow(
    kyc_result_id: UUID,
    document_id: UUID,
    file_path: str,
    document_type: Optional[str],
    country_code: str,
    perform_face_match: bool,
    reference_file_path: Optional[str],
    user_id: UUID
):
    """Process KYC document using local verification service."""
    try:
        # Use local KYC service for document verification
        result = await kyc_service.verify_document(
            file_path=file_path,
            document_type=document_type,
            country_code=country_code,
            perform_face_match=perform_face_match,
            reference_image_path=reference_file_path
        )

        logger.info(f"KYC verification completed for {kyc_result_id}: {result.get('verification_status')}")

        # Store results in database
        await store_verification_result(kyc_result_id, document_id, result, user_id)

    except Exception as e:
        logger.error(f"KYC verification failed: {str(e)}")

        # Fallback processing
        await verify_document_async_fallback(
            kyc_result_id, document_id, file_path, document_type,
            country_code, perform_face_match, reference_file_path
        )
    finally:
        # Clean up temp files
        try:
            os.remove(file_path) if os.path.exists(file_path) else None
            if reference_file_path and os.path.exists(reference_file_path):
                os.remove(reference_file_path)
        except:
            pass

async def verify_document_async_fallback(
    kyc_result_id: UUID,
    document_id: UUID,
    file_path: str,
    document_type: Optional[str],
    country_code: str,
    perform_face_match: bool,
    reference_file_path: Optional[str]
):
    """Verify document asynchronously."""
    conn = None
    try:
        # Get database connection
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
        
        # Verify document
        result = await kyc_service.verify_document(
            file_path=file_path,
            document_type=document_type,
            country_code=country_code,
            perform_face_match=perform_face_match,
            reference_image_path=reference_file_path
        )
        
        # Update KYC result
        await conn.execute("""
            UPDATE kyc_results
            SET verification_status = $1, document_type = $2, extracted_data = $3,
                risk_score = $4, risk_factors = $5, verification_checks = $6,
                status = $7, metadata = $8, updated_at = NOW()
            WHERE id = $9
        """,
            result['verification_status'],
            result.get('document_type'),
            json.dumps(result.get('extracted_data', {})),
            result.get('risk_score'),
            json.dumps(result.get('risk_factors', {})),
            json.dumps(result.get('verification_checks', {})),
            'completed',
            json.dumps(result.get('metadata', {})),
            kyc_result_id
        )
        
        # Update document status
        await conn.execute("""
            UPDATE documents
            SET upload_status = 'processed', updated_at = NOW()
            WHERE id = $1
        """, document_id)
        
        # Log success
        await conn.execute("""
            INSERT INTO processing_logs (document_id, agent_type, action, status, details)
            VALUES ($1, $2, $3, $4, $5)
        """, document_id, 'kyc', 'verify_document', 'success', json.dumps(result.get('metadata', {})))
        
    except Exception as e:
        logger.error(f"Error in async verification: {str(e)}")
        if conn:
            # Update with error
            await conn.execute("""
                UPDATE kyc_results
                SET status = $1, error_message = $2, updated_at = NOW()
                WHERE id = $3
            """, 'failed', str(e), kyc_result_id)
            
            # Log error
            await conn.execute("""
                INSERT INTO processing_logs (document_id, agent_type, action, status, details)
                VALUES ($1, $2, $3, $4, $5)
            """, document_id, 'kyc', 'verify_document', 'error', json.dumps({'error': str(e)}))
    finally:
        if conn:
            await conn.close()
        # Clean up temp files
        try:
            os.remove(file_path)
            if reference_file_path:
                os.remove(reference_file_path)
        except:
            pass

@router.get("/result/{result_id}", response_model=KYCResponse)
async def get_kyc_result(
    result_id: UUID,
    db: asyncpg.Connection = Depends(get_db)
):
    """Get KYC verification result by ID."""
    try:
        # Fetch result
        row = await db.fetchrow("""
            SELECT * FROM kyc_results WHERE id = $1
        """, result_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Result not found")
        
        # Parse JSON fields
        extracted_data = json.loads(row['extracted_data']) if row['extracted_data'] else None
        risk_factors = json.loads(row['risk_factors']) if row['risk_factors'] else None
        verification_checks = json.loads(row['verification_checks']) if row['verification_checks'] else None
        
        return KYCResponse(
            id=row['id'],
            document_id=row['document_id'],
            verification_status=row['verification_status'] or VerificationStatus.PENDING,
            document_type=row['document_type'],
            extracted_data=extracted_data,
            risk_score=row['risk_score'],
            risk_level=self._get_risk_level(row['risk_score']) if row['risk_score'] else None,
            verification_checks=verification_checks,
            status=row['status'],
            error_message=row['error_message'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching result: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _get_risk_level(risk_score: float) -> str:
    """Get risk level from score."""
    if risk_score < 20:
        return 'low'
    elif risk_score < 50:
        return 'medium'
    elif risk_score < 80:
        return 'high'
    else:
        return 'critical'

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
        
        # Check OpenCV
        try:
            import cv2
            dependencies["opencv"] = True
        except:
            dependencies["opencv"] = False
        
        # Check Supabase
        try:
            client = get_supabase_client()
            dependencies["supabase"] = True
        except:
            dependencies["supabase"] = False
        
        all_healthy = all(dependencies.values())
        
        return HealthCheck(
            status="healthy" if all_healthy else "degraded",
            timestamp=datetime.now(),
            service="kyc-agent",
            version="1.0.0",
            dependencies=dependencies
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthCheck(
            status="unhealthy",
            timestamp=datetime.now(),
            service="kyc-agent",
            version="1.0.0",
            dependencies={}
        )

@router.post("/batch", response_model=BatchKYCResponse)
async def verify_batch(
    request: BatchKYCRequest,
    background_tasks: BackgroundTasks,
    db: asyncpg.Connection = Depends(get_db)
):
    """Verify multiple documents in batch."""
    try:
        batch_id = uuid4()
        
        # Create batch processing tasks
        for doc_id in request.document_ids:
            # Verify document exists
            doc = await db.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
            if not doc:
                continue
            
            # Create KYC result record
            kyc_result_id = uuid4()
            await db.execute("""
                INSERT INTO kyc_results (id, document_id, status)
                VALUES ($1, $2, $3)
            """, kyc_result_id, doc_id, 'pending')
            
            # Add to background tasks
            background_tasks.add_task(
                verify_document_async,
                kyc_result_id,
                doc_id,
                doc['file_path'],
                request.document_type.value if request.document_type else None,
                'US',
                False,
                None
            )
        
        return BatchKYCResponse(
            batch_id=batch_id,
            total_documents=len(request.document_ids),
            status='processing',
            created_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/document-types", response_model=List[str])
async def get_supported_document_types():
    """Get list of supported document types."""
    return [doc_type.value for doc_type in DocumentType]

@router.get("/countries", response_model=List[str])
async def get_supported_countries():
    """Get list of supported countries."""
    return kyc_service.supported_countries