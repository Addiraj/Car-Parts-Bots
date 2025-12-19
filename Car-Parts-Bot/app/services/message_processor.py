from app.extensions import db
from app.models import Stock
from app.services.gpt_service import GPTService
from app.services.lead_service import LeadService
from sqlalchemy import func
import requests
def process_user_message(user_id: str, message: str) -> str:
    print("OUTBOUND IP:", requests.get("https://api.ipify.org").text)
 
    print("PROCESS USER MESSAGE STARTED")
    gpt = GPTService()
    # REPLY_ONLY_INTENTS = {
    #     "greeting",
    #     "slang_abuse",
    #     "brand_support_check",
    #     "missing_required_details",
    #     "workshop_recommendation",
    #     "goodbye",
    #     "vehicle_behaviour"
    # }
    JSON_ONLY_INTENTS = {
        "part_number",
        "chassis_number"
    }

    # ---- Intent classification ----
    # intent_data = gpt.extract_intent(message)
    # print("Intent data time check:", intent_data)
    # intent = intent_data.get("intent")
    # language = intent_data.get("language")
    # confidence = intent_data.get("confidence")

    # # Save lead
    # LeadService().create_lead(
    #     whatsapp_user_id=user_id,
    #     query_text=message,
    #     intent=intent
    # )
    # print("Fallback check:", intent_data)

    # # ---- Fallback ----
    # if intent_data.get("fallback_required", False):
    #     print("Fallback required due to low confidence or unclear intent")
    #     return gpt.get_fallback_menu(language)
    
    # print(f"Detected intent: {intent} (confidence: {confidence})")
    # # ---- Greeting ----
    # if intent == "greeting":
    #     structured = gpt.generate_structured_request(message, intent)
    #     return structured.get("message", "Hello! How can I assist you?")

    # # ---- Abuse / Slang ----
    # if intent == "slang_abuse":
    #     structured = gpt.generate_structured_request(message, intent)
    #     reply = structured.get("message", "I understand you're upset.")
    #     reply = gpt.translation_service.translate(reply, language)
    #     return reply + "\n\n" + gpt.get_fallback_menu(language)
    # # ---- Thanks ----
    intent_data = gpt.extract_intent(message)
    intent = intent_data.get("intent")
    language = intent_data.get("language")
    confidence = intent_data.get("confidence")
    print("Intent data time check:", intent_data)
    LeadService().create_lead(
        whatsapp_user_id=user_id,
        query_text=message,
        intent=intent
    )

    # ---- Fallback ----
    if intent_data.get("fallback_required", False):
        if intent != "brand_support_check":
            return gpt.get_fallback_menu(language)


    # # ---- Generate structured response ONCE ----
    # structured = gpt.generate_structured_request(message, intent)

    # reply = structured.get("message")

    # # ---- Reply-only intents exit here ----
    # if intent in REPLY_ONLY_INTENTS:
    #     if not reply:
    #         print("No reply generated for reply-only intent.")
    #         return gpt.get_fallback_menu(language)
    #     print("Reply-only intent reply:", reply,language)
    #     reply = gpt.translation_service.translate(reply, language)
    #     return reply
    # ---- Reply-only intents MUST exit BEFORE structured logic ----
    
    if intent in JSON_ONLY_INTENTS:
    # ---- Generate structured response for data intents only ----
        structured = gpt.generate_structured_request(message, intent)

        # ---- Structured extraction ----
        entities = intent_data.get("entities", {})
        # print("Initial entities extracted:", entities)

        # If no entities found yet, try GPT extraction
        if not entities:
            # structured = gpt.generate_structured_request(message, intent)
            if structured.get("needs_more_info", False):
                if intent=="chassis_number":
                    return "Please provide a valid chassis number to proceed."
                return gpt.get_fallback_menu(language)
            entities = structured.get("entities", {})

        # ---- Part Number Logic ----
        if intent == "part_number":
            part_numbers = entities.get("part_numbers") or []

            # fallback legacy single pn
            if not part_numbers:
                pn = entities.get("part_number")
                if pn:
                    part_numbers = [pn]

            if not part_numbers:
                print("No part numbers found in message.YOUR CAUSE")
                return gpt.get_fallback_menu(language)

            results_by_pn = {}

            for pn in part_numbers:
                pn_clean = pn.strip().upper()
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

            # No matches at all
            if all(len(v) == 0 for v in results_by_pn.values()):
                return gpt.format_response([], intent, language)

            # Multiple PNs
            if len(part_numbers) > 1:
                return gpt.format_multi_part_response(results_by_pn, language)

            # Single PN
            only = results_by_pn[part_numbers[0].strip().upper()]
            return gpt.format_response(only, intent, language)
        if intent == "chassis_number":
            chassis_number = entities.get("chassis")
            if not chassis_number:
                print("No chassis number found in message.")
                return gpt.get_fallback_menu(language)
            print("Chassis number found:", chassis_number)
            if len(chassis_number) == 17:
                #Go to remote APP and fetch details
                return "Thank you for providing your *chassis number*.\nWe will get back to you in few minutes with the details.✅"
            return "Please provide a valid chassis number (17 characters)."
        print("YOU ARE HERE")
        # ---- Default fallback ----
        return gpt.get_fallback_menu(language)
    # if intent in REPLY_ONLY_INTENTS:
    reply1 = gpt.generate_plain_response(message, intent)

    if not reply1:
        print("No reply generated for reply-only intent.")
        return gpt.get_fallback_menu(language)

    reply = gpt.translation_service.translate(reply1, language)
        # print(reply)
    return reply

