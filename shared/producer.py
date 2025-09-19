import random
import uuid
import json

from kafka_client import get_producer, publish_message

producer = get_producer()

# List of possible document types
doc_types = ["passport", "driving licence", "residence permit"]

# Generate a unique ID using uuid4()
message_id = str(uuid.uuid4())

# Generate a random customer ID
customer_id = f"cust-{random.randint(100, 999)}"

# Select a random document type from the list
random_doc_type = random.choice(doc_types)

# Generate a unique URL for the document
document_url = f"http://example.com/docs/{message_id}-{random_doc_type}.png"

kafka_message = {
    "id": message_id,
    "customer_id": customer_id,
    "document": {
        "url": document_url,
        "type": random_doc_type
    }
}

# The key for Kafka must still be a bytes-like object
# The value is now passed directly as a dictionary
# The kafka_client or producer configuration handles the serialization
publish_message(producer, 'ingestion-topic', key=message_id.encode('utf-8'), value=kafka_message)

print(f"Ingestion request published for job {kafka_message['id']}")
print(f"Document type: {random_doc_type}")
print(f"Document URL: {document_url}")