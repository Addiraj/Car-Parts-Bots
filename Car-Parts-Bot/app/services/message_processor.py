# from flask import app
# from app.extensions import db
# from app.models import Stock
# from app.services.gpt_service import GPTService
# from app.services.lead_service import LeadService
# from sqlalchemy import func
# import requests
# def process_user_message(user_id: str, message: str) -> str:
#     print("OUTBOUND IP:", requests.get("https://api.ipify.org").text)
 
#     print("PROCESS USER MESSAGE STARTED")
#     gpt = GPTService()
#     # REPLY_ONLY_INTENTS = {
#     #     "greeting",
#     #     "slang_abuse",
#     #     "brand_support_check",
#     #     "missing_required_details",
#     #     "workshop_recommendation",
#     #     "goodbye",
#     #     "vehicle_behaviour"
#     # }
#     JSON_ONLY_INTENTS = {
#         "part_number",
#         "chassis_number"
#     }

#     # ---- Intent classification ----
#     # intent_data = gpt.extract_intent(message)
#     # print("Intent data time check:", intent_data)
#     # intent = intent_data.get("intent")
#     # language = intent_data.get("language")
#     # confidence = intent_data.get("confidence")

#     # # Save lead
#     # LeadService().create_lead(
#     #     whatsapp_user_id=user_id,
#     #     query_text=message,
#     #     intent=intent
#     # )
#     # print("Fallback check:", intent_data)

#     # # ---- Fallback ----
#     # if intent_data.get("fallback_required", False):
#     #     print("Fallback required due to low confidence or unclear intent")
#     #     return gpt.get_fallback_menu(language)
    
#     # print(f"Detected intent: {intent} (confidence: {confidence})")
#     # # ---- Greeting ----
#     # if intent == "greeting":
#     #     structured = gpt.generate_structured_request(message, intent)
#     #     return structured.get("message", "Hello! How can I assist you?")

#     # # ---- Abuse / Slang ----
#     # if intent == "slang_abuse":
#     #     structured = gpt.generate_structured_request(message, intent)
#     #     reply = structured.get("message", "I understand you're upset.")
#     #     reply = gpt.translation_service.translate(reply, language)
#     #     return reply + "\n\n" + gpt.get_fallback_menu(language)
#     # # ---- Thanks ----
#     intent_data = gpt.extract_intent(message)
#     intent = intent_data.get("intent")
#     language = intent_data.get("language")
#     confidence = intent_data.get("confidence")
#     print("Intent data time check:", intent_data)
#     LeadService().create_lead(
#         whatsapp_user_id=user_id,
#         query_text=message,
#         intent=intent
#     )

#     # ---- Fallback ----
#     if intent_data.get("fallback_required", False):
#         if intent != "brand_support_check":
#             return gpt.get_fallback_menu(language)

#     if intent in JSON_ONLY_INTENTS:
#     # ---- Generate structured response for data intents only ----
#         structured = gpt.generate_structured_request(message, intent)

#         # ---- Structured extraction ----
#         entities = intent_data.get("entities", {})
#         # print("Initial entities extracted:", entities)

#         # If no entities found yet, try GPT extraction
#         if not entities:
#             # structured = gpt.generate_structured_request(message, intent)
#             if structured.get("needs_more_info", False):
#                 if intent=="chassis_number":
#                     return "Please provide a valid chassis number to proceed."
#                 return gpt.get_fallback_menu(language)
#             entities = structured.get("entities", {})

#         # ---- Part Number Logic ----
#         if intent == "part_number":
#             part_numbers = entities.get("part_numbers") or []

#             # fallback legacy single pn
#             if not part_numbers:
#                 pn = entities.get("part_number")
#                 if pn:
#                     part_numbers = [pn]

#             if not part_numbers:
#                 print("No part numbers found in message.YOUR CAUSE")
#                 return gpt.get_fallback_menu(language)

#             results_by_pn = {}

#             for pn in part_numbers:
#                 pn_clean = pn.strip().upper()
#                 parts = (
#                     db.session.query(Stock)
#                     .filter(func.upper(Stock.brand_part_no) == pn_clean)
#                     .limit(10)
#                     .all()
#                 )

#                 results_by_pn[pn_clean] = [
#                     {
#                         "name": p.item_desc,
#                         "part_number": p.brand_part_no,
#                         "brand": p.brand,
#                         "price": float(p.price) if p.price else None,
#                         "qty": p.qty
#                     }
#                     for p in parts
#                 ]

#             # No matches at all
#             if all(len(v) == 0 for v in results_by_pn.values()):
#                 return gpt.format_response([], intent, language)

#             # Multiple PNs
#             if len(part_numbers) > 1:
#                 return gpt.format_multi_part_response(results_by_pn, language)

#             # Single PN
#             only = results_by_pn[part_numbers[0].strip().upper()]
#             return gpt.format_response(only, intent, language)
#         if intent == "chassis_number":
#             chassis_number = entities.get("chassis")
#             if not chassis_number:
#                 print("No chassis number found in message.")
#                 return gpt.get_fallback_menu(language)
#             print("Chassis number found:", chassis_number)
#             if len(chassis_number) == 17:
#                 #Go to remote APP and fetch details
#                 return "Thank you for providing your *chassis number*.\nWe will get back to you in few minutes with the details.✅"
#             return "Please provide a valid chassis number (17 characters)."
#         print("YOU ARE HERE")
#         # ---- Default fallback ----
#         return gpt.get_fallback_menu(language)
#     # if intent in REPLY_ONLY_INTENTS:
#     reply1 = gpt.generate_plain_response(message, intent)

#     if not reply1:
#         print("No reply generated for reply-only intent.")
#         return gpt.get_fallback_menu(language)

#     reply = gpt.translation_service.translate(reply1, language)
#         # print(reply)
#     return reply

from app.extensions import db
from app.models import Stock,User  # Ensure User is imported if you enable saving VINs
from app.services.gpt_service import GPTService
from app.services.lead_service import LeadService
from app.services.car_catelouge import BMWPartsFinder  # Importing our new service
from sqlalchemy import func
import re
 
def process_user_message(user_id: str, message: str) -> str:
    print("PROCESS USER MESSAGE STARTED")
    gpt = GPTService()
   
    JSON_ONLY_INTENTS = {
        "part_number_handling_strict_matching",
        "vin_handling"
    }
 
    # ---- 1. Intent Classification ----
    intent_data = gpt.extract_intent(message)
    intent = intent_data.get("intent")
    language = intent_data.get("language")
    print("Intent data time check:", intent)
    # Save lead
    LeadService().create_lead(
        whatsapp_user_id=user_id,
        query_text=message,
        intent=intent
    )
 
    # ---- 2. Fallback for Low Confidence ----
    if intent_data.get("fallback_required", False):
        if intent != "brand_support_check":
            return gpt.get_fallback_menu(language)
 
    # ---- 3. Handle Data Intents ----
    if intent in JSON_ONLY_INTENTS:
        structured = gpt.generate_structured_request(message, intent)
        # print("Structured data:", structured)
        entities = structured.get("entities", {})

 
        # Safety check for entities
        if not entities:
            if structured.get("needs_more_info", False):
                if intent == "chassis_number":
                    return "Please provide a valid chassis number to proceed."
                return gpt.get_fallback_menu(language)
            entities = structured.get("entities", {})
 
        # ======================================================
        #  LOGIC 1: PART NUMBER (User gave explicit part code)
        # ======================================================
        if intent == "part_number_handling_strict_matching":
            part_numbers = entities.get("part_numbers") or []
            if not part_numbers and entities.get("part_number"):
                part_numbers = [entities.get("part_number")]
 
            if not part_numbers:
                # If intent is part_number but no numbers found, ignore here
                pass
            else:
                results_by_pn = {}
                for pn in part_numbers:
                    pn_clean = pn.strip().upper()
                   
                    # Query Remote DB
                    parts = (
                        db.session.query(Stock)
                        .filter(func.upper(Stock.brand_part_no) == pn_clean)
                        .limit(10)
                        .all()
                    )
                   
                    results_by_pn[pn_clean] = [
                        {
                            "name": p.item_desc,
                            "part_number": p.brand_part_no,
                            "brand": p.brand,
                            "price": float(p.price) if p.price else None,
                            "qty": p.qty
                        }
                        for p in parts
                    ]
 
                if all(len(v) == 0 for v in results_by_pn.values()):
                    return gpt.format_response([], intent, language)
 
                if len(part_numbers) > 1:
                    return gpt.format_multi_part_response(results_by_pn, language)
 
                only = results_by_pn[part_numbers[0].strip().upper()]
                return gpt.format_response(only, intent, language)
 
        # ======================================================
        #  LOGIC 2: CHASSIS NUMBER (Handling the Flow)
        # ======================================================
        if intent == "vin_handling":
            chassis_number = entities.get("chassis")
           
            if not chassis_number or len(chassis_number) != 17:
                return "Please provide a valid 17-digit chassis number."
            FILLER_WORDS = (
                r'hi|hello|please|price|cost|need|bmw|parts|part|for|'
                r'give|me|want|search|find|my|our|your|i|we|us|'
                r'and|also|with|without|about|'
                r'chassis|chasis|vin|number|numer|is|this'
            )


            # Clean message to remove the VIN and filler words
            # Remove VIN
            clean_msg = re.sub(re.escape(chassis_number), '', message, flags=re.IGNORECASE)

            # Remove filler words
            clean_msg = re.sub(rf'(?i)\b({FILLER_WORDS})\b', '', clean_msg)

            # Remove punctuation
            clean_msg = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_msg)

            # Normalize spaces
            clean_msg = re.sub(r'\s+', ' ', clean_msg).strip()

            # Decision string
            clean_check = re.sub(r'[^a-zA-Z0-9]', '', clean_msg)
            print(f"DEBUG: Message='{message}' | Clean='{clean_msg}' | Check='{clean_check}'")
 
            # print(f"DEBUG: Message: '{message}' | Cleaned: '{clean_msg}' | CheckStr: '{clean_check}'")
 
            # --- SCENARIO A: User sent ONLY VIN ---
            # Now we check the length of 'clean_check', which is purely letters/numbers
           # 🚗 User provided ONLY chassis number (no part name)
            if not clean_check:
                print(f"DEBUG: Saving chassis number {chassis_number} for User {user_id}")

                user = db.session.query(User).filter_by(whatsapp_id=user_id).first()
                if not user:
                    user = User(whatsapp_id=user_id)
                    db.session.add(user)

                user.current_vin = chassis_number
                db.session.commit()

                print(f"DEBUG: Saved VIN {chassis_number} for User {user_id}")

                return (
                    "Thank you! I've saved your chassis number 🚗.\n\n"
                    "You can now ask for parts by name, e.g.,\n"
                    "**Price for Oil Filter**"
                )

            # --- SCENARIO B: User sent VIN + Part ("Price for Oil Filter for WBA...") ---
            part_name = clean_msg.strip()
            print(f"DEBUG: Searching for '{part_name}' with VIN {chassis_number}")
 
            # 1. Search Catalog
            finder = BMWPartsFinder()
            search_result = finder.search_part(chassis_number, part_name)
            print("Search result:", search_result)
            if "error" in search_result:
                return "I found the vehicle, but I couldn't find that specific category in the catalog. Please try a different name."
 
            # 2. Get OEM Numbers
            found_oem_numbers = search_result.get('oem_numbers', [])
           
            # 3. Query Remote DB
            stock_parts = (
                db.session.query(Stock)
                .filter(Stock.brand_part_no.in_(found_oem_numbers))
                .all()
            )
           
            if not stock_parts:
                return f"I found the part ({search_result['diagram']}), but currently we don't have it in stock."
 
            # 4. Return Results
            formatted_data = [
                {"name": p.item_desc, "part_number": p.brand_part_no, "brand": p.brand, "price": float(p.price) if p.price else None, "qty": p.qty}
                for p in stock_parts
            ]
            return gpt.format_response(formatted_data, "part_number", language)
 
    # ---- 4. Reply Only Intents (Greetings, etc.) ----
    reply1 = gpt.generate_plain_response(message, intent)
    if not reply1:
        return gpt.get_fallback_menu(language)
 
    reply = gpt.translation_service.translate(reply1, language)
    return reply