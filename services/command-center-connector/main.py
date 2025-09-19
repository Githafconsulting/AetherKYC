from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime
from confluent_kafka import Consumer, Producer
import threading
import redis
import os
from colorama import init, Fore, Style

init(autoreset=True)

app = FastAPI(title="Command Center Connector", version="1.0.0")

# CORS configuration for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"{Fore.GREEN}✓ WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"{Fore.YELLOW}✗ WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected WebSocket clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Redis connection for agent state persistence
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

# Agent mapping: service names to Command Center agent names
AGENT_MAPPING = {
    "document-processor": {"name": "Sarah", "type": "Document Intelligence Agent", "department": "Compliance"},
    "ocr-agent": {"name": "Sarah", "type": "Document Intelligence Agent", "department": "Compliance"},
    "kyc-agent": {"name": "Marcus", "type": "KYC Agent", "department": "Compliance"},
    "verification-service": {"name": "Marcus", "type": "KYC Agent", "department": "Compliance"},
    "account-creation": {"name": "Elena", "type": "Account Creation Agent", "department": "Compliance"},
    "notification-service": {"name": "David", "type": "Notification Agent", "department": "Compliance"},
    "compliance-agent": {"name": "Maya", "type": "Compliance Agent", "department": "Compliance"},
    "customer-support": {"name": "Alex", "type": "Customer Support Agent", "department": "Customer Service"},
    "fraud-detection": {"name": "Jordan", "type": "Fraud Detection Agent", "department": "Risk"},
    "transaction-monitor": {"name": "Riley", "type": "Transaction Monitoring Agent", "department": "Risk"},
}

# In-memory agent state
agent_states = {}

def initialize_agent_states():
    """Initialize all agents with default state"""
    for service_name, agent_info in AGENT_MAPPING.items():
        agent_id = f"agent-{agent_info['name'].lower()}"
        agent_states[agent_id] = {
            "id": agent_id,
            "name": agent_info["name"],
            "type": agent_info["type"],
            "department": agent_info["department"],
            "status": "idle",
            "currentTask": "Waiting for tasks...",
            "tasksCompleted": 0,
            "tasksToday": 0,
            "successRate": 100.0,
            "responseTime": 0,
            "activityLog": [f"Agent {agent_info['name']} initialized"],
            "lastUpdate": datetime.now().isoformat()
        }
        # Persist to Redis (convert lists to JSON strings)
        redis_data = {k: json.dumps(v) if isinstance(v, list) else str(v) for k, v in agent_states[agent_id].items()}
        redis_client.hset(f"agent:{agent_id}", mapping=redis_data)

# Kafka consumer configuration
def create_kafka_consumer():
    return Consumer({
        'bootstrap.servers': os.getenv('KAFKA_BROKER', 'kafka:29092'),
        'group.id': 'command-center-connector',
        'auto.offset.reset': 'latest',
        'enable.auto.commit': True
    })

def kafka_consumer_thread():
    """Background thread to consume Kafka messages and update agent states"""
    consumer = create_kafka_consumer()

    # Subscribe to all relevant topics
    topics = [
        'ocr-completed',
        'kyc-submissions',
        'kyc-verification',
        'KYC.verification.completed.v1',
        'Account.creation.completed.v1',
        'kyc-alerts',
        'forms_submitted',
        'forms-verified',
        'agent-status',
        'agent-metrics'
    ]

    consumer.subscribe(topics)
    print(f"{Fore.CYAN}📡 Subscribed to Kafka topics: {topics}")

    while True:
        try:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"{Fore.RED}Kafka error: {msg.error()}")
                continue

            topic = msg.topic()
            value = json.loads(msg.value().decode('utf-8')) if msg.value() else {}

            # Process message and update agent state
            asyncio.run(process_kafka_message(topic, value))

        except Exception as e:
            print(f"{Fore.RED}Error processing message: {e}")

async def process_kafka_message(topic: str, message: dict):
    """Process Kafka message and update agent state"""
    print(f"{Fore.BLUE}📨 Processing: {topic}")

    # Determine which agent should handle this message
    agent_update = None

    if topic == "ocr-completed":
        agent_id = "agent-sarah"
        if agent_id in agent_states:
            agent_states[agent_id]["status"] = "active"
            agent_states[agent_id]["currentTask"] = f"Processed OCR for document {message.get('document_id', 'unknown')}"
            agent_states[agent_id]["tasksCompleted"] += 1
            agent_states[agent_id]["tasksToday"] += 1
            agent_states[agent_id]["activityLog"].insert(0, f"OCR completed: {message.get('filename', 'document')}")
            agent_states[agent_id]["activityLog"] = agent_states[agent_id]["activityLog"][:10]  # Keep last 10
            agent_update = agent_states[agent_id]

    elif topic in ["kyc-submissions", "kyc-verification"]:
        agent_id = "agent-marcus"
        if agent_id in agent_states:
            agent_states[agent_id]["status"] = "active"
            if topic == "kyc-submissions":
                agent_states[agent_id]["currentTask"] = f"Verifying KYC for customer {message.get('customer_id', 'unknown')}"
            else:
                agent_states[agent_id]["currentTask"] = f"KYC verification completed"
                agent_states[agent_id]["tasksCompleted"] += 1
                agent_states[agent_id]["tasksToday"] += 1

                # Trigger David (Notification Agent) for KYC completion
                david_id = "agent-david"
                if david_id in agent_states:
                    verification_result = message.get('verification_result', message.get('status', 'completed'))
                    customer_id = message.get('customer_id', 'unknown')
                    agent_states[david_id]["status"] = "active"
                    agent_states[david_id]["currentTask"] = f"Sending KYC {verification_result} notification for {customer_id}"
                    agent_states[david_id]["tasksCompleted"] += 1
                    agent_states[david_id]["tasksToday"] += 1
                    agent_states[david_id]["activityLog"].insert(0, f"📧 Sent KYC {verification_result} email to customer {customer_id}")
                    agent_states[david_id]["activityLog"] = agent_states[david_id]["activityLog"][:10]

            agent_states[agent_id]["activityLog"].insert(0, f"KYC: {message.get('status', topic)}")
            agent_states[agent_id]["activityLog"] = agent_states[agent_id]["activityLog"][:10]
            agent_update = agent_states[agent_id]

    elif topic == "forms_submitted":
        agent_id = "agent-elena"
        if agent_id in agent_states:
            agent_states[agent_id]["status"] = "active"
            agent_states[agent_id]["currentTask"] = f"Creating account from form submission"
            agent_states[agent_id]["tasksCompleted"] += 1
            agent_states[agent_id]["tasksToday"] += 1
            agent_states[agent_id]["activityLog"].insert(0, f"Form received: {message.get('form_id', 'new')}")
            agent_states[agent_id]["activityLog"] = agent_states[agent_id]["activityLog"][:10]
            agent_update = agent_states[agent_id]

    elif topic == "KYC.verification.completed.v1":
        # Marcus completed KYC - trigger David for notifications
        customer_id = message.get('customer_id', 'unknown')
        decision = message.get('decision', 'UNKNOWN')

        # Update David (Notification Agent)
        david_id = "agent-david"
        if david_id in agent_states:
            agent_states[david_id]["status"] = "active"
            if decision == "APPROVED":
                agent_states[david_id]["currentTask"] = f"Sending welcome email to customer {customer_id}"
                agent_states[david_id]["activityLog"].insert(0, f"📧 Welcome email sent - KYC APPROVED for {customer_id}")
            elif decision == "REVIEW":
                agent_states[david_id]["currentTask"] = f"Sending additional documents request to {customer_id}"
                agent_states[david_id]["activityLog"].insert(0, f"📝 Document request sent - KYC REVIEW for {customer_id}")
            else:
                agent_states[david_id]["currentTask"] = f"Sending KYC rejection notice to {customer_id}"
                agent_states[david_id]["activityLog"].insert(0, f"❌ Rejection notice sent - KYC DECLINED for {customer_id}")

            agent_states[david_id]["tasksCompleted"] += 1
            agent_states[david_id]["tasksToday"] += 1
            agent_states[david_id]["activityLog"] = agent_states[david_id]["activityLog"][:10]
            agent_update = agent_states[david_id]

    elif topic == "Account.creation.completed.v1":
        # Elena completed account creation - trigger David for mobile notifications
        customer_id = message.get('customer_id', 'unknown')
        account_data = message.get('account_data', {})
        status = message.get('status', 'UNKNOWN')

        if status == "SUCCESS":
            account_number = account_data.get('account_number', 'unknown')
            card_number = account_data.get('card_number', 'unknown')

            # Update David (Notification Agent) for mobile notifications
            david_id = "agent-david"
            if david_id in agent_states:
                agent_states[david_id]["status"] = "active"
                agent_states[david_id]["currentTask"] = f"Sending account ready notification to mobile app for {customer_id}"
                agent_states[david_id]["activityLog"].insert(0, f"📱 MOBILE NOTIFICATION: Account #{account_number} ready")
                agent_states[david_id]["activityLog"].insert(0, f"🎉 ACCOUNT CREATED: Welcome to digital banking!")
                agent_states[david_id]["activityLog"].insert(0, f"💳 CARD ISSUED: Debit card #{card_number} activated")

                agent_states[david_id]["tasksCompleted"] += 1
                agent_states[david_id]["tasksToday"] += 1
                agent_states[david_id]["activityLog"] = agent_states[david_id]["activityLog"][:10]
                agent_update = agent_states[david_id]

    elif topic == "kyc-alerts":
        agent_id = "agent-maya"
        if agent_id in agent_states:
            agent_states[agent_id]["status"] = "active"
            agent_states[agent_id]["currentTask"] = f"Reviewing compliance alert"
            agent_states[agent_id]["activityLog"].insert(0, f"Alert: {message.get('alert_type', 'compliance check')}")
            agent_states[agent_id]["activityLog"] = agent_states[agent_id]["activityLog"][:10]
            agent_update = agent_states[agent_id]

    # Broadcast update to all WebSocket clients
    if agent_update:
        agent_update["lastUpdate"] = datetime.now().isoformat()
        # Save to Redis (convert lists to JSON strings)
        redis_data = {k: json.dumps(v) if isinstance(v, list) else str(v) for k, v in agent_update.items()}
        redis_client.hset(f"agent:{agent_update['id']}", mapping=redis_data)
        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "agent_update",
            "agent": agent_update
        })
        print(f"{Fore.GREEN}✓ Updated {agent_update['name']} - {agent_update['currentTask']}")

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Send initial agent states
    await websocket.send_json({
        "type": "initial_state",
        "agents": list(agent_states.values())
    })

    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle control commands from frontend
            if message.get("type") == "control":
                agent_id = message.get("agentId")
                action = message.get("action")

                if agent_id in agent_states:
                    if action == "start":
                        agent_states[agent_id]["status"] = "active"
                        agent_states[agent_id]["currentTask"] = "Starting up..."
                        agent_states[agent_id]["activityLog"].insert(0, "Agent started by operator")
                    elif action == "stop":
                        agent_states[agent_id]["status"] = "idle"
                        agent_states[agent_id]["currentTask"] = "Stopped by operator"
                        agent_states[agent_id]["activityLog"].insert(0, "Agent stopped by operator")
                    elif action == "pause":
                        agent_states[agent_id]["status"] = "paused"
                        agent_states[agent_id]["currentTask"] = "Paused by operator"
                        agent_states[agent_id]["activityLog"].insert(0, "Agent paused by operator")

                    agent_states[agent_id]["activityLog"] = agent_states[agent_id]["activityLog"][:10]
                    agent_states[agent_id]["lastUpdate"] = datetime.now().isoformat()

                    # Save to Redis (convert lists to JSON strings)
                    redis_data = {k: json.dumps(v) if isinstance(v, list) else str(v) for k, v in agent_states[agent_id].items()}
                    redis_client.hset(f"agent:{agent_id}", mapping=redis_data)

                    # Broadcast update
                    await manager.broadcast({
                        "type": "agent_update",
                        "agent": agent_states[agent_id]
                    })

    except WebSocketDisconnect:
        manager.disconnect(websocket)

# REST API endpoints for agent management
@app.get("/api/agents")
async def get_agents():
    """Get all agent states - active agents at the top"""
    agents = list(agent_states.values())
    # Sort: active agents first, then by status priority
    status_priority = {'active': 0, 'processing': 1, 'paused': 2, 'idle': 3, 'error': 4}
    agents.sort(key=lambda x: (status_priority.get(x.get('status', 'idle'), 5), x.get('name', '')))
    return agents

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get specific agent state"""
    if agent_id in agent_states:
        return agent_states[agent_id]
    return {"error": "Agent not found"}

@app.post("/api/agents/{agent_id}/update")
async def update_agent(agent_id: str, update: dict):
    """Update agent state (for service self-reporting)"""
    if agent_id in agent_states:
        for key, value in update.items():
            if key in agent_states[agent_id]:
                agent_states[agent_id][key] = value

        agent_states[agent_id]["lastUpdate"] = datetime.now().isoformat()

        # Save to Redis (convert lists to JSON strings)
        redis_data = {k: json.dumps(v) if isinstance(v, list) else str(v) for k, v in agent_states[agent_id].items()}
        redis_client.hset(f"agent:{agent_id}", mapping=redis_data)

        # Broadcast update
        await manager.broadcast({
            "type": "agent_update",
            "agent": agent_states[agent_id]
        })

        return {"status": "success", "agent": agent_states[agent_id]}

    return {"error": "Agent not found"}

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    print(f"{Fore.CYAN}🚀 Command Center Connector starting...")

    # Initialize agent states
    initialize_agent_states()
    print(f"{Fore.GREEN}✓ Initialized {len(agent_states)} agents")

    # Start Kafka consumer in background thread
    consumer_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    consumer_thread.start()
    print(f"{Fore.GREEN}✓ Kafka consumer thread started")

    print(f"{Fore.CYAN}🎯 Command Center Connector ready!")
    print(f"{Fore.YELLOW}WebSocket: ws://localhost:8006/ws")
    print(f"{Fore.YELLOW}API: http://localhost:8006/api/agents")

@app.get("/")
async def root():
    return {
        "service": "Command Center Connector",
        "status": "running",
        "endpoints": {
            "websocket": "/ws",
            "agents": "/api/agents",
            "docs": "/docs"
        },
        "connected_agents": len(agent_states),
        "active_connections": len(manager.active_connections)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)