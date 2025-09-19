from confluent_kafka import Consumer, KafkaError
import json
import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any
import uuid

from .kafka_service import kafka_service

logger = logging.getLogger(__name__)

class KafkaConsumerService:
    def __init__(self):
        self.broker = os.getenv("KAFKA_BROKER", "kafka:29092")
        self.group_id = "document-processor-group"
        self.topics = ["user-applications"]

        # Consumer configuration
        self.consumer_conf = {
            "bootstrap.servers": self.broker,
            "group.id": self.group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 1000
        }

        self.consumer = None
        self.running = False

    def start_consumer(self):
        """Start the Kafka consumer"""
        try:
            self.consumer = Consumer(self.consumer_conf)
            self.consumer.subscribe(self.topics)
            self.running = True

            logger.info(f"Sarah (Document Intelligence Agent): Kafka consumer started")
            logger.info(f"Broker: {self.broker}")
            logger.info(f"Group ID: {self.group_id}")
            logger.info(f"Topics: {self.topics}")

            # Start consuming in background
            asyncio.create_task(self._consume_messages())

        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise

    async def _consume_messages(self):
        """Consume messages from Kafka topics"""
        logger.info("Sarah: Starting to consume user application messages...")

        try:
            while self.running:
                msg = self.consumer.poll(1.0)

                if msg is None:
                    continue

                if msg.error():
                    logger.error(f"Sarah: Consumer error: {msg.error()}")
                    continue

                # Process the message
                await self._process_message(msg)

        except Exception as e:
            logger.error(f"Sarah: Error in message consumption: {e}")
        finally:
            if self.consumer:
                self.consumer.close()

    async def _process_message(self, msg):
        """Process a single Kafka message"""
        try:
            key = msg.key().decode("utf-8") if msg.key() else "no-key"
            value = json.loads(msg.value().decode("utf-8"))
            topic = msg.topic()

            logger.info(f"Sarah (Document Intelligence Agent): Processing application from topic '{topic}' for customer '{key}'")

            if topic == "user-applications":
                await self._process_user_application(key, value)

        except Exception as e:
            logger.error(f"Sarah: Failed to process message: {e}")

    async def _process_user_application(self, application_id: str, application_data: Dict[str, Any]):
        """Process user application submission - simulate document processing"""
        try:
            logger.info(f"Sarah (Document Intelligence Agent): Processing application {application_id}")

            # Update Command Center
            await self._update_command_center(
                agent_id="agent-sarah",
                status="active",
                current_task=f"Processing application documents for {application_data.get('customer_email', 'customer')}",
                activity_log=[
                    f"🆕 NEW APPLICATION: {application_id} received from mobile app",
                    f"📄 Documents required: {', '.join(application_data.get('documents_required', []))}",
                    f"📧 Customer: {application_data.get('customer_email', 'Unknown')}"
                ]
            )

            # Simulate processing time
            await asyncio.sleep(2)

            # Extract document info from application data
            documents_required = application_data.get('documents_required', [])
            customer_email = application_data.get('customer_email', 'unknown@example.com')

            # Process each document type mentioned in the application
            for i, doc_type in enumerate(documents_required):
                await asyncio.sleep(1)  # Simulate processing time for each document

                # Map document types to our internal format
                doc_type_mapping = {
                    'passport': 'passport',
                    'id_card': 'passport',  # Treat ID card as passport for demo
                    'driver_license': 'passport',  # Treat driver license as passport for demo
                    'birth_certificate': 'unknown',
                    'utility_bill': 'bank_statement'
                }

                internal_doc_type = doc_type_mapping.get(doc_type, 'unknown')

                # Simulate OCR results based on document type
                if internal_doc_type == 'passport':
                    extracted_text = f"PASSPORT\nName: {customer_email.split('@')[0].title()}\nNationality: US\nPassport No: A12345678\nDate of Birth: 01/01/1990\nExpiry Date: 01/01/2030"
                    confidence = 92.5
                elif internal_doc_type == 'bank_statement':
                    extracted_text = f"BANK STATEMENT\nAccount Holder: {customer_email.split('@')[0].title()}\nAccount Number: ****1234\nBalance: $5,000.00\nStatement Period: Jan 2024"
                    confidence = 88.0
                else:
                    extracted_text = f"Document content for {doc_type}\nCustomer: {customer_email.split('@')[0].title()}\nDocument verified"
                    confidence = 75.0

                # Update Command Center with processing progress
                progress = f"Document {i+1} of {len(documents_required)}"
                await self._update_command_center(
                    agent_id="agent-sarah",
                    status="active",
                    current_task=f"Extracting text from {doc_type} ({progress})",
                    activity_log=[
                        f"🔤 OCR ACTIVE: Processing {doc_type} document ({confidence:.1f}% confidence)",
                        f"📄 PROGRESS: {progress} documents processed",
                        f"🆕 NEW APPLICATION: {application_id} received from mobile app",
                        f"📧 Customer: {customer_email}"
                    ]
                )

                # Generate mock storage URL
                storage_url = f"supabase://documents/{application_id}/{doc_type}_{uuid.uuid4().hex[:8]}"

                # Publish to forms.submitted.v1 topic for KYC agent
                kafka_success = kafka_service.publish_form_submission(
                    request_id=str(uuid.uuid4()),
                    customer_id=application_id,
                    document_type=internal_doc_type,
                    extracted_text=extracted_text,
                    confidence=confidence,
                    storage_url=storage_url,
                    metadata={
                        "original_application": application_data,
                        "document_index": i,
                        "total_documents": len(documents_required),
                        "processing_method": "simulated_ocr",
                        "customer_email": customer_email
                    }
                )

                if kafka_success:
                    logger.info(f"Sarah: Published {doc_type} results to forms.submitted.v1")
                else:
                    logger.error(f"Sarah: Failed to publish {doc_type} results")

            # Final completion status
            await self._update_command_center(
                agent_id="agent-sarah",
                status="active",
                current_task=f"Application processing completed - {len(documents_required)} documents processed",
                activity_log=[
                    f"🎉 COMPLETED: All {len(documents_required)} documents processed successfully",
                    f"📤 HANDOFF: Data sent to Marcus (KYC Agent) for verification",
                    f"✅ KAFKA: Published to forms.submitted.v1 topic",
                    f"🔤 OCR RESULTS: Average confidence {confidence:.1f}%",
                    f"📧 Customer: {customer_email}"
                ],
                extra_data={"tasksCompleted": len(documents_required)}
            )

            logger.info(f"Sarah: Completed processing application {application_id} with {len(documents_required)} documents")

        except Exception as e:
            logger.error(f"Sarah: Failed to process user application {application_id}: {e}")

            # Update Command Center with error
            await self._update_command_center(
                agent_id="agent-sarah",
                status="error",
                current_task=f"Error processing application {application_id}",
                activity_log=[
                    f"❌ ERROR: Failed to process application - {str(e)}",
                    f"🆕 NEW APPLICATION: {application_id} received from mobile app"
                ]
            )

    async def _update_command_center(self, agent_id: str, status: str, current_task: str, activity_log: list, extra_data: dict = None):
        """Update Command Center with Sarah status"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                agent_update = {
                    "status": status,
                    "currentTask": current_task,
                    "activityLog": activity_log,
                    **(extra_data or {})
                }
                await client.post(
                    f"http://command-center-connector:8006/api/agents/{agent_id}/update",
                    json=agent_update
                )
                logger.info(f"Sarah: Updated Command Center - {current_task}")
        except Exception as e:
            logger.error(f"Sarah: Failed to update Command Center: {e}")

    def stop_consumer(self):
        """Stop the Kafka consumer"""
        self.running = False
        if self.consumer:
            self.consumer.close()
        logger.info("Sarah: Kafka consumer stopped")

# Global instance
kafka_consumer_service = KafkaConsumerService()