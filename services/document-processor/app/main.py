from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from contextlib import asynccontextmanager
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    print("Starting OCR Agent service")

    # Check Supabase configuration
    if not os.getenv("SUPABASE_URL"):
        print("WARNING: SUPABASE_URL not configured")
    if not os.getenv("SUPABASE_SERVICE_KEY"):
        print("WARNING: SUPABASE_SERVICE_KEY not configured")

    # Initialize EasyOCR Engine
    try:
        import easyocr
        print("EasyOCR Engine initialized successfully!")
        print("Supported languages: en, fr, de, es, it, pt, ru, ja, ch")
    except Exception as e:
        print(f"EasyOCR initialization failed: {e} (will use fallback mode)")

    # Start Kafka consumer
    try:
        kafka_consumer_service.start_consumer()
        print("Sarah (Document Intelligence Agent): Kafka consumer started - listening for user applications")
    except Exception as e:
        print(f"WARNING: Failed to start Kafka consumer: {e}")

    yield

    # Shutdown
    print("Shutting down OCR Agent service")
    kafka_consumer_service.stop_consumer()

# Create FastAPI app
app = FastAPI(
    title="OCR Agent API",
    description="Document OCR processing service with Tesseract",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8082").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header."""
    start_time = time.time()

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request error: {str(e)}")

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
print("Adding OCR router...")
app.include_router(router)
print("Router added successfully!")

# Debug endpoint
@app.get("/debug")
async def debug_endpoint():
    print("=== DEBUG ENDPOINT HIT ===")
    return {"message": "Debug working", "routes": len(app.routes)}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "OCR Agent",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "health": "/ocr/health",
            "process": "/ocr/process"
        }
    }

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv('../.env')

    port = int(os.getenv("OCR_SERVICE_PORT", "8001"))
    host = os.getenv("OCR_SERVICE_HOST", "0.0.0.0")

    print(f"Starting OCR Agent on {host}:{port}")
    print(f"API Docs: http://localhost:{port}/docs")
    print("=" * 50)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info"
    )