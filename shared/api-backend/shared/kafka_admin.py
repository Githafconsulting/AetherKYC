# shared/kafka_admin.py
from confluent_kafka.admin import AdminClient, NewTopic
import os

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

admin = AdminClient({"bootstrap.servers": BOOTSTRAP})

def create_topics(topics: list):
    """Create Kafka topics if they don't exist."""
    new_topics = [NewTopic(t, num_partitions=3, replication_factor=1) for t in topics]
    fs = admin.create_topics(new_topics, request_timeout=15)

    for topic, f in fs.items():
        try:
            f.result()
            print(f"✅ Topic {topic} created or already exists")
        except Exception as e:
            print(f"⚠️ Failed to create topic {topic}: {e}")

if __name__ == "__main__":
    topics = [
        "kyc.document.uploaded",
        "kyc.document.ocr_processed",
        "kyc.document.ocr_request",
        "kyc.customer.verified",
        "kyc.document.ocr_result"
    ]
    create_topics(topics)
