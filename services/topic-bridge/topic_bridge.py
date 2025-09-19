"""
Topic Bridge Service
Bridges messages between different topic naming conventions
Maps your system's topics to teammate's topics and vice versa
"""

from confluent_kafka import Consumer, Producer
import json
import os
import threading
import logging
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:29092")

# Topic mappings between systems
TOPIC_MAPPINGS = {
    # Your system -> Teammate's system
    "kyc-submissions": "forms_submitted",
    "kyc-verification": "forms-verified",

    # Teammate's system -> Your system
    "forms_submitted": "kyc-submissions",
    "forms-verified": "kyc-verification",

    # Shared topics (no mapping needed)
    "kyc-alerts": "kyc-alerts",
    "ocr-completed": "ocr-completed"
}

class TopicBridge:
    def __init__(self):
        self.producer = Producer({
            "bootstrap.servers": KAFKA_BROKER,
            "client.id": "topic-bridge"
        })

        self.consumers = {}
        self.threads = []

    def delivery_report(self, err, msg):
        """Callback for message delivery confirmation"""
        if err:
            logger.error(f"Delivery failed for record {msg.key()}: {err}")
        else:
            logger.info(f"Message bridged from {msg.topic()} successfully")

    def bridge_message(self, source_topic: str, target_topic: str, key: str, value: Dict[str, Any]):
        """Bridge a message from source topic to target topic"""
        try:
            # Add metadata about bridging
            value["_bridged_from"] = source_topic
            value["_bridged_to"] = target_topic
            value["_bridge_timestamp"] = os.popen('date -u +"%Y-%m-%dT%H:%M:%S.%3NZ"').read().strip()

            self.producer.produce(
                topic=target_topic,
                key=key,
                value=json.dumps(value),
                callback=self.delivery_report
            )
            self.producer.poll(0)

            logger.info(f"Bridged message: {source_topic} -> {target_topic} (key: {key})")

        except Exception as e:
            logger.error(f"Failed to bridge message: {e}")

    def consume_and_bridge(self, source_topic: str, target_topic: str):
        """Consumer thread for a specific topic mapping"""
        consumer = Consumer({
            "bootstrap.servers": KAFKA_BROKER,
            "group.id": f"bridge-{source_topic}-to-{target_topic}",
            "auto.offset.reset": "latest",  # Only bridge new messages
            "enable.auto.commit": True
        })

        consumer.subscribe([source_topic])
        logger.info(f"Started bridge: {source_topic} -> {target_topic}")

        try:
            while True:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error(f"Consumer error on {source_topic}: {msg.error()}")
                    continue

                try:
                    key = msg.key().decode("utf-8") if msg.key() else None
                    value = json.loads(msg.value().decode("utf-8"))

                    # Check if message was already bridged (avoid loops)
                    if "_bridged_from" not in value:
                        self.bridge_message(source_topic, target_topic, key, value)
                    else:
                        logger.debug(f"Skipping already bridged message on {source_topic}")

                except Exception as e:
                    logger.error(f"Error processing message from {source_topic}: {e}")

        except KeyboardInterrupt:
            logger.info(f"Stopping bridge: {source_topic} -> {target_topic}")
        finally:
            consumer.close()

    def start(self):
        """Start all topic bridges"""
        logger.info("Starting Topic Bridge Service")
        logger.info(f"Kafka Broker: {KAFKA_BROKER}")
        logger.info(f"Topic Mappings: {TOPIC_MAPPINGS}")

        # Create consumer threads for each mapping
        for source, target in TOPIC_MAPPINGS.items():
            if source != target:  # Don't bridge topics to themselves
                thread = threading.Thread(
                    target=self.consume_and_bridge,
                    args=(source, target),
                    daemon=True
                )
                thread.start()
                self.threads.append(thread)

        logger.info(f"Started {len(self.threads)} bridge threads")

        # Keep main thread alive
        try:
            while True:
                self.producer.poll(1.0)
        except KeyboardInterrupt:
            logger.info("Shutting down Topic Bridge Service")
            self.producer.flush()

if __name__ == "__main__":
    bridge = TopicBridge()
    bridge.start()