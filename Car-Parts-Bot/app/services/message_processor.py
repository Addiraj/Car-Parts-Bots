
# from app.extensions import db
# from app.models import Stock, User
# from app.services.gpt_service import GPTService
# # from app.services.lead_service import LeadService
# from app.services.extract_vin_service import extract_vin_from_text
# from collections import defaultdict
# from app.services.translation_service import TranslationService
# from app.services.scraper.partsouq_xpath_scraper import get_scraper
# from app.services.lead_service import lead_service
# from app.session_store import get_session, save_session, set_vin, set_awaiting
# from sqlalchemy import func
# import re
# # import asyncio

# FILLER_WORDS = (
#                 r'hi|hello|please|price|cost|need|'
#                 r'for|give|me|want|search|find|'
#                 r'my|our|your|i|we|us|of|also|with|without|about|'
#                 r'chassis|chasis|vin|number|numer|is|this|'
#                 r'the|and|send|sent|show|get'
#             )

# translator = TranslationService()
# # from app.services.gpt_service import gpt
# def normalize_part_number(pn: str) -> str:
#     return re.sub(r'[^A-Z0-9]', '', pn.upper()) if pn else ''
# def normalize_pn(pn: str) -> str:
#     return "".join(pn.split()) if pn else ""

# def process_user_message(user_id: str, message: str) -> str:
#     """
#     Main message processing function.
#     Routes messages based on intent and handles all business logic.
#     """
#     gpt = GPTService()
#     print("Checking for redis session for user:", user_id)
#     session = get_session(user_id)
#     # 2️⃣ 🔥 Detect NEW VIN in CURRENT message
#     new_vin = extract_vin_from_text(message)  # your regex / structured extractor

#     if new_vin:
#         old_vin = session["entities"].get("vin")

#         # Overwrite VIN (this is expected behavior)
#         set_vin(session, new_vin)

#         # Reset dependent state
#         session["entities"]["part"] = None
#         set_awaiting(session, "part_name")

#         save_session(user_id, session)

#         # Optional UX clarity
#         if old_vin and old_vin != new_vin:
#             return (
#                 "I've updated your VIN 🚗.\n\n"
#                 "Please tell me which part you need."
#             )

#         return (
#             "Thank you! I've saved your chassis number 🚗.\n\n"
#             "Please tell me which part you need."
#         )

#     print("Session data:", session)
#     stored_vin = session["entities"].get("vin")
#     print("Stored VIN in session:", stored_vin)
#     # ======================================================
#     # PRIORITY ROUTE: VIN already stored + user asking part
#     # ======================================================
#     if stored_vin:
#         # Try to treat message as part name
#         print("VIN IS STORED IN SESSION, CHECKING FOR PART NAME IN CATELOG")
#         language = translator.detect_language(message) or "en"
#         clean_msg = re.sub(re.escape(stored_vin), '', message, flags=re.IGNORECASE)
#         clean_msg = re.sub(rf'(?i)\b({FILLER_WORDS})\b', '', clean_msg)
#         clean_msg = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_msg)
#         clean_msg = re.sub(r'\s+', ' ', clean_msg).strip()
#         part_name = clean_msg.strip().lower()

#         words = part_name.split()
#         if len(words) >= 1 and all(w.isalpha() for w in words):

#             print(f"USING STORED VIN {stored_vin} FOR PART {part_name}")

#             try:
#                 scraper = get_scraper()
#                 search_result = scraper.search_part(stored_vin, part_name)
#             except Exception as e:
#                 print("Scraper error:", e)
#                 return "Our system encountered an error. Our team will assist you shortly. 😊"

#             if "error" not in search_result and search_result.get("parts"):
#                 # ✅ SAME logic you already have below
#                 found_oem_numbers = list({
#                     normalize_pn(p["number"])
#                     for p in search_result.get("parts", [])
#                     if p.get("number") and p["number"] != "N/A"
#                 })

#                 if not found_oem_numbers:
#                     return "No part numbers found. Our team will assist you."

#                 normalized_db_pn = func.upper(Stock.part_number)
#                 for ch in [
#                 ' ', '-', '+', '%', '$', '_', '/', '.', ',', ':', ';',
#                 '#', '@', '!', '*', '(', ')', '?', '&', '=', '<', '>',
#                 '~', '`', '|', '^', '"', "'",
#                 '´', '“', '”', '‘', '’', '–', '—', '•', '…',
#                 '{', '}', '[', ']'
#                 ]:
#                     normalized_db_pn = func.replace(normalized_db_pn, ch, '')

#                 stock_parts = (
#                     db.session.query(Stock)
#                     .filter(normalized_db_pn.in_(found_oem_numbers))
#                     .all()
#                 )
#                 print("Matched stock parts with stored VIN:", stock_parts)
#                 if stock_parts:
#                     formatted = [{
#                         "name": p.item_desc,
#                         "part_number": p.part_number,
#                         "brand": p.brand,
#                         "price": float(p.price) if p.price else None,
#                         "qty": p.qty,
#                     } for p in stock_parts]

#                     return gpt.format_response(
#                         {"RESULTS": formatted},
#                         "part_number",
#                         language
#                     )
#                 # 🔴 IMPORTANT: stop fallback
#                 return (
#                     "I couldn't find this part for your vehicle right now.\n"
#                     "Please try a different part name or our team will assist you shortly. 😊"
#                 )
#     print("PROCEEDING WITH NORMAL FLOW")
#     # print("PROCESS USER MESSAGE STARTED")
    
#     JSON_ONLY_INTENTS = {
#         "partnumber_handling",
#         "vin_handling"
#     }
 
#     # ---- 1. Intent Classification ----
#     intent_data = gpt.extract_intent(message)
#     intent = intent_data.get("intent")
#     language = intent_data.get("language")
#     print("Intent detected:", intent)
    
#     # Save lead
#     lead_service.create_lead(
#         whatsapp_user_id=user_id,
#         query_text=message,
#         intent=intent
#     )
#     print("Lead saved.")
#     # ---- 2. Fallback for Low Confidence ----
#     if intent_data.get("fallback_required", False):
#         if intent != "brand_support_check":
#             return gpt.get_fallback_menu(language)
    
#     # ---- 3. Handle Data Intents ----
#     if intent in JSON_ONLY_INTENTS:
#         structured = gpt.generate_structured_request(message, intent)
#         entities = structured.get("entities", {})
 
#         # Safety check for entities
#         if not entities:
#             if structured.get("needs_more_info", False):
#                 if intent == "vin_handling":
#                     return "Please provide a valid chassis number to proceed."
#                 return gpt.get_fallback_menu(language)
#             entities = structured.get("entities", {})
 
#         # ======================================================
#         #  LOGIC 1: PART NUMBER (User gave explicit part code)
#         # ======================================================
#         if intent == "partnumber_handling":
#             # Block natural language queries pretending to be part numbers
#             alpha_chars = sum(c.isalpha() for c in message)
#             total_chars = max(len(message), 1)

#             if alpha_chars / total_chars > 0.6:
#                 intent = "brand_support_check"

#             print("Entities extracted for part number handling:", entities.get("part_numbers"))
#             # -------- Extract part numbers --------
#             structured_part_numbers = entities.get("part_numbers") or []
#             part_numbers = [
#                 normalize_part_number(pn)
#                 for pn in structured_part_numbers
#                 if pn and normalize_part_number(pn)
#             ]
#             print("Normalized part numbers:", part_numbers)
#             if not part_numbers and entities.get("part_number"):
#                 part_numbers = [entities.get("part_number")]
#             if not part_numbers:
#                 return gpt.format_response([], intent, language)
#             # results_by_pn = {}

#             if part_numbers:
#                 # 🔒 Build normalized DB expression ONCE
#                 normalized_db_pn = func.upper(Stock.part_number)
#                 for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
#                         '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
#                         '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
#                     normalized_db_pn = func.replace(normalized_db_pn, ch, '')

#                 # -------------------------------
#                 # STEP 1: Match all input PNs
#                 # -------------------------------
#                 matched_parts = []
#                 matched_tags = set()

#                 for pn in part_numbers:
#                     pn_clean = normalize_part_number(pn)
#                     if not pn_clean:
#                         continue
#                     parts = (
#                         db.session.query(Stock)
#                         .filter(normalized_db_pn == pn_clean)
#                         .all()
#                     )
                    
#                     for p in parts:
#                         matched_parts.append(p)
#                         if p.tag:
#                             matched_tags.add(p.tag)

#                     if not matched_tags:
#                         return (
#                             f"Sorry, we couldn't find any parts matching the provided "
#                             f"part number(s). Our team will assist you shortly. 😊"
#                         )
                    
#                     # -------------------------------
#                     # STEP 3: Fetch ALL sibling parts
#                     # -------------------------------
#                     siblings = (
#                         db.session.query(Stock)
#                         .filter(Stock.tag.in_(matched_tags))
#                         .order_by(Stock.tag, Stock.price.asc())
#                         .all()
#                     )

#                     # -------------------------------
#                     # STEP 4: Deduplicate results
#                     # -------------------------------
#                     unique_parts = {}
#                     for p in siblings:
#                         dedupe_key = (p.part_number, p.brand,p.price)
#                         unique_parts[dedupe_key] = p

#                     final_parts = list(unique_parts.values())

#                     results = [
#                         {
#                             "name": p.item_desc,
#                             "part_number": p.part_number,
#                             "brand": p.brand,
#                             "price": float(p.price) if p.price is not None else None,
#                             "qty": p.qty,
#                             "tag": p.tag,
#                         }
#                         for p in final_parts
#                     ]
#                 is_multiple = len(part_numbers) > 1
#                 # print("Final results for part number handling:", results)
        
#                 grouped_results = defaultdict(list)

#                 for r in results:
#                     tag = r.get("tag", "OTHER")
#                     grouped_results[tag].append(r)
#                 # print("Grouped results:", dict(grouped_results))
#                 return gpt.format_response(grouped_results, intent, language,is_multiple)

#         # ======================================================
#         #  LOGIC 2: VIN/CHASSIS HANDLING
#         # ======================================================
#         if intent == "vin_handling":
#             chassis_number = entities.get("chassis")
#             print("We are breaking here - VIN handling")
#             # --- VIN validation ---
#             if not chassis_number or len(chassis_number) != 17:
#                 return "Please provide a valid 17-digit chassis number."
#             print("WE HAVE TO GO THROUGH THIS")
#             # ⚠️ SAFER filler words (no domain nouns)
            

#             # --- Clean message ---
#             clean_msg = re.sub(re.escape(chassis_number), '', message, flags=re.IGNORECASE)
#             clean_msg = re.sub(rf'(?i)\b({FILLER_WORDS})\b', '', clean_msg)
#             clean_msg = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_msg)
#             clean_msg = re.sub(r'\s+', ' ', clean_msg).strip()
#             clean_check = re.sub(r'[^a-zA-Z0-9]', '', clean_msg)

#             print(f"DEBUG: Message='{message}' | Clean='{clean_msg}' | Check='{clean_check}'")

#             # --- SCENARIO A: ONLY VIN ---
#             if not clean_check:
#                 # Load Redis session
#                 session = get_session(user_id)
#                 # Store VIN in session
#                 set_vin(session, chassis_number)
#                 # OPTIONAL (recommended): set next expected step
#                 set_awaiting(session, "part_name")
#                 # Save session back to Redis (TTL refreshed)
#                 save_session(user_id, session)

#                 return (
#                     "Thank you! I've saved your chassis number 🚗.\n\n"
#                     "You can now ask for parts by name, for example:\n"
#                     "Oil Filter or Brake Pads"
#                 )

#             # --- SCENARIO B: VIN + PART ---
#             part_name = clean_msg.lower().strip()

#             # ❌ Block nonsense queries early
#             if len(part_name) < 3:
#                 return "Please mention a valid part name like Oil Filter, Brake Pad, etc."

#             print(f"DEBUG: Searching for '{part_name}' with VIN {chassis_number}")

#             # 🚀 Async Scraper runner (SAFE & CORRECT)
#             try:
#                 scraper = get_scraper()
#                 search_result = scraper.search_part(chassis_number, part_name)
#             except Exception as e:
#                 print(f"[!] Scraper error: {e}")
#                 return "Our system encountered an error. Our team will contact you shortly. 😊"

#             print("Search result:", search_result)

#             # --- Error handling ---
#             if "error" in search_result:
#                 msg = search_result.get("error", "")
#                 if "VIN" in msg or "blocked" in msg:
#                     return "Unable to find this VIN in our catalog. Our team will assist you. 😊"
#                 elif "diagram" in msg:
#                     return f"Could not find '{part_name}' for this vehicle. Try another part name. 😊"
#                 return "Our team will contact you as we are unable to process your request. 😊"

#             # --- Extract OEM numbers ---
#             found_oem_numbers = list({
#                 normalize_pn(p["number"])
#                 for p in search_result.get("parts", [])
#                 if p.get("number") and p["number"] != "N/A"
#             })


#             if not found_oem_numbers:
#                 return "No part numbers found in catalog. Our team will assist you. 😊"

#             normalized_db_pn = func.upper(Stock.part_number)

#             for ch in [
#                 ' ', '-', '+', '%', '$', '_', '/', '.', ',', ':', ';',
#                 '#', '@', '!', '*', '(', ')', '?', '&', '=', '<', '>',
#                 '~', '`', '|', '^', '"', "'",
#                 '´', '“', '”', '‘', '’', '–', '—', '•', '…',
#                 '{', '}', '[', ']'
#             ]:
#                 normalized_db_pn = func.replace(normalized_db_pn, ch, '')

#             stock_parts = (
#                 db.session.query(Stock)
#                 .filter(normalized_db_pn.in_(found_oem_numbers))
#                 .all()
#             )
#             print("Matched stock parts:", stock_parts)

#             if not stock_parts:
#                 return "I am unable to fetch your details accurately at the moment.\nOur team will contact you soon to assist you further.\nYou may also reach us on WhatsApp at +971504827057. 😊"

#             # ✅ FINAL RESPONSE DATA
#             formatted_data = [
#                 {
#                     "name": p.item_desc,
#                     "part_number": p.part_number,
#                     "brand": p.brand,
#                     "price": float(p.price) if p.price else None,
#                     "qty": p.qty,
#                 }
#                 for p in stock_parts
#             ]
#             grouped_data = {"RESULTS": formatted_data}
#             # print("Final grouped data for VIN handling:", grouped_data)
#             return gpt.format_response(grouped_data, "part_number", language)

#     # print("HOLA SLOW")
#     # ---- 4. Reply Only Intents (Greetings, brand support, etc.) ----
#     reply = gpt.generate_plain_response(message, intent)
#     if not reply:
#         return gpt.get_fallback_menu(language)
 
#     # Translate if needed (GPT already handles language in most cases)
#     if language and language != "en":
#         reply = gpt.translation_service.translate(reply, language)
#     print("FINAL REPLY:")
#     return reply

import re
from sqlalchemy import func
from app.extensions import db
from app.models import Stock
from app.services.gpt_service import GPTService
from app.services.translation_service import TranslationService
from app.services.extract_vin_service import extract_vin_from_text , get_vin_validation_error
from app.services.scraper.partsouq_xpath_scraper import get_scraper
from app.services.lead_service import lead_service
from app.session_store import get_session, save_session, set_vin, set_awaiting
from collections import defaultdict
translator = TranslationService()


def handle_vin_input(new_vin: str, user_id: str, session: dict, message: str = "", old_vin: str = None) -> str:
    """
    Reusable logic for when a VIN is detected (via Text, OCR, or PDF).
    Returns a response string or None if it should fall through.
    """
    # Save / overwrite VIN
    set_vin(session, new_vin)
    set_awaiting(session, "part_name")
    session["entities"]["part"] = None
    save_session(user_id, session)

    # Check if message is VIN-only
    # If called from a document upload, original_message might be empty or just the filename, so we assume VIN-only behavior if mostly empty.
    residual = ""
    if message:
        residual = re.sub(re.escape(new_vin), '', message, flags=re.IGNORECASE)
        residual = re.sub(rf'(?i)\b({FILLER_WORDS})\b', '', residual)
        residual = re.sub(r'[^a-zA-Z]', '', residual)
        print(f"DEBUG: Message='{message}' | Residual after VIN removal='{residual}'")

    if not residual:
        try:
            # 1. Initialize Scraper
            scraper = get_scraper()
            if scraper is None:
                return "SCRAPER NOT ACCESSIBLE"
            vehicle_info = scraper.get_vehicle_details(new_vin)
            vehicle_brand = vehicle_info.get('brand', 'N/A')
            
            # Normalize and check supported brands
            supported_brands = ["BMW", "MERCEDES", "ROLLS ROYCE", "MINI", "HONDA"]
            brand_upper = vehicle_brand.upper().strip()
            
            is_supported = any(b in brand_upper for b in supported_brands)
            
            if vehicle_info and is_supported:
                # 3. Format the Response
                if old_vin and old_vin != new_vin:
                    return (
                        f"🚗 **Vehicle Identified!**\n"
                        f"**Brand:** {vehicle_info.get('brand', 'N/A')}\n"
                        f"**Name:** {vehicle_info.get('name', 'N/A')}\n"
                        f"**Year:** {vehicle_info.get('date', 'N/A')}\n\n"
                        f"I've updated this chassis number. Please tell me which part you need! 🔧"
                    )
                return (
                    f"🚗 **Vehicle Identified!**\n"
                    f"**Brand:** {vehicle_info.get('brand', 'N/A')}\n"
                    f"**Name:** {vehicle_info.get('name', 'N/A')}\n"
                    # f"**Model:** {vehicle_info.get('model', 'N/A')}\n"
                    f"**Year:** {vehicle_info.get('date', 'N/A')}\n\n"
                    f"I've saved this chassis number. Please tell me which part you need! 🔧"
                )
            elif vehicle_info:
                return (
                    f"❌ *Vehicle Not Supported* 🚘\n"
                    f"• *VIN:* {vin}\n"
                    f"• *Brand:* {vehicle_brand}\n\n"
                    f"Sorry, we currently only support BMW, Mercedes-Benz, Rolls-Royce, Mini Cooper, and Honda."
                )

        except Exception as e:
            print(f"[!] Error fetching vehicle details: {e}")
            # If it fails, it will just fall through to the standard message below
            pass

    # FALLBACK if scraper fails or no residual text
    return (
        f"I've saved this chassis number **{new_vin}**. 🚗\n\n"
        f"Please tell me which part you need! (e.g., 'Brake Pads')"
    )

FILLER_WORDS = (
    r'hi|hello|please|price|cost|need|ve|will|'
    r'for|give|me|want|search|find|'
    r'my|our|your|i|we|us|of|also|with|without|about|ll|proceed|request|'
    r'chassis|chasis|vin|number|numer|is|this|'
    r'the|and|send|sent|show|get|car|vehicle|I|identified|the|VIN|'
)

# from app.services.gpt_service import gpt
def normalize_part_number(pn: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', pn.upper()) if pn else ''
def normalize_pn(pn: str) -> str:
    return "".join(pn.split()) if pn else ""
def normalize_pn(pn: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', pn.upper()) if pn else ""

def process_user_message(user_id: str, message: str) -> str:
    gpt = GPTService()
    # language = translator.detect_language(message) or "en"

    # ======================================================
    # 1️⃣ LOAD SESSION
    # ======================================================
    session = get_session(user_id)
    stored_vin = session["entities"].get("vin")
    # ======================================================
    # 2️⃣ DETECT VIN IN CURRENT MESSAGE (ALWAYS FIRST)
    # ======================================================
    new_vin = extract_vin_from_text(message)
    print("NEW VIN:", new_vin)

    # 2a. If no valid VIN, check for VIN-like errors (typos, length, etc.)
    if not new_vin:
        vin_error = get_vin_validation_error(message)
        if vin_error:
            # We found something that looks like a broken VIN.
            # Fail fast and tell the user.
            return vin_error
    if new_vin:
        old_vin = stored_vin
        # Save / overwrite VIN
        set_vin(session, new_vin)
        set_awaiting(session, "part_name")
        session["entities"]["part"] = None
        save_session(user_id, session)

        # Check if message is VIN-only
        residual = re.sub(re.escape(new_vin), '', message, flags=re.IGNORECASE)
        residual = re.sub(rf'(?i)\b({FILLER_WORDS})\b', '', residual)
        residual = re.sub(r'[^a-zA-Z]', '', residual)
        print(f"DEBUG: Message='{message}' | Residual after VIN removal='{residual}'")
        if not residual:
            try:
                # 1. Initialize Scraper
                scraper = get_scraper()

                # 2. Fetch Details
                vehicle_info = scraper.get_vehicle_details(new_vin)
                vehicle_brand = vehicle_info.get('brand', 'N/A')
            
                # Normalize and check supported brands
                supported_brands = ["BMW", "MERCEDES", "ROLLS ROYCE", "MINI", "HONDA"]
                brand_upper = vehicle_brand.upper().strip()
                
                is_supported = any(b in brand_upper for b in supported_brands)
                
                if vehicle_info and is_supported:
                    # 3. Format the Response
                    if old_vin and old_vin != new_vin:
                        return (
                            f"🚗 **Vehicle Identified!**\n"
                            f"**Brand:** {vehicle_info.get('brand', 'N/A')}\n"
                            f"**Name:** {vehicle_info.get('name', 'N/A')}\n"
                            f"**Year:** {vehicle_info.get('date', 'N/A')}\n\n"
                            f"I've updated this chassis number. Please tell me which part you need! 🔧"
                        )
                    return (
                        f"🚗 **Vehicle Identified!**\n"
                        f"**Brand:** {vehicle_info.get('brand', 'N/A')}\n"
                        f"**Name:** {vehicle_info.get('name', 'N/A')}\n"
                        f"**Year:** {vehicle_info.get('date', 'N/A')}\n\n"
                        f"I've saved this chassis number. Please tell me which part you need! 🔧"
                    )
                elif vehicle_info:
                    return (
                        f"❌ *Vehicle Not Supported* 🚘\n"
                        f"• *VIN:* {vin}\n"
                        f"• *Brand:* {vehicle_brand}\n\n"
                        f"Sorry, we currently only support BMW, Mercedes-Benz, Rolls-Royce, Mini Cooper, and Honda."
                    )
                else:
                    return "Our team will conatact you soon."
            except Exception as e:
                print(f"[!] Error fetching vehicle details: {e}")
                # If it fails, it will just fall through to the standard message below
                pass

        # VIN + something else → continue normally
        stored_vin = new_vin
    print(session)
    # ======================================================
    # 4️⃣ INTENT FLOW (SYMPTOMS / GREETINGS / QUESTIONS)
    # ======================================================
    print("PROCEEDING WITH NORMAL FLOW")
    
    JSON_ONLY_INTENTS = {
        "part_number_handling",
    }
 
    # ---- 1. Intent Classification ----
    intent_data = gpt.extract_intent(message)
    intent = intent_data.get("intent")
    language = intent_data.get("language")
    print("Intent detected:", intent)
    
    # Save lead
    lead_service.create_lead(
        whatsapp_user_id=user_id,
        query_text=message,
        intent=intent
    )
    print("Lead saved.")
    # ---- 2. Fallback for Low Confidence ----
    if intent_data.get("fallback_required", False):
        if intent != "brand_support_check":
            return gpt.get_fallback_menu(language)
    
    # ---- 3. Handle Data Intents ----
    if intent in JSON_ONLY_INTENTS:
        structured = gpt.generate_structured_request(message, intent)
        entities = structured.get("entities", {})
 
        # Safety check for entities
        if not entities:
            if structured.get("needs_more_info", False):
                if intent == "vin_handling":
                    return "Please provide a valid chassis number to proceed."
                return gpt.get_fallback_menu(language)
            entities = structured.get("entities", {})
 
        # ======================================================
        #  LOGIC 1: PART NUMBER (User gave explicit part code)
        # ======================================================
        if intent == "part_number_handling":
            # Block natural language queries pretending to be part numbers
            alpha_chars = sum(c.isalpha() for c in message)
            total_chars = max(len(message), 1)

            if alpha_chars / total_chars > 0.6:
                intent = "brand_support_check"

            print("Entities extracted for part number handling:", entities.get("part_numbers"))
            # -------- Extract part numbers --------
            structured_part_numbers = entities.get("part_numbers") or []
            part_numbers = [
                normalize_part_number(pn)
                for pn in structured_part_numbers
                if pn and normalize_part_number(pn)
            ]
            print("Normalized part numbers:", part_numbers)
            if not part_numbers and entities.get("part_number"):
                part_numbers = [entities.get("part_number")]
            if not part_numbers:
                return gpt.format_response([], intent, language)
            # results_by_pn = {}

            if part_numbers:
                # 🔒 Build normalized DB expression ONCE
                normalized_db_pn = func.upper(Stock.part_number)
                for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
                        '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
                        '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
                    normalized_db_pn = func.replace(normalized_db_pn, ch, '')

                # -------------------------------
                # STEP 1: Match all input PNs
                # -------------------------------
                matched_parts = []
                matched_tags = set()
                found_any = False
                missing_pns = []

                for pn in part_numbers:
                    pn_clean = normalize_part_number(pn)
                    if not pn_clean:
                        continue
                    parts = (
                        db.session.query(Stock)
                        .filter(normalized_db_pn == pn_clean)
                        .all()
                    )
                    
                    if parts:
                        found_any = True
                        for p in parts:
                            matched_parts.append(p)
                            if p.tag:
                                matched_tags.add(p.tag)
                    else:
                        missing_pns.append(pn)

                # If absolutely nothing found for any input
                if not found_any and not missing_pns:
                     return (
                            f"Sorry, we couldn't find any parts matching the provided "
                            f"part number(s). Our team will assist you shortly. 😊"
                        )
                    
                # -------------------------------
                # STEP 3: Fetch ALL sibling parts
                # -------------------------------
                siblings = []
                if matched_tags:
                    siblings = (
                        db.session.query(Stock)
                        .filter(Stock.tag.in_(matched_tags))
                        .order_by(Stock.tag, Stock.price.asc())
                        .all()
                    )

                # -------------------------------
                # STEP 4: Deduplicate results & Add Missing
                # -------------------------------
                unique_parts = {}
                for p in siblings:
                    dedupe_key = (p.part_number, p.brand,p.price)
                    unique_parts[dedupe_key] = p

                final_parts = list(unique_parts.values())

                results = [
                    {
                        "name": p.item_desc,
                        "part_number": p.part_number,
                        "brand": p.brand,
                        "price": float(p.price) if p.price is not None else None,
                        "qty": p.qty,
                        "tag": p.tag,
                    }
                    for p in final_parts
                ]

                # Add entries for missing parts
                for mpn in missing_pns:
                    results.append({
                        "name": "Part not found. Our team will contact you shortly. Pls contact +971 50 482 7057",
                        "part_number": mpn,
                        "brand": None,
                        "price": None,
                        "qty": 0,
                        "tag": f"Requested: {mpn}"
                    })

                is_multiple = len(part_numbers) > 1
                # print("Final results for part number handling:", results)
        
                grouped_results = defaultdict(list)

                for r in results:
                    tag = r.get("tag", "OTHER")
                    grouped_results[tag].append(r)
                # print("Grouped results:", dict(grouped_results))
                return gpt.format_response(grouped_results, intent, language,is_multiple)
        
    if stored_vin and intent=="car_part_request":
        if language and language != "en":
            try:
                print("GO TO TRANSLATION FOR PART NAME REQUEST")
                message = translator.translate(message, "en")
            except Exception as e:
                print(f"Translation failed: {e}")
        part_name = gpt.extract_part_name_with_gpt(message)
        if not part_name:
            return "Please tell me the part name you are looking for (e.g. Oil Filter, Brake Pads)."

        print(f"USING STORED VIN {stored_vin} FOR PART {part_name}")
        try:
            scraper = get_scraper()
            #WE CAN FETCH MODEL YEAR CAR BRAND IF NEEDED FROM VIN
            search_result = scraper.search_part(stored_vin, part_name)
        except Exception:
            return "Our system encountered an error. Our team will assist you shortly. 😊"
        print("Search result:", search_result)
        if "error" not in search_result and search_result.get("parts"):
            found_oem_numbers = {
                normalize_pn(p["number"])
                for p in search_result["parts"]
                if p.get("number") and p["number"] != "N/A"
            }

            if not found_oem_numbers:
                return "No part numbers found. Our team will assist you."

            normalized_db_pn = func.upper(Stock.part_number)
            for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
                        '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
                        '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
                normalized_db_pn = func.replace(normalized_db_pn, ch, '')

            stock_parts = (
                db.session.query(Stock)
                .filter(normalized_db_pn.in_(found_oem_numbers))
                .all()
            )
            print("Matched stock parts with stored VIN:", stock_parts)
            if stock_parts:
                formatted = [{
                    "name": p.item_desc,
                    "part_number": p.part_number,
                    "brand": p.brand,
                    "price": float(p.price) if p.price else None,
                    "qty": p.qty,
                } for p in stock_parts]

                # Fetch vehicle info for richer response
                vehicle_info = None
                try:
                    vehicle_info = scraper.get_vehicle_details(stored_vin)
                except Exception as e:
                    print(f"Failed to fetch vehicle info for response: {e}")

                return gpt.format_response(
                    {"RESULTS": formatted},
                    "part_number",
                    language,
                    vehicle_info=vehicle_info
                )

            return (
                "I couldn't find this part for your vehicle right now.\n"
                "Our team will assist you shortly. 😊"
            )
        else:
            return (
                "Our team will assist you shortly. 😊"
            )
    # ---- 4. Reply Only Intents (Greetings, brand support, etc.) ----
    reply = gpt.generate_plain_response(message, intent)
    if not reply:
        return gpt.get_fallback_menu(language)
 
    # Translate if needed (GPT already handles language in most cases)
    if language and language != "en":
        reply = gpt.translation_service.translate(reply, language)
    print("FINAL REPLY:")
    return reply

def handle_part_number_search(part_numbers: list[str], intent: str, language: str) -> str:
    """
    Reusable logic for searching a list of part numbers in the database.
    """
    gpt = GPTService()
    
    if not part_numbers:
        return gpt.format_response([], intent, language)
    # results_by_pn = {}

    if part_numbers:
        # 🔒 Build normalized DB expression ONCE
        normalized_db_pn = func.upper(Stock.part_number)
        for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
                '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
                '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
            normalized_db_pn = func.replace(normalized_db_pn, ch, '')

        # -------------------------------
        # STEP 1: Match all input PNs
        # -------------------------------
        matched_parts = []
        matched_tags = set()

        for pn in part_numbers:
            pn_clean = normalize_part_number(pn)
            if not pn_clean:
                continue
            parts = (
                db.session.query(Stock)
                .filter(normalized_db_pn == pn_clean)
                .all()
            )
            
            for p in parts:
                matched_parts.append(p)
                if p.tag:
                    matched_tags.add(p.tag)

            if not matched_tags:
                return (
                    f"Sorry, we couldn't find any parts matching the provided "
                    f"part number(s). Our team will assist you shortly. 😊"
                )
            
            # -------------------------------
            # STEP 3: Fetch ALL sibling parts
            # -------------------------------
            siblings = (
                db.session.query(Stock)
                .filter(Stock.tag.in_(matched_tags))
                .order_by(Stock.tag, Stock.price.asc())
                .all()
            )

            # -------------------------------
            # STEP 4: Deduplicate results
            # -------------------------------
            unique_parts = {}
            for p in siblings:
                dedupe_key = (p.part_number, p.brand,p.price)
                unique_parts[dedupe_key] = p

            final_parts = list(unique_parts.values())

            results = [
                {
                    "name": p.item_desc,
                    "part_number": p.part_number,
                    "brand": p.brand,
                    "price": float(p.price) if p.price is not None else None,
                    "qty": p.qty,
                    "tag": p.tag,
                }
                for p in final_parts
            ]
        is_multiple = len(part_numbers) > 1
        # print("Final results for part number handling:", results)

        grouped_results = defaultdict(list)

        for r in results:
            tag = r.get("tag", "OTHER")
            grouped_results[tag].append(r)
        # print("Grouped results:", dict(grouped_results))
        return gpt.format_response(grouped_results, intent, language,is_multiple)
        
    # if stored_vin and intent=="car_part_request":
    #     part_name = gpt.extract_part_name_with_gpt(message)
    #     if not part_name:
    #         return "Please tell me the part name you are looking for (e.g. Oil Filter, Brake Pads)."

    #     print(f"USING STORED VIN {stored_vin} FOR PART {part_name}")
    #     try:
    #         scraper = get_scraper()
    #         #WE CAN FETCH MODEL YEAR CAR BRAND IF NEEDED FROM VIN
    #         search_result = scraper.search_part(stored_vin, part_name)
    #     except Exception:
    #         return "Our system encountered an error. Our team will assist you shortly. 😊"
    #     print("Search result:", search_result)
    #     if "error" not in search_result and search_result.get("parts"):
    #         found_oem_numbers = {
    #             normalize_pn(p["number"])
    #             for p in search_result["parts"]
    #             if p.get("number") and p["number"] != "N/A"
    #         }

    #         if not found_oem_numbers:
    #             return "No part numbers found. Our team will assist you."

    #         normalized_db_pn = func.upper(Stock.part_number)
    #         for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
    #                     '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
    #                     '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
    #             normalized_db_pn = func.replace(normalized_db_pn, ch, '')

    #         stock_parts = (
    #             db.session.query(Stock)
    #             .filter(normalized_db_pn.in_(found_oem_numbers))
    #             .all()
    #         )
    #         print("Matched stock parts with stored VIN:", stock_parts)
    #         if stock_parts:
    #             formatted = [{
    #                 "name": p.item_desc,
    #                 "part_number": p.part_number,
    #                 "brand": p.brand,
    #                 "price": float(p.price) if p.price else None,
    #                 "qty": p.qty,
    #             } for p in stock_parts]

    #             return gpt.format_response(
    #                 {"RESULTS": formatted},
    #                 "part_number",
    #                 language
    #             )

    #         return (
    #             "I couldn't find this part for your vehicle right now.\n"
    #             "Our team will assist you shortly. 😊"
    #         )
    #     else:
    #         return (
    #             "Our team will assist you shortly. 😊"
    #         )
    # # ---- 4. Reply Only Intents (Greetings, brand support, etc.) ----
    # reply = gpt.generate_plain_response(message, intent)
    # if not reply:
    #     return gpt.get_fallback_menu(language)
 
    # # Translate if needed (GPT already handles language in most cases)
    # if language and language != "en":
    #     reply = gpt.translation_service.translate(reply, language)
    # print("FINAL REPLY:")
    # return reply