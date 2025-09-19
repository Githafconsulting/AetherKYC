from confluent_kafka import Consumer
import json
import os
from datetime import datetime
from typing import Dict, Any
import colorama
from colorama import Fore, Style

# Initialize colorama for colored output
colorama.init(autoreset=True)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPICS = ["ocr-completed", "kyc-submissions", "kyc-verification", "kyc-alerts"]
GROUP_ID = "integrated-kyc-listener"

consumer_conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "group.id": GROUP_ID,
    "auto.offset.reset": "earliest"
}

def log_message(topic: str, key: str, value: Dict[str, Any]):
    """Enhanced logging with colors and structured formatting"""
    timestamp = datetime.now().strftime("%H:%M:%S")

    # Color mapping for different topics
    topic_colors = {
        "ocr-completed": Fore.CYAN,
        "kyc-submissions": Fore.GREEN,
        "kyc-verification": Fore.YELLOW,
        "kyc-alerts": Fore.RED
    }

    color = topic_colors.get(topic, Fore.WHITE)

    print(f"\n{color}{'='*60}")
    print(f"{color}[{timestamp}] {topic.upper()}")
    print(f"{color}{'='*60}")
    print(f"{Fore.WHITE}Customer ID: {key}")

    # Handle different message types
    if topic == "ocr-completed":
        print(f"{Fore.WHITE}Document Type: {value.get('document_type', 'unknown')}")
        print(f"{Fore.WHITE}Confidence: {value.get('confidence', 0):.1f}%")
        print(f"{Fore.WHITE}Text Length: {len(value.get('extracted_text', ''))}")
        print(f"{Fore.WHITE}Storage URL: {value.get('storage_url', 'N/A')}")
        print(f"{Fore.WHITE}Status: {value.get('status', 'unknown')}")

    elif topic in ["kyc-submissions", "kyc-verification"]:
        print(f"{Fore.WHITE}Document Type: {value.get('document_type', 'unknown')}")
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

def process_ocr_result(key: str, value: Dict[str, Any]):
    """Process OCR completion results - could trigger additional workflows"""
    document_type = value.get('document_type', 'unknown')
    confidence = value.get('confidence', 0)

    # Example: Could trigger additional processing based on document type
    if document_type in ["passport", "id_card", "driver_license"] and confidence >= 80:
        print(f"{Fore.GREEN}✓ High-confidence identity document detected - ready for KYC verification{Style.RESET_ALL}")
    elif confidence < 70:
        print(f"{Fore.YELLOW}⚠ Low confidence document - may need manual review{Style.RESET_ALL}")
    else:
        print(f"{Fore.BLUE}ℹ Document processed - type: {document_type}{Style.RESET_ALL}")

def process_kyc_submission(key: str, value: Dict[str, Any]):
    """Process KYC submission - could trigger verification workflow"""
    print(f"{Fore.GREEN}→ KYC verification ready to start for customer {key}{Style.RESET_ALL}")

def process_kyc_verification(key: str, value: Dict[str, Any]):
    """Process active KYC verification"""
    print(f"{Fore.YELLOW}⚡ KYC verification in progress for customer {key}{Style.RESET_ALL}")

def process_kyc_alert(key: str, value: Dict[str, Any]):
    """Process KYC alerts - could trigger manual review"""
    alert_reason = value.get('alert_reason', 'Unknown alert')
    print(f"{Fore.RED}🚨 ALERT: {alert_reason} for customer {key}{Style.RESET_ALL}")

consumer = Consumer(consumer_conf)
consumer.subscribe(TOPICS)

print(f"{Fore.MAGENTA}🎧 Integrated KYC Listener Started")
print(f"{Fore.WHITE}Listening to Kafka topics: {TOPICS}")
print(f"{Fore.WHITE}Broker: {KAFKA_BROKER}")
print(f"{Fore.WHITE}Group ID: {GROUP_ID}")
print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}\n")

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

        # Log the message with enhanced formatting
        log_message(msg.topic(), key, value)

        # Process based on topic
        if msg.topic() == "ocr-completed":
            process_ocr_result(key, value)
        elif msg.topic() == "kyc-submissions":
            process_kyc_submission(key, value)
        elif msg.topic() == "kyc-verification":
            process_kyc_verification(key, value)
        elif msg.topic() == "kyc-alerts":
            process_kyc_alert(key, value)

except KeyboardInterrupt:
    print(f"\n{Fore.YELLOW}Shutting down listener...{Style.RESET_ALL}")

finally:
    consumer.close()
    print(f"{Fore.GREEN}Consumer closed successfully{Style.RESET_ALL}")