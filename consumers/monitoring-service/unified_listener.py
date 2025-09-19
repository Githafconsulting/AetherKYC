"""
Unified KYC Listener
Listens to topics from both systems and provides unified monitoring
"""

from confluent_kafka import Consumer
import json
import os
from datetime import datetime
from typing import Dict, Any
import colorama
from colorama import Fore, Style

# Initialize colorama for colored output
colorama.init(autoreset=True)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:29092")

# All topics from both systems
TOPICS = [
    # Your system topics
    "ocr-completed",
    "kyc-submissions",
    "kyc-verification",
    "kyc-alerts",

    # Teammate's system topics
    "forms_submitted",
    "forms-verified"
]

GROUP_ID = os.getenv("CONSUMER_GROUP_ID", "unified-kyc-listener-group")

consumer_conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "group.id": GROUP_ID,
    "auto.offset.reset": "earliest"
}

def log_message(topic: str, key: str, value: Dict[str, Any]):
    """Enhanced logging with colors and structured formatting for both systems"""
    timestamp = datetime.now().strftime("%H:%M:%S")

    # Color mapping for different topics
    topic_colors = {
        # Your system
        "ocr-completed": Fore.CYAN,
        "kyc-submissions": Fore.GREEN,
        "kyc-verification": Fore.YELLOW,
        "kyc-alerts": Fore.RED,

        # Teammate's system
        "forms_submitted": Fore.MAGENTA,
        "forms-verified": Fore.BLUE
    }

    color = topic_colors.get(topic, Fore.WHITE)

    # Determine system source
    system = "AGENTS-PLATFORM" if topic in ["ocr-completed", "kyc-submissions", "kyc-verification", "kyc-alerts"] else "TEAMMATE-SYSTEM"

    print(f"\n{color}{'='*60}")
    print(f"{color}[{timestamp}] {topic.upper()} ({system})")
    print(f"{color}{'='*60}")
    print(f"{Fore.WHITE}Customer ID: {key}")

    # Check if message was bridged
    if "_bridged_from" in value:
        print(f"{Fore.CYAN}📨 Bridged from: {value['_bridged_from']}")
        print(f"{Fore.CYAN}📬 Bridged to: {value['_bridged_to']}")

    # Handle different message types based on topic
    if topic == "ocr-completed":
        print(f"{Fore.WHITE}Document Type: {value.get('document_type', 'unknown')}")
        print(f"{Fore.WHITE}Confidence: {value.get('confidence', 0):.1f}%")
        print(f"{Fore.WHITE}Text Length: {len(value.get('extracted_text', ''))}")
        print(f"{Fore.WHITE}Storage URL: {value.get('storage_url', 'N/A')}")
        print(f"{Fore.WHITE}Status: {value.get('status', 'unknown')}")

    elif topic in ["kyc-submissions", "kyc-verification", "forms_submitted", "forms-verified"]:
        print(f"{Fore.WHITE}Document Type: {value.get('document_type', 'unknown')}")
        print(f"{Fore.WHITE}Document Number: {value.get('document_number', 'N/A')}")
        print(f"{Fore.WHITE}Country: {value.get('country', 'N/A')}")
        print(f"{Fore.WHITE}Request ID: {value.get('request_id', 'N/A')}")
        print(f"{Fore.WHITE}Status: {value.get('status', 'unknown')}")

        if "extracted_text" in value:
            text_preview = value["extracted_text"][:100] + "..." if len(value["extracted_text"]) > 100 else value["extracted_text"]
            print(f"{Fore.WHITE}Text Preview: {text_preview}")

    elif topic == "kyc-alerts":
        print(f"{Fore.WHITE}Alert Reason: {value.get('alert_reason', 'No reason provided')}")
        print(f"{Fore.WHITE}Document Type: {value.get('document_type', 'unknown')}")
        print(f"{Fore.WHITE}Status: {value.get('status', 'unknown')}")

    print(f"{Fore.WHITE}Timestamp: {value.get('timestamp', 'N/A')}")
    print(f"{color}{'='*60}{Style.RESET_ALL}")

def process_message(topic: str, key: str, value: Dict[str, Any]):
    """Process messages and show system interactions"""

    # Track cross-system interactions
    if "_bridged_from" in value:
        source_system = "AGENTS-PLATFORM" if value["_bridged_from"] in ["kyc-submissions", "kyc-verification"] else "TEAMMATE-SYSTEM"
        target_system = "TEAMMATE-SYSTEM" if source_system == "AGENTS-PLATFORM" else "AGENTS-PLATFORM"
        print(f"{Fore.CYAN}🔄 Cross-System Communication: {source_system} → {target_system}{Style.RESET_ALL}")

    # Process based on topic
    if topic == "ocr-completed":
        document_type = value.get('document_type', 'unknown')
        confidence = value.get('confidence', 0)

        if document_type in ["passport", "id_card", "driver_license"] and confidence >= 80:
            print(f"{Fore.GREEN}✓ High-confidence identity document - will be routed to both systems{Style.RESET_ALL}")
        elif confidence < 70:
            print(f"{Fore.YELLOW}⚠ Low confidence document - may need manual review{Style.RESET_ALL}")

    elif topic in ["kyc-submissions", "forms_submitted"]:
        print(f"{Fore.GREEN}→ Document ready for KYC verification in both systems{Style.RESET_ALL}")

    elif topic in ["kyc-verification", "forms-verified"]:
        print(f"{Fore.BLUE}⚡ Verification completed - results available in both systems{Style.RESET_ALL}")

    elif topic == "kyc-alerts":
        alert_reason = value.get('alert_reason', 'Unknown alert')
        print(f"{Fore.RED}🚨 ALERT: {alert_reason} - notification sent to both systems{Style.RESET_ALL}")

# Create consumer
consumer = Consumer(consumer_conf)
consumer.subscribe(TOPICS)

print(f"{Fore.MAGENTA}{'='*70}")
print(f"{Fore.MAGENTA}🎧 UNIFIED KYC LISTENER - BRIDGING BOTH SYSTEMS")
print(f"{Fore.MAGENTA}{'='*70}{Style.RESET_ALL}")
print(f"{Fore.WHITE}Monitoring topics from both systems:")
print(f"{Fore.GREEN}  Your System: ocr-completed, kyc-submissions, kyc-verification, kyc-alerts")
print(f"{Fore.BLUE}  Teammate's System: forms_submitted, forms-verified")
print(f"{Fore.WHITE}Broker: {KAFKA_BROKER}")
print(f"{Fore.WHITE}Group ID: {GROUP_ID}")
print(f"{Fore.MAGENTA}{'='*70}{Style.RESET_ALL}\n")

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"{Fore.RED}Consumer error: {msg.error()}{Style.RESET_ALL}")
            continue

        key = msg.key().decode("utf-8") if msg.key() else "no-key"
        value = json.loads(msg.value().decode("utf-8"))

        # Log and process the message
        log_message(msg.topic(), key, value)
        process_message(msg.topic(), key, value)

except KeyboardInterrupt:
    print(f"\n{Fore.YELLOW}Shutting down unified listener...{Style.RESET_ALL}")

finally:
    consumer.close()
    print(f"{Fore.GREEN}Consumer closed successfully{Style.RESET_ALL}")