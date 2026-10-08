"""
ocr_processor.py
OCR extraction for CBSE answer sheets / question papers using Tesseract + OpenCV + EasyOCR.
Supports PDF and image (JPG/PNG) input.
"""
import os
import re
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from typing import List, Dict
import easyocr

# Try to import easyocr, but don't fail if not available
try:
    import easyocr
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

_easyocr_reader = None

def get_easyocr():
    global _easyocr_reader
    if not _EASYOCR_AVAILABLE:
        return None
    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
    return _easyocr_reader

class OCRProcessor:
    def __init__(self, tesseract_cmd: str = None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # ---------- Image loading ----------
    def _load_pages_as_images(self, file_path: str) -> List[np.ndarray]:
        ext = os.path.splitext(file_path)[1].lower()
        images = []
        if ext == ".pdf":
            pil_pages = convert_from_path(file_path, dpi=300)
            for pil_img in pil_pages:
                images.append(cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR))
        elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff"):
            img = cv2.imread(file_path)
            if img is None:
                raise ValueError(f"Could not read image file: {file_path}")
            images.append(img)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        return images

    # ---------- Preprocessing ----------
    def preprocess_image(self, img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 15
        )
        deskewed = self._deskew(thresh)
        return deskewed

    def _deskew(self, img: np.ndarray) -> np.ndarray:
        coords = np.column_stack(np.where(img < 255))
        if coords.shape[0] < 50:
            return img
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:
            return img
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)

    # ---------- Public API ----------
    def extract_text(self, file_path: str) -> str:
        """Extract text using EasyOCR if available, otherwise Tesseract"""
        ext = os.path.splitext(file_path)[1].lower()
        
        # Try EasyOCR only if available (local dev)
        if _EASYOCR_AVAILABLE:
            try:
                reader = get_easyocr()
                if reader and ext == ".pdf":
                    pages = self._load_pages_as_images(file_path)
                    full_text = []
                    for page in pages:
                        results = reader.readtext(page, detail=0)
                        full_text.append(" ".join(results))
                    return "\n".join(full_text)
                elif reader:
                    results = reader.readtext(file_path, detail=0)
                    return " ".join(results)
            except Exception as e:
                print(f"EasyOCR failed: {e}, falling back to Tesseract")
        
        # Fallback to Tesseract (production default)
        if ext == ".pdf":
            pages = self._load_pages_as_images(file_path)
            full_text = []
            for page in pages:
                processed = self.preprocess_image(page)
                text = pytesseract.image_to_string(processed, config="--oem 3 --psm 6")
                full_text.append(text)
            return "\n".join(full_text)
        else:
            img = cv2.imread(file_path)
            processed = self.preprocess_image(img)
            return pytesseract.image_to_string(processed, config="--oem 3 --psm 6")

    def extract_roll_number(self, text: str) -> str:
        # Try to find CBSE-like patterns in messy OCR text
        patterns = [
            r'[A-Z]{2,6}\s*\d{4,8}',  # CBSE2024006
            r'[A-Z]{2,6}[\s_]*[A-Za-z0-9]{4,10}',  # CBSC_Roxuoo style
            r'\b\d{8,12}\b',  # Just digits
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                # Clean up the match
                raw = match.group(0)
                cleaned = re.sub(r'[_\s]', '', raw)  # Remove underscores and spaces
                if len(cleaned) >= 6:
                    return cleaned[:15]
        return "UNKNOWN"

    def extract_answers(self, text: str) -> Dict[str, str]:
        """
        Parse answers from text, capturing multi-line answers.
        Reads until the next Q label (Q1, Q2, Q1(a), Q5(b), etc.)
        """
        answers: Dict[str, str] = {}
        
        # Match Q1:, Q1(a):, Q5(b): etc. and capture everything until next Q label
        pattern = re.compile(
            r"(?:^|(?<=\s))Q(?:uestion)?\.?\s*(\d{1,2})(?:\s*\(([a-z])\)\s*[\.\):]?|\s*[\.\):])\s*(.*?)(?=(?:^|\s)Q(?:uestion)?\.?\s*\d|\Z)",
            re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        
        for m in pattern.finditer(text):
            qnum = m.group(1)
            sub = m.group(2)
            qid = f"{qnum}{sub}" if sub else qnum
            answer_text = m.group(3).strip()
            
            # Remove excessive whitespace but keep multi-line structure
            answer_text = re.sub(r'\n\s*\n', '\n', answer_text)
            
            if answer_text:
                answers[qid] = answer_text
        
        # Fallback: try Answer 1: or Ans 1: format
        if not answers:
            ans_pattern = re.compile(
                r"^Ans(?:wer)?\.?\s*(\d{1,2})(?:\s*\(([a-z])\))?\s*[\.\):]\s*(.*?)(?=^Ans(?:wer)?\.?\s*\d|\Z)",
                re.IGNORECASE | re.MULTILINE | re.DOTALL
            )
            for m in ans_pattern.finditer(text):
                qnum = m.group(1)
                sub = m.group(2)
                qid = f"{qnum}{sub}" if sub else qnum
                answer_text = m.group(3).strip()
                if answer_text:
                    answers[qid] = answer_text
        
        return answers

    def process_answer_sheet(self, file_path: str) -> Dict:
        text = self.extract_text(file_path)
        print("===== EASYOCR RAW TEXT =====")
        print(text)
        print("===== END RAW TEXT =====")
    
        # For handwritten text, try to extract roll number with fuzzy matching
        roll_number = self.extract_roll_number(text)
        if roll_number == "UNKNOWN":
            # Try to find anything that looks like CBSE followed by digits
            fuzzy_roll = re.search(r'[A-Z]{2,6}\s*\d{4,8}', text, re.IGNORECASE)
            if fuzzy_roll:
                roll_number = fuzzy_roll.group(0).replace(" ", "")
       
        # For handwritten answers, just return the full text
        # The AI evaluator will handle matching via semantic similarity
        answers = self.extract_answers(text)
    
        # If regex failed to find answers, create a single chunk with the full text
        if not answers:
            answers = {"full_text": text}
    
        return {
            "raw_text": text,
            "roll_number": roll_number,
            "answers": answers,
        }