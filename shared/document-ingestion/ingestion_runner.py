import json
from shared.kafka_client import get_consumer
from ingestion_graph import graph
from model.state import IngestionState

GROUP_ID = "ingestion_runner"
TOPIC = ["kyc.document.uploaded"]

consumer = get_consumer(GROUP_ID, TOPIC)

print("🚀 Ingestion runner started...")

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print("⚠️ Kafka error:", msg.error())
        continue

    payload = json.loads(msg.value().decode("utf-8"))
    document_id = payload.get("document_id")

    print(f"📥 Received message for document {document_id}")

    # Build initial state
    state = IngestionState(kafka_message=payload)

    # Run graph
    result = graph.invoke(state)

    print(f"✅ Graph finished for {document_id}, final state: {result}")