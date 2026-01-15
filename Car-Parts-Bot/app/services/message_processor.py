
from app.extensions import db
from app.models import Stock, User
from app.services.gpt_service import GPTService
from app.services.lead_service import LeadService
from collections import defaultdict
# 🚀 UPDATED: Import Scrape.do scraper instead of old HTTP scraper
from app.services.scraper.partsouq_xpath_scraper import get_scraper
from app.services.lead_service import lead_service
from sqlalchemy import func
import re
import asyncio
# from app.services.gpt_service import gpt
def normalize_part_number(pn: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', pn.upper()) if pn else ''
def normalize_pn(pn: str) -> str:
    return "".join(pn.split()) if pn else ""

def process_user_message(user_id: str, message: str) -> str:
    """
    Main message processing function.
    Routes messages based on intent and handles all business logic.
    """
    print("PROCESS USER MESSAGE STARTED")
    gpt = GPTService()
   
    JSON_ONLY_INTENTS = {
        "partnumber_handling",
        "vin_handling"
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
        if intent == "partnumber_handling":
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

        # ======================================================
        #  LOGIC 2: VIN/CHASSIS HANDLING
        # ======================================================
        if intent == "vin_handling":
            chassis_number = entities.get("chassis")
            print("We are breaking here - VIN handling")
            # --- VIN validation ---
            if not chassis_number or len(chassis_number) != 17:
                return "Please provide a valid 17-digit chassis number."
            print("WE HAVE TO GO THROUGH THIS")
            # ⚠️ SAFER filler words (no domain nouns)
            FILLER_WORDS = (
                r'hi|hello|please|price|cost|need|'
                r'for|give|me|want|search|find|'
                r'my|our|your|i|we|us|of|also|with|without|about|'
                r'chassis|chasis|vin|number|numer|is|this|'
                r'the|and|send|sent|show|get'
            )

            # --- Clean message ---
            clean_msg = re.sub(re.escape(chassis_number), '', message, flags=re.IGNORECASE)
            clean_msg = re.sub(rf'(?i)\b({FILLER_WORDS})\b', '', clean_msg)
            clean_msg = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_msg)
            clean_msg = re.sub(r'\s+', ' ', clean_msg).strip()
            clean_check = re.sub(r'[^a-zA-Z0-9]', '', clean_msg)

            print(f"DEBUG: Message='{message}' | Clean='{clean_msg}' | Check='{clean_check}'")

            # --- SCENARIO A: ONLY VIN ---
            if not clean_check:
                user = db.session.query(User).filter_by(whatsapp_id=user_id).first()
                if not user:
                    user = User(whatsapp_id=user_id)
                    db.session.add(user)

                user.current_vin = chassis_number
                db.session.commit()

                return (
                    "Thank you! I've saved your chassis number 🚗.\n\n"
                    "You can now ask for parts by name, e.g.,\n"
                    "**Oil Filter** or **Brake Pads**"
                )

            # --- SCENARIO B: VIN + PART ---
            part_name = clean_msg.lower().strip()

            # ❌ Block nonsense queries early
            if len(part_name) < 3:
                return "Please mention a valid part name like Oil Filter, Brake Pad, etc."

            print(f"DEBUG: Searching for '{part_name}' with VIN {chassis_number}")

            # 🚀 Async Scraper runner (SAFE & CORRECT)
            try:
                scraper = get_scraper()
                search_result = scraper.search_part(chassis_number, part_name)
            except Exception as e:
                print(f"[!] Scraper error: {e}")
                return "Our system encountered an error. Our team will contact you shortly. 😊"

            print("Search result:", search_result)

            # --- Error handling ---
            if "error" in search_result:
                msg = search_result.get("error", "")
                if "VIN" in msg or "blocked" in msg:
                    return "Unable to find this VIN in our catalog. Our team will assist you. 😊"
                elif "diagram" in msg:
                    return f"Could not find '{part_name}' for this vehicle. Try another part name. 😊"
                return "Our team will contact you as we are unable to process your request. 😊"

            # --- Extract OEM numbers ---
            found_oem_numbers = list({
                normalize_pn(p["number"])
                for p in search_result.get("parts", [])
                if p.get("number") and p["number"] != "N/A"
            })


            if not found_oem_numbers:
                return "No part numbers found in catalog. Our team will assist you. 😊"

            normalized_db_pn = func.upper(Stock.part_number)

            for ch in [
                ' ', '-', '+', '%', '$', '_', '/', '.', ',', ':', ';',
                '#', '@', '!', '*', '(', ')', '?', '&', '=', '<', '>',
                '~', '`', '|', '^', '"', "'",
                '´', '“', '”', '‘', '’', '–', '—', '•', '…',
                '{', '}', '[', ']'
            ]:
                normalized_db_pn = func.replace(normalized_db_pn, ch, '')

            stock_parts = (
                db.session.query(Stock)
                .filter(normalized_db_pn.in_(found_oem_numbers))
                .all()
            )
            print("Matched stock parts:", stock_parts)

            if not stock_parts:
                return "I am unable to fetch your details accurately at the moment.\nOur team will contact you soon to assist you further.\nYou may also reach us on WhatsApp at +971504827057. 😊"

            # ✅ FINAL RESPONSE DATA
            formatted_data = [
                {
                    "name": p.item_desc,
                    "part_number": p.part_number,
                    "brand": p.brand,
                    "price": float(p.price) if p.price else None,
                    "qty": p.qty,
                }
                for p in stock_parts
            ]
            grouped_data = {"RESULTS": formatted_data}
            # print("Final grouped data for VIN handling:", grouped_data)
            return gpt.format_response(grouped_data, "part_number", language)

    # print("HOLA SLOW")
    # ---- 4. Reply Only Intents (Greetings, brand support, etc.) ----
    reply = gpt.generate_plain_response(message, intent)
    if not reply:
        return gpt.get_fallback_menu(language)
 
    # Translate if needed (GPT already handles language in most cases)
    if language and language != "en":
        reply = gpt.translation_service.translate(reply, language)
    print("FINAL REPLY:")
    return reply