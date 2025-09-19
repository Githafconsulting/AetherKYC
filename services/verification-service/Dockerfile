# Multi-stage build for KYC Agent
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libgomp1 \
    libglib2.0-0 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 kycuser && \
    mkdir -p /app /tmp/uploads && \
    chown -R kycuser:kycuser /app /tmp/uploads

# Copy Python packages from builder
COPY --from=builder /root/.local /home/kycuser/.local

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=kycuser:kycuser app/ ./app/

# Switch to non-root user
USER kycuser

# Add local bin to PATH
ENV PATH=/home/kycuser/.local/bin:$PATH
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8002/kyc/health')" || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]