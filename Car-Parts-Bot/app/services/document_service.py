
import os
import requests
import pdfplumber
import pandas as pd
import re
import io
import pypdfium2 as pdfium
from flask import current_app
from .message_processor import handle_vin_input, handle_part_number_search, normalize_part_number
from ..services.extract_vin_service import extract_vin_from_text
from ..services.media_service import process_image_media
from ..services.image_intent_executor import run_image_intent
from ..services.image_intent_router import detect_image_intent
from ..session_store import get_session

def download_document(media_id: str, original_filename: str) -> str:
    """
    Download WhatsApp document to a temporary file.
    Returns the absolute path to the saved file.
    """
    token = current_app.config["META_ACCESS_TOKEN"]
    # 1. Get URL from Media ID
    url_req = requests.get(
        f"https://graph.facebook.com/v20.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    url_req.raise_for_status()
    media_url = url_req.json().get("url")

    # 2. Download Content
    resp = requests.get(
        media_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    resp.raise_for_status()

    # 3. Save to /tmp or configured upload dir
    # Use original filename extension or default
    ext = os.path.splitext(original_filename)[1] or ".bin"
    file_path = f"/tmp/{media_id}{ext}"
    
    with open(file_path, "wb") as f:
        f.write(resp.content)
    
    return file_path


def process_document_media(user_id: str, media_id: str, filename: str) -> str:
    """
    Main entry point for document processing task.
    Determines file type (PDF vs Excel) and routes accordingly.
    """
    try:
        file_path = download_document(media_id, filename)
        ext = os.path.splitext(filename)[1].lower()

        print(f"📄 Processing document: {filename} ({ext})")

        if ext == ".pdf":
            return process_pdf(user_id, file_path, filename)
        elif ext in [".xlsx", ".xls", ".csv"]:
            return process_excel_or_csv(user_id, file_path, ext)
        else:
            return "I received your file, but I can only process PDF or Excel documents for now."

    except Exception as e:
        print(f"❌ Document processing error: {e}")
        return "Sorry, I encountered an error reading your document. Please try again."
    finally:
        # Cleanup
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

def process_pdf(user_id: str, file_path: str, filename: str) -> str:
    """
    Extract text from PDF. Look for VIN first.
    """
    text_content = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            # check first 2 pages
            if len(pdf.pages) > 5:
                return "You cannot upload pdf more than 5 pages."

            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_content += text + "\n"
    except Exception as e:
        print(f"PDF extract error: {e}")
        # Continue to image fallback if text fails
        pass
    
    # --- STRATEGY: Text Content Analysis ---
    if len(text_content) > 0:
        # B. Check for Part Numbers (filtering quantities)
        # Expected format: "12345 5", "ABC-123 10" -> Remove small numbers (qty)
        potential_tokens = re.split(r'\s+', text_content)
        valid_part_numbers = []
        
        for token in potential_tokens:
            token = token.strip()
            if not token:
                continue
            
            # Normalize: remove special chars to check length
            norm = normalize_part_number(token)
            
            # Filter: Quantities are usually 1, 2, 10, 50, 100 (len 1-3)
            # Part numbers are usually longer. We pick threshold len >= 4.
            # Also ensure it has at least one digit (to avoid random words like 'ITEM')
            if len(norm) >= 4 and any(c.isdigit() for c in norm):
                valid_part_numbers.append(norm)

        # Unique & Limit
        valid_part_numbers = list(set(valid_part_numbers))
        print(valid_part_numbers)
        if valid_part_numbers:
            print(f"✅ Found {len(valid_part_numbers)} potential part numbers in PDF Text (quantities filtered).")
            return handle_part_number_search(valid_part_numbers, intent="partnumber_handling", language="en")
        
        # If text was found but NO VIN and NO Part Numbers -> Fallthrough to Image Fallback
        # (It might be a scanned image with some OCR garbage text)
    
    
    # 2. FALLBACK: Scanned PDF (Image)
    print("⚠️ No VIN found in text. Attempting OCR/Vision via Image Conversion...")
    try:
        # Load PDF
        pdf = pdfium.PdfDocument(file_path)
        
        # Iterate through pages (limit to first 5 to avoid timeouts)
        for i, page in enumerate(pdf):
            if i >= 5:
                return "You cannot upload pdf more than 5 pages."
                
            print(f"🔄 Scanning Page {i+1} for VIN...")
            
            # Render at high DPI (e.g. 300 equivalent)
            bitmap = page.render(scale=2) 
            pil_image = bitmap.to_pil()
            
            # Convert to Bytes
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format='JPEG')
            img_bytes = img_byte_arr.getvalue()
            
            # Re-use the existing Image Logic manually
            # 1. Detect Intent
            intent_key = detect_image_intent(img_bytes, "image/jpeg")
            print(f"🔍 Page {i+1} Intent: {intent_key}")
            
            # 2. Execute Intent
            result = run_image_intent(intent_key, img_bytes, "image/jpeg")
            message = result.get("message", "")
            print(f"👀 Page {i+1} Vision Output: '{message}'")
            
            # 3. Extract VIN
            vin_from_vision = extract_vin_from_text(message)
            
            if vin_from_vision:
                print(f"✅ Found VIN on Page {i+1}: {vin_from_vision}")
                session = get_session(user_id)
                old_vin = session["entities"].get("vin")
                response = handle_vin_input(vin_from_vision, user_id, session, message,old_vin)
                if response:
                    return response
                return f"I found chassis number {vin_from_vision} in your scanned document! What parts do you need? 🔧"
        
        print("❌ Scanned all pages, NO VIN found.")

    except Exception as e:
        print(f"❌ Scanned PDF fallback failed: {e}")

    return (
        "I analyzed the document but couldn't find a valid chassis number (VIN). "
        "Please ensure the VIN is clearly visible or send a clear photo of the registration card."
    )

def process_excel_or_csv(user_id: str, file_path: str, ext: str) -> str:
    """
    Read Excel/CSV. Look for 'part number' column or assume first column.
    """
    try:
        if ext == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        # Strategy: Look for column with name like 'part', 'number', 'code', 'oe'
        # Or just take the first column if it looks alphanumeric.
        
        target_col = None
        # 1. Variable header matching
        for col in df.columns:
            c = str(col).lower()
            if "part number" in c or "number" in c or "code" in c or "oe" in c:
                target_col = col
                break
        
        # 2. Fallback to first column
        if not target_col:
            target_col = df.columns[0]

        # Extract values
        raw_values = df[target_col].dropna().astype(str).tolist()
        # Normalize and Filter
        clean_parts = []
        for val in raw_values:
            norm = normalize_part_number(val)
            # Basic validation: length > 3 and has digits?
            if norm and len(norm) > 3:
                clean_parts.append(norm)

        # Cap at 50 to avoid exploding the query
        clean_parts = clean_parts[:]

        if not clean_parts:
            return "I couldn't find any valid part numbers in the Excel sheet. Please check the columns."

        print(f"✅ Found {len(clean_parts)} part numbers in Excel.")
        print(clean_parts)  
        # Reuse existing logic
        return handle_part_number_search(clean_parts, intent="partnumber_handling", language="en")

    except Exception as e:
        print(f"Excel parse error: {e}")
        return "I couldn't read this Excel file. Please ensure it's a standard format."
