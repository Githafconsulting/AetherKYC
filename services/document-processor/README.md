# OCR Agent

Simple document OCR processing with Supabase storage and colored terminal logging.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure .env with your Supabase credentials:**
   ```bash
   SUPABASE_URL=https://your-project-ref.supabase.co
   SUPABASE_SERVICE_KEY=your-service-role-key-here
   ```

3. **Start the server:**
   ```bash
   python run.py
   ```

4. **Test at:**
   - API: `http://localhost:8001/ocr/process`
   - Docs: `http://localhost:8001/docs`

## Features

- ✅ Document type detection (passport, bank statement, ID photo)
- ✅ Colored terminal logging with process tracking
- ✅ Supabase storage integration
- ✅ PDF and image support (PNG, JPG, JPEG)
- ✅ Fallback mode when EasyOCR unavailable

## File Structure

```
├── app/
│   ├── main.py          # FastAPI app & server startup
│   ├── models.py        # Data models
│   ├── routes.py        # API endpoints with logging
│   └── services/
│       └── ocr_service.py  # OCR processing engine
├── requirements.txt     # Dependencies
├── .env                 # Your config (Supabase credentials)
└── README.md           # This file
```

That's it! 🚀