FROM python:3.12-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy IngestionService source
COPY . .

# Run ingestion_runner.py
CMD ["python", "ingestion_runner.py"]