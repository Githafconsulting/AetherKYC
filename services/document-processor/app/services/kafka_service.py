from confluent_kafka import Producer
import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class KafkaService:
    def __init__(self):
        self.broker = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.producer = Producer({"bootstrap.servers": self.broker})

    def delivery_report(self, err, msg):
        """Delivery callback for Kafka producer"""
        if err:
            logger.error(f"Delivery failed for record {msg.key()}: {err}")
        else:
            logger.info(f"Record {msg.key()} successfully produced to {msg.topic()} [{msg.partition()}]")

    def publish_form_submission(self,
                          request_id: str,
                          customer_id: Optional[str],
                          document_type: str,
                          extracted_text: str,
                          confidence: float,
                          storage_url: str,
                          metadata: Dict[str, Any] = None) -> bool:
        """Publish form submission with OCR results to Kafka"""

        # Create message payload for forms.submitted.v1
        message = {
            "request_id": request_id,
            "customer_id": customer_id or f"customer_{uuid.uuid4().hex[:8]}",
            "document_type": document_type,
            "extracted_text": extracted_text,
            "confidence": confidence,
            "storage_url": storage_url,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "status": "ocr_completed",
            "processing_stage": "document_intelligence_complete",
            "ready_for_kyc": True
        }

        try:
            # Publish to forms.submitted.v1 topic (correct workflow)
            self.producer.produce(
                topic="forms.submitted.v1",
                key=message["customer_id"],
                value=json.dumps(message),
                callback=self.delivery_report
            )

            # Log successful publication
            logger.info(f"Form submission published to forms.submitted.v1 for customer {message['customer_id']}")

            # Flush to ensure delivery
            self.producer.flush()
            return True

        except Exception as e:
            logger.error(f"Failed to publish OCR result to Kafka: {e}")
            return False

    # Backward compatibility alias
    def publish_ocr_result(self, *args, **kwargs):
        """Backward compatibility - redirects to publish_form_submission"""
        return self.publish_form_submission(*args, **kwargs)

    def close(self):
        """Close the Kafka producer"""
        if self.producer:
            self.producer.flush()

# Global instance
kafka_service = KafkaService()