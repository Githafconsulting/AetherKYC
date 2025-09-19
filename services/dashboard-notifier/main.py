from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from confluent_kafka import Consumer
import json
import asyncio
import logging
from typing import Dict, Set
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dashboard Notification Service", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.client_info: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_info[client_id] = {
            "websocket": websocket,
            "connected_at": datetime.utcnow().isoformat(),
            "dashboard_type": "general"
        }
        logger.info(f"Dashboard client {client_id} connected")

    def disconnect(self, websocket: WebSocket, client_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if client_id in self.client_info:
            del self.client_info[client_id]
        logger.info(f"Dashboard client {client_id} disconnected")

    async def send_to_all(self, message: dict):
        """Send message to all connected dashboards"""
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.add(websocket)

        # Remove disconnected clients
        for ws in disconnected:
            self.active_connections.discard(ws)

    async def send_to_client(self, client_id: str, message: dict):
        """Send message to specific dashboard client"""
        if client_id in self.client_info:
            try:
                websocket = self.client_info[client_id]["websocket"]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                self.disconnect(websocket, client_id)

manager = ConnectionManager()

# Kafka configuration
KAFKA_CONFIG = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'dashboard-notifier-group',
    'auto.offset.reset': 'latest',
    'enable.auto.commit': True
}

# Topics to monitor for dashboard updates
MONITORED_TOPICS = [
    'ocr-completed',
    'kyc-submissions',
    'kyc-verification',
    'kyc-alerts',
    'forms_submitted',
    'forms-verified'
]

class DashboardNotifier:
    def __init__(self):
        self.consumer = Consumer(KAFKA_CONFIG)
        self.consumer.subscribe(MONITORED_TOPICS)
        self.running = False

    async def start_consuming(self):
        """Start consuming Kafka messages and sending to dashboards"""
        self.running = True
        logger.info("Starting dashboard notification service")

        while self.running:
            try:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    await asyncio.sleep(0.1)
                    continue

                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue

                # Process the message and send to dashboard
                await self.process_message(msg)

            except Exception as e:
                logger.error(f"Error in message processing: {e}")
                await asyncio.sleep(1)

    async def process_message(self, msg):
        """Process Kafka message and format for dashboard"""
        try:
            topic = msg.topic()
            key = msg.key().decode('utf-8') if msg.key() else "unknown"
            value = json.loads(msg.value().decode('utf-8'))

            # Create dashboard notification
            notification = self.format_dashboard_message(topic, key, value)

            # Send to all connected dashboards
            await manager.send_to_all(notification)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def format_dashboard_message(self, topic: str, key: str, value: dict) -> dict:
        """Format message for dashboard consumption"""
        timestamp = datetime.utcnow().isoformat()

        # Base notification structure
        notification = {
            "id": str(uuid.uuid4()),
            "timestamp": timestamp,
            "topic": topic,
            "customer_id": key,
            "type": self.get_notification_type(topic),
            "status": value.get("status", "unknown"),
            "data": value
        }

        # Customize based on topic
        if topic == "ocr-completed":
            notification.update({
                "title": "OCR Processing Complete",
                "message": f"Document processed for customer {key}",
                "level": "success" if value.get("confidence", 0) > 80 else "warning",
                "details": {
                    "document_type": value.get("document_type"),
                    "confidence": value.get("confidence"),
                    "extracted_text_length": len(value.get("extracted_text", "")),
                    "processing_time": value.get("processing_time")
                }
            })

        elif topic in ["kyc-submissions", "forms_submitted"]:
            notification.update({
                "title": "New Verification Request",
                "message": f"Document submitted for verification - {key}",
                "level": "info",
                "details": {
                    "document_type": value.get("document_type"),
                    "country": value.get("country"),
                    "request_id": value.get("request_id")
                }
            })

        elif topic in ["kyc-verification", "forms-verified"]:
            status = value.get("verification_result", "unknown")
            level = "success" if status == "PASSED" else "warning" if status == "MANUAL_REVIEW_REQUIRED" else "error"

            notification.update({
                "title": "Verification Complete",
                "message": f"Verification {status} for customer {key}",
                "level": level,
                "details": {
                    "verification_result": status,
                    "confidence_score": value.get("confidence_score"),
                    "risk_score": value.get("risk_score"),
                    "checks_performed": value.get("checks_performed", [])
                }
            })

        elif topic == "kyc-alerts":
            notification.update({
                "title": "System Alert",
                "message": f"Alert: {value.get('alert_reason', 'Unknown issue')}",
                "level": "error",
                "details": {
                    "alert_reason": value.get("alert_reason"),
                    "document_type": value.get("document_type"),
                    "error_details": value.get("error")
                }
            })

        return notification

    def get_notification_type(self, topic: str) -> str:
        """Get notification type based on topic"""
        type_mapping = {
            "ocr-completed": "document_processing",
            "kyc-submissions": "verification_request",
            "kyc-verification": "verification_result",
            "kyc-alerts": "system_alert",
            "forms_submitted": "form_submission",
            "forms-verified": "form_verification"
        }
        return type_mapping.get(topic, "general")

    def stop(self):
        """Stop the notification service"""
        self.running = False
        self.consumer.close()

# Global notifier instance
notifier = DashboardNotifier()

@app.on_event("startup")
async def startup_event():
    """Start the Kafka consumer on startup"""
    asyncio.create_task(notifier.start_consuming())

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    notifier.stop()

@app.websocket("/ws/dashboard/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for dashboard connections"""
    await manager.connect(websocket, client_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()

            # Handle dashboard commands
            try:
                command = json.loads(data)
                if command.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": datetime.utcnow().isoformat()}))
                elif command.get("type") == "subscribe":
                    # Handle topic subscription preferences
                    topics = command.get("topics", [])
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "topics": topics,
                        "message": f"Subscribed to {len(topics)} topics"
                    }))
            except json.JSONDecodeError:
                # Handle non-JSON messages
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "dashboard-notifier",
        "active_connections": len(manager.active_connections),
        "monitored_topics": MONITORED_TOPICS,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    return {
        "active_connections": len(manager.active_connections),
        "clients": list(manager.client_info.keys()),
        "monitored_topics": MONITORED_TOPICS,
        "kafka_config": {k: v for k, v in KAFKA_CONFIG.items() if k != 'bootstrap.servers'}
    }

@app.post("/send-test-notification")
async def send_test_notification():
    """Send a test notification to all dashboards"""
    test_notification = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "topic": "test",
        "customer_id": "TEST_USER",
        "type": "test",
        "title": "Test Notification",
        "message": "This is a test notification from the dashboard service",
        "level": "info",
        "status": "test",
        "data": {"test": True}
    }

    await manager.send_to_all(test_notification)
    return {"message": "Test notification sent", "connections": len(manager.active_connections)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)