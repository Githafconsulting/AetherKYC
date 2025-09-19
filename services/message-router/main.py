from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient
import json
import os

app = FastAPI()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")

TOPIC_MAP = {
    "submission": "kyc-submissions",
    "verification": "kyc-verification",
    "alert": "kyc-alerts"
}

producer = Producer({"bootstrap.servers": KAFKA_BROKER})
admin_client = AdminClient({"bootstrap.servers": KAFKA_BROKER})


# -----------------------------
# Models
# -----------------------------
class KYCRequest(BaseModel):
    customer_id: str
    document_type: str
    document_number: str
    country: str


# -----------------------------
# Producer delivery callback
# -----------------------------
def delivery_report(err, msg):
    if err:
        print(f"Delivery failed for record {msg.key()}: {err}")
    else:
        print(f"Record {msg.key()} successfully produced to {msg.topic()} [{msg.partition()}]")


# -----------------------------
# API Endpoints
# -----------------------------
@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test Kafka connection
        metadata = admin_client.list_topics(timeout=5)
        return {
            "status": "healthy",
            "kafka_broker": KAFKA_BROKER,
            "topics_count": len(metadata.topics)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Kafka connection failed: {e}")

@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "service": "Message Router",
        "version": "1.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "submit_kyc": "/submit-kyc",
            "list_topics": "/list-topics",
            "delete_topic": "/delete-topic"
        }
    }
@app.post("/submit-kyc")
def submit_kyc(payload: KYCRequest, topic_type: str = Query("submission")):
    topic = TOPIC_MAP.get(topic_type)
    if not topic:
        raise HTTPException(status_code=400, detail=f"Unknown topic_type: {topic_type}")

    try:
        producer.produce(
            topic=topic,
            key=payload.customer_id,
            value=json.dumps(payload.dict()),
            callback=delivery_report
        )
        producer.flush()
        return {"message": f"KYC payload for customer {payload.customer_id} sent to topic {topic}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/list-topics")
def list_topics():
    """List all available Kafka topics"""
    try:
        metadata = admin_client.list_topics(timeout=10)
        topics = [t for t in metadata.topics.keys()]
        return {"topics": topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list topics: {e}")


@app.delete("/delete-topic")
def delete_topic(topic_name: str = Query(..., description="Name of topic to delete")):
    """Delete a specific Kafka topic"""
    try:
        fs = admin_client.delete_topics([topic_name], operation_timeout=30)
        for topic, f in fs.items():
            try:
                f.result()  # The result is None if success
                return {"message": f"Topic '{topic}' deleted successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to delete topic '{topic}': {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))