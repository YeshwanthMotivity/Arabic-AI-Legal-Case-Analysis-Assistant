# Arabic AI Legal Case Analysis Assistant

##  Overview
This project is an AI-powered legal assistant specialized in analyzing Arabic legal cases (Saudi Law). It provides:
- **Case Analysis**: Classification, Legal Principles, Trends, and Recommendations.
- **Interactive Query Panel**: Ask specific questions (Outcome, Compensation, etc.) deterministically.
- **Draft Generation**: Auto-generate Plaintiff Claims (`لائحة دعوى`) or Defendant Memos (`مذكرة دفاع`).
- **Document Upload**: Support for PDF, DOCX, and TXT files.

##  Prerequisites
- Python 3.10+
- Node.js & npm
- Tesseract OCR (Optional, for scanned PDFs)

##  Installation

### 1. Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
```

## ‍️ How to Run

### Step 1: Start Backend (Port 5000)
```bash
cd backend
python main.py
```
*Wait for "Application startup complete" message.*

### Step 2: Start Frontend
```bash
cd frontend
npm start
```
*The application will open at `http://localhost:3000`.*

##  Verification
To verify the system is working correctly, run the workflow test:
```bash
cd backend
python test_workflow.py
```

##  Project Structure
- `backend/main.py`: Main API server (FastAPI)
- `backend/engines/`: AI Logic Modules (Classification, Similarity, Draft, Query, etc.)
- `frontend/src/App.js`: Main React Interface
- `artifacts/`: Project documentation and logs
