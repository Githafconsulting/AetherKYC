# nodes/ack_control_center_node.py
from model.state import IngestionState
from shared.supabase_client import supabase
from shared.kafka_client import publish

TOPIC_PUBLISH = "kyc.document.ocr_request"

def ack_control_center(state: IngestionState) -> IngestionState:
    payload = state.kafka_message
    document_id = payload.get("document_id")
    user_id = payload.get("user_id")

    # ✅ log to supabase ingestion_logs
    log = {
        "document_id": document_id,
        "user_id": user_id,
        "status": "received"
    }
    supabase.table("ingestion_logs").insert(log).execute()
    print(f"✅ Logged ack for document {document_id}")

    # 📤 publish to OCR request topic
    publish(TOPIC_PUBLISH, key=document_id, value=payload)
    print(f"📤 Published OCR request for document {document_id}")

    # update state
    state.document_id = document_id
    state.user_id = user_id
    return state