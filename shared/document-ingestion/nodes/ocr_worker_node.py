import json
import tempfile
import base64
import sys
import os
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from PIL import Image

# Adjust sys.path to import Backend shared clients
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Backend")))
from kafka_client import get_consumer, publish
from supabase_client import supabase

GROUP_ID = "ocr_worker_group"
CONSUME_TOPIC = ["kyc.document.ocr_request"]
OCR_TOPIC = "kyc.document.ocr_processed"

# Initialize Moondream via Ollama
llm = OllamaLLM(model="moondream")

# OCR prompt
ocr_prompt = PromptTemplate(
    input_variables=["image"],
    template="""
You are an OCR system. Extract ALL text from this document image.
Return ONLY the extracted text, nothing else.

Extracted text:
"""
)

# Validation prompt
validation_prompt = PromptTemplate(
    input_variables=["extracted_text", "expected_fields"],
    template="""
Given this extracted text from a KYC document:
{extracted_text}

Expected information:
{expected_fields}

Analyze the text and return a JSON object with validation results:
{{
    "first_name_found": true/false,
    "last_name_found": true/false, 
    "dob_found": true/false,
    "address_found": true/false,
    "extracted_first_name": "found name or null",
    "extracted_last_name": "found name or null",
    "extracted_dob": "found date or null",
    "extracted_address": "found address or null",
    "confidence_score": 0.0-1.0,
    "validation_notes": "any issues or observations"
}}

Return ONLY the JSON object, no other text.
"""
)

def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def extract_text_with_moondream(image_path):
    try:
        image_b64 = image_to_base64(image_path)
        prompt = ocr_prompt.format(image=f"data:image/jpeg;base64,{image_b64}")
        return llm.invoke(prompt).strip()
    except Exception as e:
        print(f"❌ Moondream OCR failed: {e}")
        return ""

def validate_with_llm(extracted_text, expected_fields):
    try:
        expected_str = json.dumps(expected_fields, indent=2)
        prompt = validation_prompt.format(
            extracted_text=extracted_text,
            expected_fields=expected_str
        )
        response = llm.invoke(prompt)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "first_name_found": False,
                "last_name_found": False,
                "dob_found": False,
                "address_found": False,
                "confidence_score": 0.0,
                "validation_notes": "❌ Failed to parse validation response"
            }
    except Exception as e:
        return {
            "first_name_found": False,
            "last_name_found": False,
            "dob_found": False,
            "address_found": False,
            "confidence_score": 0.0,
            "validation_notes": f"❌ Validation error: {e}"
        }

def extract_and_validate(payload: dict):
    document_id = payload.get("document_id")
    bucket_path = payload.get("file_path")

    expected_fields = {
        "first_name": payload.get("first_name", "").lower(),
        "last_name": payload.get("last_name", "").lower(),
        "dob": payload.get("dob", ""),
        "address": payload.get("address", "").lower(),
    }

    # Clean path
    if bucket_path.startswith("documents/"):
        bucket_path = bucket_path[len("documents/"):]

    # 1️⃣ Download
    try:
        print(f"📂 Downloading {bucket_path}")
        file_bytes = supabase.storage.from_("documents").download(bucket_path)
    except Exception as e:
        error_result = {"document_id": document_id, "status": "error", "error": str(e)}
        publish(OCR_TOPIC, key=document_id, value=error_result)
        return

    # 2️⃣ OCR
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name

    extracted_text = extract_text_with_moondream(tmp_path)
    os.unlink(tmp_path)

    if not extracted_text:
        error_result = {"document_id": document_id, "status": "error", "error": "No text extracted"}
        publish(OCR_TOPIC, key=document_id, value=error_result)
        return

    print(f"📝 Extracted text: {extracted_text[:200]}...")

    # 3️⃣ Validation
    validation_results = validate_with_llm(extracted_text, expected_fields)

    # 4️⃣ Publish results ✅ (fixed publish call)
    result = {
        "document_id": document_id,
        "status": "completed",
        "extracted_text": extracted_text,
        "expected_fields": expected_fields,
        "validation_results": validation_results,
    }

    print(f"✅ OCR completed for document {document_id}")
    print(f"🎯 Validation results: {validation_results}")

    publish(OCR_TOPIC, key=document_id, value=result)

def main():
    print("🚀 Starting Moondream OCR Worker...")
    consumer = get_consumer(GROUP_ID, CONSUME_TOPIC)

    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"❌ Kafka error: {msg.error()}")
            continue

        try:
            payload = json.loads(msg.value().decode("utf-8"))
            print(f"📨 Received OCR request for {payload.get('document_id')}")
            extract_and_validate(payload)
        except Exception as e:
            print(f"❌ Processing error: {e}")

if __name__ == "__main__":
    main()