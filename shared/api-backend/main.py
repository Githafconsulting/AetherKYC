from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse
from shared.supabase_client import insert_customer, insert_document, storage_upload
from shared.kafka_client import publish   # 👈 add this
import uuid

app = FastAPI()

@app.get("/form", response_class=HTMLResponse)
async def get_form():
    return """
    <html>
        <body>
            <h2>KYC Upload Form</h2>
            <form action="/upload" enctype="multipart/form-data" method="post">
                First Name: <input type="text" name="first_name"><br>
                Last Name: <input type="text" name="last_name"><br>
                Document Type: <input type="text" name="doc_type"><br>
                Date of Birth: <input type="date" name="dob"><br>
                Document No: <input type="text" name="document_no"><br>
                Address: <input type="text" name="address"><br>
                File: <input type="file" name="file"><br><br>
                <input type="submit" value="Submit">
            </form>
        </body>
    </html>
    """

@app.post("/upload")
async def upload_document(
    first_name: str = Form(...),
    last_name: str = Form(...),
    doc_type: str = Form(...),
    dob: str = Form(...),
    document_no: str = Form(...),
    address: str = Form(...),
    file: UploadFile = None
):
    # 1️⃣ Generate unique IDs
    user_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())

    # 2️⃣ Destination path in storage
    dest_path = f"{user_id}/{document_id}_{file.filename}"

    # 3️⃣ Upload file to Supabase Storage
    file_path = storage_upload(file, dest_path)

    # 4️⃣ Insert customer info
    insert_customer(user_id, first_name, last_name, dob, document_no, address)

    # 5️⃣ Insert document metadata
    insert_document(document_id, user_id, file_path, doc_type)

    # 6️⃣ Publish Kafka event (📣 notify downstream systems)
    event = {
        "user_id": user_id,
        "document_id": document_id,
        "file_path": file_path,
        "doc_type": doc_type,
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "document_no": document_no,
        "address": address,
        "status": "uploaded"
    }
    publish("kyc.document.uploaded", key=document_id, value=event)

    # 7️⃣ Respond back to client
    return event