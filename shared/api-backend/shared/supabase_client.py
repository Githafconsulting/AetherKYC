# shared/supabase_client.py
import os
import requests
from urllib.parse import quote_plus
import supabase

from dotenv import load_dotenv

load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET = os.getenv("SUPABASE_BUCKET", "documents")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

supabase = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

from supabase import create_client
import os



supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def storage_upload(file, dest_path: str):
    file_bytes = file.file.read()
    res = supabase.storage.from_(BUCKET).upload(dest_path, file_bytes)

    # UploadResponse contains `path` and `full_path`
    if not res.path:
        print("Supabase upload failed, raw response:", res)
        raise Exception(f"Storage upload failed: {res}")

    # Return the full path in the bucket for downstream usage
    return res.full_path  # or res.path if you prefer

def insert_customer(user_id, first_name, last_name, dob, document_no, address):
    supabase.table("customers").insert({
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "document_no": document_no,
        "address": address
    }).execute()

def insert_document(document_id, user_id, bucket_path, doc_type):
    supabase.table("documents").insert({
        "document_id": document_id,
        "user_id": user_id,
        "bucket_path": bucket_path,
        "doc_type": doc_type,
        "status": "pending"
    }).execute()