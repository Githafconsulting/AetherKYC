from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from contextlib import asynccontextmanager
from prometheus_client import make_asgi_app, Counter, Histogram
import time
from datetime import datetime

from .routes import router
from .models import ErrorResponse
from .services.kafka_consumer_service import kafka_consumer_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Metrics
request_count = Counter('kyc_requests_total', 'Total KYC requests')
request_duration = Histogram('kyc_request_duration_seconds', 'KYC request duration')
error_count = Counter('kyc_errors_total', 'Total KYC errors')
verification_count = Counter('kyc_verifications_total', 'Total KYC verifications', ['status'])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting KYC Agent service")

    # Check required environment variables
    required_vars = ["DATABASE_URL", "SUPABASE_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")

    # Initialize OpenCV
    try:
        import cv2
        logger.info(f"OpenCV version: {cv2.__version__}")
    except Exception as e:
        logger.error(f"Failed to initialize OpenCV: {e}")

    # Start Kafka consumer for processing KYC submissions
    try:
        kafka_consumer_service.start_consumer()
        logger.info("Kafka consumer service started successfully")
    except Exception as e:
        logger.error(f"Failed to start Kafka consumer: {e}")

    yield

    # Shutdown
    logger.info("Shutting down KYC Agent service")
    kafka_consumer_service.stop_consumer()

# Create FastAPI app
app = FastAPI(
    title="KYC Agent API",
    description="Document KYC verification service with advanced checks",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header and metrics."""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Record metrics
        request_count.inc()
        request_duration.observe(process_time)
        
        # Log request
        logger.info(
            f"request_processed method={request.method} path={request.url.path} status_code={response.status_code} process_time={process_time}"
        )
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        error_count.inc()
        
        logger.error(
            f"request_error method={request.method} path={request.url.path} error={str(e)} process_time={process_time}"
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    error_count.inc()
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="Validation Error",
            detail=str(exc),
            status_code=400
        ).model_dump()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    error_count.inc()
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail="An unexpected error occurred",
            status_code=500
        ).model_dump()
    )

# Include routers
app.include_router(router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "KYC Agent",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "health": "/kyc/health",
            "verify": "/kyc/verify",
            "document_types": "/kyc/document-types",
            "countries": "/kyc/countries",
            "metrics": "/metrics"
        }
    }

@app.get("/status")
async def status():
    """Service status endpoint."""
    return {
        "status": "operational",
        "service": "KYC Agent",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "document_verification": True,
            "face_matching": True,
            "risk_assessment": True,
            "batch_processing": True
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("KYC_SERVICE_PORT", "8002"))
    host = os.getenv("KYC_SERVICE_HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )