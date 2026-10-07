"""
app.py
FastAPI backend for the CBSE English Paper Evaluation System.
Data is persisted as JSON files under DATA_DIR (swap for PostgreSQL later).
"""
import os
import json
import uuid
import shutil
from datetime import datetime
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from ocr_processor import OCRProcessor
from ai_evaluator import AIEvaluator
from analytics import AnalyticsEngine

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "./data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
DB_FILE = os.path.join(DATA_DIR, "db.json")
ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".txt"}

for d in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR):
    os.makedirs(d, exist_ok=True)
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump({"question_papers": {}, "answer_keys": {}, "batches": {}}, f)

app = FastAPI(title="CBSE English Paper Evaluation System")

# CORS - allow local dev and production frontend
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
# Add production frontend URL from env if set
if os.getenv("FRONTEND_URL"):
    allowed_origins.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ocr = OCRProcessor(tesseract_cmd=os.getenv("TESSERACT_CMD"))
evaluator = AIEvaluator()


# ---------- DB helpers ----------
def read_db() -> dict:
    with open(DB_FILE, "r") as f:
        return json.load(f)


def write_db(db: dict):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


def validate_ext(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXT}")
    return ext


async def save_upload(file: UploadFile, subdir: str) -> str:
    ext = validate_ext(file.filename)
    folder = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"{uuid.uuid4().hex}{ext}")
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return dest


# ---------- Endpoints ----------
@app.post("/api/upload/question-paper")
async def upload_question_paper(
    file: UploadFile = File(...),
    total_marks: int = Form(...),
    subject: str = Form("English"),
    exam_date: str = Form(""),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext == ".txt":
        text = (await file.read()).decode("utf-8")
        path = ""
    else:
        path = await save_upload(file, "question_papers")
        text = ocr.extract_text(path)
    
    questions = evaluator.parse_questions(text)
    print("===== EXTRACTED TEXT =====")
    print(text[:500])
    print("===== PARSED QUESTIONS =====")
    print(list(questions.keys()))
    if not questions:
        raise HTTPException(422, "Could not parse any questions from the paper. Check formatting.")

    paper_id = uuid.uuid4().hex
    db = read_db()
    db["question_papers"][paper_id] = {
        "id": paper_id,
        "file_path": path,
        "total_marks": total_marks,
        "subject": subject,
        "exam_date": exam_date,
        "questions": questions,
        "raw_text": text,
        "created_at": datetime.utcnow().isoformat(),
    }
    write_db(db)
    return {"paper_id": paper_id, "questions_found": len(questions), "questions": questions}


@app.post("/api/upload/answer-key")
async def upload_answer_key(
    file: UploadFile = File(...),
    paper_id: str = Form(...),
):
    db = read_db()
    if paper_id not in db["question_papers"]:
        raise HTTPException(404, "Question paper not found")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext == ".txt":
        text = (await file.read()).decode("utf-8")
        path = ""
    else:
        path = await save_upload(file, "answer_keys")
        text = ocr.extract_text(path)
    key = evaluator.parse_answer_key(text)
    if not key:
        raise HTTPException(422, "Could not parse the answer key. Check formatting (e.g. 'Answer 1: ...').")

    key_id = uuid.uuid4().hex
    db["answer_keys"][key_id] = {
        "id": key_id,
        "paper_id": paper_id,
        "file_path": path,
        "key": key,
        "created_at": datetime.utcnow().isoformat(),
    }
    write_db(db)
    return {"key_id": key_id, "questions_keyed": len(key), "preview": key}


@app.post("/api/upload/answer-sheets")
async def upload_answer_sheets(
    files: List[UploadFile] = File(...),
    paper_id: str = Form(...),
    key_id: str = Form(...),
):
    db = read_db()
    if paper_id not in db["question_papers"]:
        raise HTTPException(404, "Question paper not found")
    if key_id not in db["answer_keys"]:
        raise HTTPException(404, "Answer key not found")

    batch_id = uuid.uuid4().hex
    sheets = []
    for f in files:
        try:
            path = await save_upload(f, f"answer_sheets/{batch_id}")
            sheets.append({"filename": f.filename, "file_path": path, "status": "uploaded"})
        except HTTPException as e:
            sheets.append({"filename": f.filename, "status": "error", "error": e.detail})

    db["batches"][batch_id] = {
        "id": batch_id,
        "paper_id": paper_id,
        "key_id": key_id,
        "sheets": sheets,
        "evaluated": False,
        "results": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    write_db(db)
    return {"batch_id": batch_id, "sheets_uploaded": len(sheets), "sheets": sheets}


@app.post("/api/evaluate/{paper_id}/{key_id}")
async def evaluate_batch(paper_id: str, key_id: str, batch_id: str = Form(...)):
    db = read_db()
    paper = db["question_papers"].get(paper_id)
    key = db["answer_keys"].get(key_id)
    batch = db["batches"].get(batch_id)
    if not (paper and key and batch):
        raise HTTPException(404, "Paper, key, or batch not found")

    questions = paper["questions"]
    answer_key = key["key"]

    results = []
    errors = []
    for sheet in batch["sheets"]:
        if sheet["status"] != "uploaded":
            continue
        try:
            file_path = sheet["file_path"]
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == ".txt":
                # Read text file directly
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                roll_number = ocr.extract_roll_number(text)
                student_answers = ocr.extract_answers(text)
            else:
                # Use OCR for PDF/images
                parsed = ocr.process_answer_sheet(file_path)
                roll_number = parsed["roll_number"]
                student_answers = parsed["answers"]
            
            print(f"===== STUDENT: {roll_number} =====")
            print(f"Answers found: {list(student_answers.keys())}")
            
            eval_result = evaluator.evaluate_student(student_answers, questions, answer_key)
            results.append({
                "roll_number": roll_number,
                "filename": sheet["filename"],
                **eval_result,
            })
        except Exception as e:
            errors.append({"filename": sheet["filename"], "error": str(e)})

    batch["evaluated"] = True
    batch["results"] = results
    batch["errors"] = errors
    write_db(db)
    return {"batch_id": batch_id, "evaluated_count": len(results), "errors": errors, "results": results}


@app.get("/api/results/{batch_id}")
async def get_results(batch_id: str):
    db = read_db()
    batch = db["batches"].get(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    if not batch["evaluated"]:
        raise HTTPException(400, "Batch has not been evaluated yet")
    return {"batch_id": batch_id, "results": batch["results"], "errors": batch.get("errors", [])}


@app.get("/api/dashboard/{batch_id}")
async def get_dashboard(batch_id: str):
    db = read_db()
    batch = db["batches"].get(batch_id)
    if not batch or not batch["evaluated"]:
        raise HTTPException(404, "Evaluated batch not found")
    engine = AnalyticsEngine(batch["results"])
    return engine.full_report()


@app.get("/api/export/{batch_id}")
async def export_results(batch_id: str):
    db = read_db()
    batch = db["batches"].get(batch_id)
    if not batch or not batch["evaluated"]:
        raise HTTPException(404, "Evaluated batch not found")
    engine = AnalyticsEngine(batch["results"])
    out_path = os.path.join(EXPORT_DIR, f"{batch_id}.xlsx")
    engine.export_excel(out_path)
    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"cbse_results_{batch_id[:8]}.xlsx",
    )

@app.post("/api/upload/question-paper-text")
async def upload_question_paper_text(
    file: UploadFile = File(...),
    total_marks: int = Form(...),
    subject: str = Form("English"),
    exam_date: str = Form(""),
):
    """Upload question paper as a .txt file (bypasses OCR)"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".txt":
        raise HTTPException(400, "This endpoint only accepts .txt files")
    
    text = (await file.read()).decode("utf-8")
    questions = evaluator.parse_questions(text)
    
    print("===== TEXT FROM FILE =====")
    print(text)
    print("===== PARSED QUESTIONS =====")
    print(questions)
    
    if not questions:
        raise HTTPException(422, "Could not parse any questions from the paper. Check formatting.")

    paper_id = uuid.uuid4().hex
    db = read_db()
    db["question_papers"][paper_id] = {
        "id": paper_id,
        "file_path": "",
        "total_marks": total_marks,
        "subject": subject,
        "exam_date": exam_date,
        "questions": questions,
        "raw_text": text,
        "created_at": datetime.utcnow().isoformat(),
    }
    write_db(db)
    return {"paper_id": paper_id, "questions_found": len(questions), "questions": questions}

@app.post("/api/upload/answer-key-text")
async def upload_answer_key_text(
    file: UploadFile = File(...),
    paper_id: str = Form(...),
):
    """Upload answer key as a .txt file (bypasses OCR)"""
    db = read_db()
    if paper_id not in db["question_papers"]:
        raise HTTPException(404, "Question paper not found")
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".txt":
        raise HTTPException(400, "This endpoint only accepts .txt files")
    
    text = (await file.read()).decode("utf-8")
    key = evaluator.parse_answer_key(text)
    
    print("===== ANSWER KEY TEXT =====")
    print(text)
    print("===== PARSED KEY =====")
    print(key)
    
    if not key:
        raise HTTPException(422, "Could not parse the answer key. Check formatting (e.g. 'Answer 1: ...').")

    key_id = uuid.uuid4().hex
    db["answer_keys"][key_id] = {
        "id": key_id,
        "paper_id": paper_id,
        "file_path": "",
        "key": key,
        "created_at": datetime.utcnow().isoformat(),
    }
    write_db(db)
    return {"key_id": key_id, "questions_keyed": len(key)}


@app.post("/api/upload/answer-sheet-text")
async def upload_answer_sheet_text(
    file: UploadFile = File(...),
    paper_id: str = Form(...),
    key_id: str = Form(...),
):
    """Upload a single answer sheet as a .txt file (bypasses OCR)"""
    db = read_db()
    if paper_id not in db["question_papers"]:
        raise HTTPException(404, "Question paper not found")
    if key_id not in db["answer_keys"]:
        raise HTTPException(404, "Answer key not found")
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".txt":
        raise HTTPException(400, "This endpoint only accepts .txt files")
    
    text = (await file.read()).decode("utf-8")
    
    batch_id = uuid.uuid4().hex
    path = os.path.join(UPLOAD_DIR, "answer_sheets", batch_id, file.filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    
    sheet = {"filename": file.filename, "file_path": path, "status": "uploaded"}
    
    db["batches"][batch_id] = {
        "id": batch_id,
        "paper_id": paper_id,
        "key_id": key_id,
        "sheets": [sheet],
        "evaluated": False,
        "results": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    write_db(db)
    return {"batch_id": batch_id, "sheets_uploaded": 1}

@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
