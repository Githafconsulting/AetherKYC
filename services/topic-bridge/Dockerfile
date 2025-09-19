FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY topic_bridge.py .

# Run the bridge service
CMD ["python", "topic_bridge.py"]