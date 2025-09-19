# Document Processing & Ingestion Platform

A comprehensive document processing and ingestion system that combines OCR extraction, intelligent document routing, KYC verification, and real-time message streaming using Kafka. This platform handles complex document workflows with multiple processing pipelines and cross-system communication.

## 🏗️ Architecture

```
Document Upload → OCR Agent → Kafka Topics → KYC Agent → Verification Results
                     ↓
              Message Router
                     ↓
              Topic Bridge Service
                     ↓
            Forms Processing API
                     ↓
            System Monitoring
```

## 📁 Project Structure

```
document-processing-platform/
├── README.md                          # Project documentation
├── docker-compose.yml                 # System orchestration
├── .env                              # Environment configuration
├── .env.example                      # Environment template
│
├── services/                          # Core Processing Services
│   ├── ocr-agent/                    # Document OCR processing
│   │   ├── app/
│   │   │   ├── services/
│   │   │   │   ├── kafka_service.py  # Kafka integration
│   │   │   │   └── ocr_service.py    # OCR processing engine
│   │   │   ├── main.py               # FastAPI application
│   │   │   ├── routes.py             # API endpoints
│   │   │   └── models.py             # Data models
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── kyc-agent/                    # Identity verification service
│   │   ├── app/
│   │   │   ├── services/
│   │   │   │   ├── kafka_consumer_service.py  # Message consumer
│   │   │   │   └── kyc_service.py             # KYC verification engine
│   │   │   ├── main.py               # FastAPI application
│   │   │   ├── routes.py             # Verification endpoints
│   │   │   └── models.py             # Verification models
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── message-router/               # Primary message routing service
│   │   ├── main.py                   # Kafka FastAPI router
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── forms-api/                    # Forms processing API
│   │   ├── main.py                   # Forms FastAPI service
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── topic-bridge/                 # Cross-system message bridge
│       ├── topic_bridge.py           # Message translation service
│       ├── requirements.txt
│       └── Dockerfile
│
├── consumers/                         # Message Processing Consumers
│   ├── monitoring-service/           # System-wide monitoring
│   │   ├── unified_listener.py       # Real-time system monitor
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── kyc-listener/                 # KYC-specific message consumer
│   │   ├── kyc_listener.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── forms-listener/               # Forms processing consumer
│       ├── kyc_listener.py
│       ├── requirements.txt
│       └── Dockerfile
│
├── shared/                           # Shared Libraries & Components
│   ├── api-backend/                  # Backend API utilities
│   │   ├── shared/
│   │   │   ├── kafka_admin.py        # Kafka administration
│   │   │   ├── kafka_client.py       # Kafka client utilities
│   │   │   └── supabase_client.py    # Database client
│   │   └── main.py                   # Backend service
│   │
│   ├── document-ingestion/           # Advanced document ingestion
│   │   ├── ingestion_graph.py        # Processing workflow graph
│   │   ├── ingestion_runner.py       # Ingestion orchestrator
│   │   ├── nodes/                    # Processing nodes
│   │   │   ├── ocr_worker_node.py    # OCR processing node
│   │   │   └── ack_control_center_node.py  # Acknowledgment control
│   │   └── shared/                   # Ingestion utilities
│   │
│   ├── kafka_client.py               # Global Kafka utilities
│   ├── producer.py                   # Message producers
│   └── listen_all.py                 # Universal message listeners
│
├── infrastructure/                   # System Infrastructure
│   ├── kafka/logs/                  # Kafka storage
│   └── redis/data/                  # Redis cache storage
│
├── uploads/                         # Document upload storage
└── docs/                           # Additional documentation
```

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Navigate to the platform
cd document-processing-platform

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Start All Services
```bash
# Start the entire platform
docker-compose up -d

# Watch logs
docker-compose logs -f
```

### 3. Test the Platform

#### Document Processing Pipeline
```bash
# Upload document for OCR processing
curl -X POST "http://localhost:8001/ocr/process" \
  -F "file=@sample-document.jpg" \
  -F "language=eng"

# Submit document for KYC verification
curl -X POST "http://localhost:8000/submit-kyc?topic_type=submission" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST_001",
    "document_type": "passport",
    "document_number": "P123456789",
    "country": "US"
  }'
```

#### Forms Processing Pipeline
```bash
# Submit through forms API
curl -X POST "http://localhost:8003/submit-kyc?topic_type=submission" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "FORM_001",
    "document_type": "id_card",
    "document_number": "ID987654321",
    "country": "UK"
  }'
```

#### System Monitoring
```bash
# Watch real-time processing
docker logs -f monitoring-service

# Check system topics
curl http://localhost:8000/list-topics
curl http://localhost:8003/list-topics
```

## 🔄 Message Flow & Topics

### Core Message Topics

| Topic Name | Purpose | Producer | Consumer |
|------------|---------|----------|----------|
| `ocr-completed` | OCR processing results | OCR Agent | KYC Agent, Monitoring |
| `kyc-submissions` | Document verification requests | Message Router | KYC Agent |
| `kyc-verification` | Verification results | KYC Agent | Monitoring |
| `kyc-alerts` | System alerts & warnings | All Services | Monitoring |
| `forms_submitted` | Forms processing requests | Forms API | Forms Listener |
| `forms-verified` | Forms verification results | Forms API | Monitoring |

### Cross-System Communication
The **Topic Bridge Service** automatically translates messages between different naming conventions:

```
Document Router System    ←→    Forms Processing System
    kyc-submissions      ←→       forms_submitted
    kyc-verification     ←→       forms-verified
    kyc-alerts          =         kyc-alerts (shared)
```

## 🌐 Service Endpoints

### OCR Agent (Port 8001)
- `POST /ocr/process` - Process document with OCR
- `GET /ocr/result/{id}` - Retrieve OCR results
- `GET /ocr/health` - Service health check
- `GET /docs` - API documentation

### KYC Agent (Port 8002)
- `POST /kyc/verify` - Verify identity documents
- `GET /kyc/status/{id}` - Check verification status
- `GET /kyc/health` - Service health check
- `GET /docs` - API documentation

### Message Router (Port 8000)
- `POST /submit-kyc` - Submit KYC requests
- `GET /list-topics` - List available Kafka topics
- `DELETE /delete-topic` - Remove topics
- `GET /docs` - API documentation

### Forms API (Port 8003)
- `POST /submit-kyc` - Submit forms for processing
- `GET /list-topics` - List forms-related topics
- `DELETE /delete-topic` - Topic management
- `GET /docs` - API documentation

## 🎨 System Monitoring

The **Monitoring Service** provides real-time colored logging for all system activities:

- 🟦 **OCR-COMPLETED** - Document OCR processing results
- 🟩 **KYC-SUBMISSIONS** - Document verification requests
- 🟨 **KYC-VERIFICATION** - Verification processing status
- 🟥 **KYC-ALERTS** - System alerts and errors
- 🟪 **FORMS_SUBMITTED** - Forms processing requests
- 🔵 **FORMS-VERIFIED** - Forms verification results

### Cross-System Message Indicators
```
📨 Bridged from: [source_topic]
📬 Bridged to: [target_topic]
🔄 Cross-System: ROUTER-SYSTEM ↔ FORMS-SYSTEM
```

## 🔧 Development

### Individual Service Development
```bash
# Start specific services
docker-compose up ocr-agent kafka redis

# View service logs
docker-compose logs -f kyc-agent

# Access service container
docker-compose exec ocr-agent bash
```

### Local Development Setup
```bash
# Install service dependencies
cd services/ocr-agent
pip install -r requirements.txt

# Run service locally
uvicorn app.main:app --reload --port 8001
```

## 📊 System Health & Monitoring

### Health Checks
```bash
curl http://localhost:8001/ocr/health         # OCR Agent
curl http://localhost:8002/kyc/health         # KYC Agent
curl http://localhost:8000/list-topics        # Message Router
curl http://localhost:8003/list-topics        # Forms API
```

### Infrastructure Status
```bash
docker-compose ps                             # All services
docker-compose logs --tail=50 -f            # Recent logs
```

### Message Topic Monitoring
```bash
# Monitor all system messages
docker logs -f monitoring-service

# Check topic states
curl http://localhost:8000/list-topics
curl http://localhost:8003/list-topics
```

## 🛠️ Troubleshooting

### Common Issues

1. **Kafka Connection Problems**
   ```bash
   # Verify Kafka health
   docker-compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
   ```

2. **Cross-System Communication Issues**
   ```bash
   # Check topic bridge logs
   docker logs topic-bridge
   ```

3. **Service Port Conflicts**
   ```bash
   # Check port availability
   netstat -tulpn | grep :8001
   netstat -tulpn | grep :8003
   ```

### System Reset
```bash
# Stop all services
docker-compose down

# Complete reset (removes all data)
docker-compose down -v

# Rebuild and restart
docker-compose up --build -d
```

## 🔐 Security & Performance

### Security Features
- **Message Loop Prevention**: Topic bridge prevents circular message routing
- **Service Isolation**: Each service runs in isolated containers
- **Input Validation**: Comprehensive validation on all API endpoints
- **Health Monitoring**: Automatic service health checks

### Performance Optimizations
- **Redis Caching**: Fast data access and session management
- **Kafka Partitioning**: Parallel message processing
- **Consumer Groups**: Load balancing across consumers
- **Docker Optimization**: Efficient container resource usage

## 📈 Extension Points

### Adding New Services
1. Create service directory in `services/`
2. Add service definition to `docker-compose.yml`
3. Implement Kafka integration for message flow
4. Add monitoring endpoints

### Custom Document Processing
1. Extend OCR agent with new processing engines
2. Add custom verification rules to KYC agent
3. Implement new topic bridges for external systems
4. Add custom monitoring dashboards

## 🏆 Platform Benefits

✅ **Unified Architecture** - Single platform for all document processing needs
✅ **Scalable Design** - Easy to add new services and processing pipelines
✅ **Real-time Processing** - Kafka-based message streaming for immediate results
✅ **Cross-System Integration** - Seamless communication between different APIs
✅ **Comprehensive Monitoring** - Real-time visibility into all system operations
✅ **Production Ready** - Docker orchestration with health checks and recovery

---

**🎉 Document Processing & Ingestion Platform** - A complete solution for document processing, verification, and intelligent routing with real-time monitoring and cross-system integration.