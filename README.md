# CBSE English Paper Evaluation System

AI-powered evaluation of CBSE Class 12 English answer sheets: OCR extraction +
semantic-similarity grading against a rubric (Content 40%, Organization 30%,
Language 20%, Grammar 10%), with an analytics dashboard.

## Structure
```
backend/    FastAPI app, OCR, AI evaluator, analytics, JSON storage (./data)
frontend/   React + MUI + Recharts UI
```

## Backend Setup
```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# System dependencies (Ubuntu/Debian):
sudo apt-get install tesseract-ocr poppler-utils

uvicorn app:app --reload --port 8000
```
On first run, `sentence-transformers` downloads the `all-MiniLM-L6-v2` model
(~90MB). `language_tool_python` is optional; if it fails to start (needs Java),
the evaluator falls back to a neutral grammar score automatically.

## Frontend Setup
```bash
cd frontend
npm install
echo "REACT_APP_API_URL=http://localhost:8000" > .env
npm start
```
App runs at http://localhost:3000, backend at http://localhost:8000.

## Workflow
1. **Question Paper** — upload PDF/image with marks in `[N marks]` format per question.
2. **Answer Key** — upload with `Answer 1: ...` blocks for each question.
3. **Answer Sheets** — bulk upload 40-50 scanned sheets; each must have a
   `Roll No: XXXXXXXX` line and `Q1.`/`Q2.` markers per answer.
4. **Run Evaluation** — OCR + AI scoring runs across the batch.
5. **Results / Analytics** — sortable results table, Excel export, and dashboard.

## Notes
- Data persists as JSON in `backend/data/db.json` (uploads/exports alongside it).
  Swap `read_db`/`write_db` in `app.py` for a real DB (e.g. PostgreSQL) later.
- Passing criteria: 33% (CBSE standard), configurable via `PASS_PERCENTAGE` in `analytics.py`.
- Section-wise mapping (`SECTION_MAP` in `analytics.py`) should be edited to match your
  actual question paper's Reading/Writing/Grammar/Literature layout.
