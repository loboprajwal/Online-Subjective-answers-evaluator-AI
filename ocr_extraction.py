import os
import cv2
import numpy as np
import json
import re
import argparse
import easyocr
from pdf2image import convert_from_path
from PIL import Image

# --- SETTINGS & PATHS ---
DEFAULT_PDF_FOLDER = "data/pdf"
DEFAULT_JSON_OUTPUT = "data/json"

def clean_image(image_pil):
    """ Cleans image to make handwriting easier to read """
    img = np.array(image_pil)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # Increase contrast and sharpen
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    img = cv2.filter2D(img, -1, kernel)
    
    # Adaptive thresholding to remove shadows from scans
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 11, 2)
    return img

def extract_text_from_pdf(pdf_path):
    """ Converts PDF to images and extracts text using EasyOCR """
    print(f"📄 Processing: {os.path.basename(pdf_path)}...")
    
    # Initialize EasyOCR (CPU is safer for default compatibility)
    reader = easyocr.Reader(['en'], gpu=False)
    
    try:
        pages = convert_from_path(pdf_path, 300)
    except Exception as e:
        print(f" ❌ Could not read PDF: {e}")
        return None

    full_text = ""
    for i, page_img in enumerate(pages):
        print(f"  -> Reading Page {i+1}...")
        processed = clean_image(page_img)
        # detail=0 gives just text; paragraph=True handles blocks of handwriting
        text_blocks = reader.readtext(processed, detail=0, paragraph=True)
        full_text += f"\n {' '.join(text_blocks)}"
        
    return full_text

def parse_extracted_text(raw_text):
    """ Splits raw text into question-answer format """
    # Robust splitting by patterns like "Q1", "Q 1", "Question 1", "1.", or "1)"
    # Added \s* after Q, allowed ) as a delimiter, and made sure it's at start of a word
    segments = re.split(r'(\bQ\s*\d+\b|\bQuestion\s*\d+\b|\b\d+[.)])', raw_text, flags=re.IGNORECASE)
    
    parsed_data = []
    
    # Fallback: if no markers were found, treat the entire block as one answer
    if len(segments) == 1:
        text = segments[0].strip()
        if text:
            parsed_data.append({
                "Question Number": 1,
                "Answer": text
            })
        return parsed_data

    for i in range(1, len(segments), 2):
        q_label = segments[i].strip()
        q_num_match = re.search(r'\d+', q_label)
        if not q_num_match: continue
        
        q_num = int(q_num_match.group())
        ans_text = segments[i+1].strip() if i+1 < len(segments) else ""
        
        parsed_data.append({
            "Question Number": q_num,
            "Answer": ans_text
        })
    return parsed_data

def process_single_pdf(pdf_path):
    """ Processes one PDF and returns the structured answer list """
    raw_text = extract_text_from_pdf(pdf_path)
    if raw_text:
        return parse_extracted_text(raw_text)
    return []

def save_model_answer(pdf_path, output_json_path):
    """ Special handler for the model answer sheet """
    answers = process_single_pdf(pdf_path)
    if answers:
        # semantic_scoring.py expects lowercase keys for the model answer
        formatted_answers = [
            {"question_number": a["Question Number"], "answer": a["Answer"]}
            for a in answers
        ]
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(formatted_answers, f, indent=4)
        print(f"✅ Model answer saved to {output_json_path}")
        return True
    return False

def process_batch(pdf_folder, output_json_folder):
    """ Runs the pipeline on all PDFs in the folder """
    os.makedirs(output_json_folder, exist_ok=True)
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith(".pdf")]
    
    if not pdf_files:
        print(f"⚠️ No PDFs found in {pdf_folder}.")
        return

    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_folder, pdf_file)
        raw_text = extract_text_from_pdf(pdf_path)
        
        if raw_text:
            student_id = os.path.splitext(pdf_file)[0]
            parsed_answers = parse_extracted_text(raw_text)
            
            output_data = {
                "student_id": student_id,
                "answers": parsed_answers
            }
            
            output_path = os.path.join(output_json_folder, f"{student_id}.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4)
            print(f" ✅ Saved structured JSON to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="OCR Extraction Pipeline using EasyOCR")
    parser.add_argument("--pdf_dir", default=DEFAULT_PDF_FOLDER, help="Directory containing PDFs")
    parser.add_argument("--json_dir", default=DEFAULT_JSON_OUTPUT, help="Directory for final JSONs")
    args = parser.parse_args()

    process_batch(args.pdf_dir, args.json_dir)
    print("\n✨ OCR Extraction Completed.")

if __name__ == "__main__":
    main()