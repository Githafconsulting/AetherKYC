from confluent_kafka import Producer, Consumer
import json

def get_producer():
    return Producer({"bootstrap.servers": "localhost:9092"})

def get_consumer(group_id, topics):
    consumer = Consumer({
        "bootstrap.servers": "localhost:9092",
        "group.id": group_id,
        "auto.offset.reset": "earliest"
    })
    consumer.subscribe(topics)
    return consumer

def publish_message(producer, topic, key, value):
    producer.produce(
        topic,
        key=key,
        value=json.dumps(value).encode("utf-8")
    )
    producer.flush()
