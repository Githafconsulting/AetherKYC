# shared/kafka_client.py
from confluent_kafka import Producer, Consumer
import json
import os

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

# --- Producer ---
_prod = None
def get_producer():
    global _prod
    if _prod is None:
        _prod = Producer({"bootstrap.servers": BOOTSTRAP})
    return _prod

def publish(topic: str, key: str, value: dict):
    p = get_producer()
    p.produce(topic, key=key, value=json.dumps(value).encode("utf-8"))
    p.flush()

# --- Consumer ---
def get_consumer(group_id: str, topics: list):
    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": group_id,
        "auto.offset.reset": "earliest"
    })
    consumer.subscribe(topics)
    return consumer