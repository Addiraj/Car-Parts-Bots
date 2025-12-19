import hmac
import json
import hashlib
from typing import Any
from flask import Blueprint, current_app, jsonify, request
import requests
from ..extensions import db
from ..models import Lead,Stock
from ..services.gpt_service import GPTService
# from ..services.chassis_service import ChassisService
from ..services.lead_service import LeadService
# from ..services.carparts_dubai_service import CarPartsDubaiService
from sqlalchemy import or_, and_
from ..redis_client import redis_client
import json
from datetime import datetime
from sqlalchemy import func
from ..tasks import task_queue, process_whatsapp_message
from ..services.media_service import download_whatsapp_media as _download_media
whatsapp_bp = Blueprint("whatsapp", __name__)

@whatsapp_bp.get("")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    # print("VERIFY TOKEN FROM CONFIG:", current_app.config.get("META_VERIFY_TOKEN"))

    if mode == "subscribe" and token == current_app.config.get("META_VERIFY_TOKEN"):
        return challenge, 200
    return "Forbidden", 403


@whatsapp_bp.post("")
def receive_message():
    payload: dict[str, Any] = request.get_json(silent=True) or {}
    entries = payload.get("entry", [])

    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Block status webhooks
            if "statuses" in value:
                continue

            messages = value.get("messages", [])
            if not messages:
                continue

            bot_number = value.get("metadata", {}).get("display_phone_number")
            contacts = value.get("contacts", [])
            user_id = contacts[0]["wa_id"] if contacts else None

            for msg in messages:

                msg_id = msg.get("id")
                if msg_id:
                    cache_key = f"whatsapp_msg:{msg_id}"
                    if redis_client.exists(cache_key):
                        print("⏭ Skip duplicate:", msg_id)
                        continue
                    redis_client.setex(cache_key, 172800, "processed")

                if msg.get("from") == bot_number:
                    print("Skip bot msg")
                    continue

                msg_type = msg.get("type")

                if msg_type == "text":
                    text = msg["text"]["body"].strip().upper()

                    redis_client.publish(
                        "chatbot_events",
                        json.dumps({
                            "type": "user_message",
                            "from": user_id,
                            "text": text
                        })
                    )
                    # print("process whatsapp text message in background task",process_whatsapp_message(user_id, text, "text"))
                    # 🚀 ENQUEUE JOB IN BACKGROUND
                    task_queue.enqueue(process_whatsapp_message, user_id, text, "text")


                elif msg_type == "image":
                    img_media_id = msg["image"]["id"]

                    redis_client.publish(
                        "chatbot_events",
                        json.dumps({
                            "type": "user_image",
                            "from": user_id,
                            "media_id": img_media_id
                        })
                    )

                    # 🚀 Enqueue job to process chassis + GPT reply
                    task_queue.enqueue(process_whatsapp_message, user_id, img_media_id, "image")


                elif msg_type == "audio":
                    media_id = msg["audio"]["id"]

                    redis_client.publish(
                        "chatbot_events",
                        json.dumps({
                            "type": "user_audio",
                            "from": user_id,
                            "media_id": media_id
                        })
                    )

                    # 🚀 Send to worker for transcription + GPT + reply
                    task_queue.enqueue(process_whatsapp_message, user_id, media_id, "audio")


    # ALWAYS only one final response
    return jsonify({"status": "ok"}), 200


# @whatsapp_bp.post("")
# def receive_message():
#     payload: dict[str, Any] = request.get_json(silent=True) or {}
#     # print("request from webhook", payload)
#     entries = payload.get("entry", [])
#     for entry in entries:
#         for change in entry.get("changes", []):
#             value = change.get("value", {})

#             # 🔥🔥 BLOCK STATUS WEBHOOKS (delivery/read/sent) to stop infinite loops
#             if "statuses" in value:
#                 return jsonify({"status": "ignored"}), 200

#             messages = value.get("messages", [])

#              # 🔥 Ignore non-message webhooks (e.g. presence, typing indicators)
#             if not messages:
#                 return jsonify({"status": "ignored"}), 200

#             bot_number = value.get("metadata", {}).get("display_phone_number", None)
#             # print(bot_number)
#             contacts = value.get("contacts", [])
#             user_id = contacts[0]["wa_id"] if contacts else None
#             redis_client.publish(
#                 "chatbot_events",
#                 json.dumps({
#                     "type": "user_message",
#                     "from": user_id,
#                     "text": messages[0].get("text", {}).get("body", "")
#                 })
#             )

#             for msg in messages:
#                 # 🔥🔥 DEDUPLICATION: Skip if message already processed
#                 msg_id = msg.get("id")
#                 if msg_id and redis_client:
#                     cache_key = f"whatsapp_msg:{msg_id}"
#                     if redis_client.exists(cache_key):
#                         print(f"⏭️  Skipping duplicate message: {msg_id}")
#                         continue
#                     # Mark as processed for 172800 seconds (prevent duplicates from retries)
#                     redis_client.setex(cache_key, 172800, "processed") # 48 hours
                
#                 if msg.get("from") == bot_number:
#                     print("Skipping bot-sent message")
#                     return jsonify({"status": "ignored"}), 200
#                 text = None
#                 media_url = None

#                 if msg.get("type") == "text":
#                     text = msg["text"]["body"]
#                     text=text.strip().upper()

#                 elif msg.get("type") == "image":
#                     img_media_id = msg["image"]["id"]

#                     from ..services.media_service import process_image_media

#                     chassis_number = process_image_media(img_media_id)

#                     if chassis_number:
#                         reply = f"Detected chassis number: {chassis_number}"
#                     else:
#                         reply = "Sorry, I could not detect any chassis/VIN in the image."
#                     print("🚗 Detected Chassis Number:", chassis_number)
#                     _send_whatsapp_text(user_id, reply)
#                     return jsonify({"status": "ok"})

#                 elif msg.get("type") == "audio":
#                     media_id = msg["audio"]["id"]
#                     media_url = _get_media_url(media_id)

#                     from ..services.media_service import download_whatsapp_media
#                     audio_bytes = download_whatsapp_media(media_url)

#                     # 1. Transcribe with language detection
#                     from ..services.whisper_service import transcribe_audio, clean_voice_text

#                     raw_text, user_lang = transcribe_audio(audio_bytes)  # <-- FIXED
#                     print("RAW:", raw_text, "LANG:", user_lang)

#                     # 2. Clean text + english version for processing
#                     cleaned_json = clean_voice_text(raw_text, user_lang)
#                     parsed = json.loads(cleaned_json)

#                     english_text = parsed["english"]
#                     native_text = parsed["native"]


#                     # 3. Process backend logic always in English
#                     response_text = _process_user_message(user_id, english_text)

#                     # 4. Reply in user's language
#                     if user_lang == "en":
#                         final_reply = response_text
#                     else:
#                         # no translation needed, GPT already produced "native"
#                         final_reply = GPTService().translation_service.translate(response_text, user_lang)

#                     _send_whatsapp_text(user_id, final_reply)
#                     return jsonify({"status": "ok"})

#                 if user_id and text:
#                     # Process message with GPT and search
#                     response_text = _process_user_message(user_id, text)

#                     # Send response
#                     _send_whatsapp_text(user_id, response_text)
#                     return jsonify({"status": "ok"})
#     return jsonify({"status": "ok"})


# def _process_user_message(user_id: str, message: str) -> str:
#         print("PROCESS USER MESSAGE STARTED")
#         gpt = GPTService()

#         # STEP 1 — Intent Classification (GPT #1)
#         intent_data = gpt.extract_intent(message)
#         # print("Intent extracted---->",intent_data)
#         intent = intent_data["intent"]
#         confidence = intent_data.get("confidence", 0.0)
#         language = intent_data.get("language")
#         # 🔥 Save LEAD only ONCE here
#         LeadService().create_lead(
#             whatsapp_user_id=user_id,
#             query_text=message,
#             intent=intent
#         )

#         # Fallback menu trigger
#         if intent_data["fallback_required"]:
#             return gpt.get_fallback_menu(language)
        
#         # Force English for structured searches only
#         if intent in ["part_number", "chassis_number"]:
#             pass
#         # Handle greeting intent with GPT #2
#         if intent == "greeting":
#             structured = gpt.generate_structured_request(message, intent)
#             return structured.get("message", "Hello! How can I assist you?")
#         # Slang / abusive intent: calm message + redirect
#         if intent == "slang_abuse":
#             structured = gpt.generate_structured_request(message, intent)
#             reply = structured.get("message", "I understand you're upset.")

#             # Translate calming message into user's language
#             reply = gpt.translation_service.translate(reply, language)

#             return reply + "\n\n" + gpt.get_fallback_menu(language)

#         # STEP 2 — Structured Entity Extraction (GPT #2)
#         structured = gpt.generate_structured_request(message, intent)
#         if structured.get("needs_more_info", True):
#             return gpt.get_fallback_menu(language)

#         entities = structured.get("entities", {})

#         if intent == "part_number":
#             part_numbers = entities.get("part_numbers", [])
#             print("Extracted Part Numbers:", part_numbers)

#             # fallback for legacy prompt
#             if not part_numbers:
#                 single_pn = entities.get("part_number")
#                 if single_pn:
#                     part_numbers = [single_pn]
                    
#             # Ensure list has values
#             if not part_numbers:
#                 print("⚠ No part numbers extracted")
#                 return gpt.get_fallback_menu(language)

#             # 🔥 DB Search FIRST for all PNs
#             results_by_pn = {}
#             for pn in part_numbers:
#                 pn_clean = pn.strip().upper()
#                 parts = (
#                     db.session.query(Stock)
#                     .filter(func.upper(Stock.brand_part_no) == pn_clean)
#                     .limit(10)
#                     .all()
#                 )

#                 results_by_pn[pn] = [_serialize_part(p) for p in parts]


#             # 🔥 No matches for any PN
#             if all(len(lst) == 0 for lst in results_by_pn.values()):
#                 return gpt.format_response([], intent, language)

#             # If multiple PNs → use grouped formatter
#             if len(part_numbers) > 1:
#                 print("Multi part response")
#                 return gpt.format_multi_part_response(results_by_pn, language)

#             # Single PN → extract its list & format normally
#             print("Single part response")
#             only_results = results_by_pn[part_numbers[0]]
#             print("FROM WEBHOOK-->",language)
#             return gpt.format_response(only_results, intent, language)

# def _serialize_part(p):
#     return {
#         "name": p.item_desc,    # GPT uses "name", so map item_desc to name
#         "part_number": p.brand_part_no,
#         "brand": p.brand,
#         "price": float(p.price) if p.price is not None else None,
#         "qty": p.qty
#     }


# def _send_whatsapp_text(wa_id: str, text: str) -> None:

#     token = current_app.config.get("META_ACCESS_TOKEN")
#     phone_id = current_app.config.get("META_PHONE_NUMBER_ID")
#     if not token or not phone_id:
#         return

#     url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json",
#     }
#     data = {
#         "messaging_product": "whatsapp",
#         "to": wa_id,
#         "type": "text",
#         "text": {"body": text},
#     }
#     try:
#         redis_client.publish(
#             "chatbot_events",
#             json.dumps({
#                 "type": "reply",
#                 "to": wa_id,
#                 "text": text
#             })
#         )
#         print("Sending WhatsApp message to", wa_id)
#         requests.post(url, headers=headers, json=data, timeout=10)
#     except Exception:
#         pass

# def _get_media_url(media_id):
#     token = current_app.config.get("META_ACCESS_TOKEN")
#     resp = requests.get(
#         f"https://graph.facebook.com/v18.0/{media_id}",
#         headers={"Authorization": f"Bearer {token}"}
#     )
#     data = resp.json()
#     return data.get("url")



# import hmac
# import json
# import hashlib
# from typing import Any
# from flask import Blueprint, current_app, jsonify, request
# import requests
# from ..extensions import db
# from ..models import Lead, Stock
# from ..services.gpt_service import GPTService
# # from ..services.chassis_service import ChassisService
# from ..services.lead_service import LeadService
# # from ..services.carparts_dubai_service import CarPartsDubaiService
# from sqlalchemy import or_, and_
# from ..redis_client import redis_client
# from datetime import datetime
# import threading  # 👈 for background processing

# from ..services.media_service import download_whatsapp_media as _download_media

# whatsapp_bp = Blueprint("whatsapp", __name__)


# # -----------------------------
# # Optional: Verify Meta Signature (HMAC)
# # -----------------------------
# def _verify_meta_signature(raw_body: bytes) -> bool:
#     app_secret = current_app.config.get("META_APP_SECRET")
#     if not app_secret:
#         # If not configured, skip verification
#         return True

#     signature = request.headers.get("X-Hub-Signature-256")
#     if not signature or "=" not in signature:
#         return False

#     try:
#         algo, received_sig = signature.split("=", 1)
#     except ValueError:
#         return False

#     if algo != "sha256":
#         return False

#     expected_sig = hmac.new(
#         app_secret.encode("utf-8"),
#         msg=raw_body,
#         digestmod=hashlib.sha256
#     ).hexdigest()

#     return hmac.compare_digest(expected_sig, received_sig)


# @whatsapp_bp.get("")
# def verify_webhook():
#     mode = request.args.get("hub.mode")
#     token = request.args.get("hub.verify_token")
#     challenge = request.args.get("hub.challenge")

#     if mode == "subscribe" and token == current_app.config.get("META_VERIFY_TOKEN"):
#         return challenge, 200
#     return "Forbidden", 403


# @whatsapp_bp.post("")
# def receive_message():
#     raw_body = request.get_data(cache=False, as_text=False)

#     if not _verify_meta_signature(raw_body):
#         return jsonify({"status": "invalid_signature"}), 403

#     payload: dict[str, Any] = json.loads(raw_body or b"{}")

#     # ⚡ Capture REAL app object before thread starts
#     app = current_app._get_current_object()

#     threading.Thread(
#         target=_handle_whatsapp_payload_thread,
#         args=(app, payload),
#         daemon=True
#     ).start()

#     # Respond immediately so WhatsApp DOES NOT RETRY
#     return jsonify({"status": "ok"}), 200


# def _handle_whatsapp_payload_thread(app, payload):
#     with app.app_context():
#         _handle_whatsapp_payload(payload)


# def _handle_whatsapp_payload(payload: dict[str, Any]) -> None:
#     """Process incoming WhatsApp payload in background."""
#     entries = payload.get("entry", [])
#     for entry in entries:
#         for change in entry.get("changes", []):
#             value = change.get("value", {})
#             messages = value.get("messages", [])
#             contacts = value.get("contacts", [])
#             user_id = contacts[0]["wa_id"] if contacts else None

#             if not user_id:
#                 continue

#             for msg in messages:
#                 msg_id = msg.get("id")
#                 if not msg_id:
#                     continue

#                 # 🔒 Idempotency: skip duplicates using Redis
#                 try:
#                     cache_key = f"wa_msg:{msg_id}"
#                     if redis_client.get(cache_key):
#                         print(f"⚠️ Duplicate WhatsApp message ignored: {msg_id}")
#                         continue
#                     # Mark processed for 5 minutes
#                     redis_client.setex(cache_key, 300, "processed")
#                 except Exception as e:
#                     # If Redis is misconfigured, log but don't crash
#                     print(f"Redis error (dedupe failed): {e}")

#                 msg_type = msg.get("type")
#                 text = None

#                 # -----------------------------
#                 # TEXT MESSAGE
#                 # -----------------------------
#                 if msg_type == "text":
#                     text = msg["text"]["body"]
#                     if text:
#                         response_text = _process_user_message(user_id, text)
#                         _send_whatsapp_text(user_id, response_text)
#                     continue  # next message

#                 # -----------------------------
#                 # IMAGE MESSAGE (chassis detection)
#                 # -----------------------------
#                 if msg_type == "image":
#                     img_media_id = msg["image"]["id"]

#                     from ..services.media_service import process_image_media

#                     chassis_number = process_image_media(img_media_id)

#                     if chassis_number:
#                         reply = f"Detected chassis number: {chassis_number}"
#                     else:
#                         reply = "Sorry, I could not detect any chassis/VIN in the image."
#                     print("🚗 Detected Chassis Number:", chassis_number)
#                     _send_whatsapp_text(user_id, reply)
#                     continue  # next message

#                     # img_media_url = _get_media_url(media_id)
#                     # image_bytes = _download_media(media_url)

#                     # ------------------------------------
#                     # KEEPING YOUR COMMENTED OUT CODE
#                     # ------------------------------------
#                     # elif user_id and img_media_id:
#                     #     print("📸 Image received! Downloading...")
#                     #     from ..services.vin_ocr import _download_media_blob
#                     #     result = _download_media_blob(img_media_id)
#                     #
#                     #     # 2. Run OCR
#                     #     from ..services.vin_ocr import extract_vin_from_image
#                     #     result = extract_vin_from_image(img_bytes)
#                     #     print(result)
#                     #     # 3. Extract chassis from OCR
#                     #     chassis_list = result.get("vins", [])
#                     #     chassis_number = chassis_list[0] if chassis_list else None
#                     #
#                     #     # 4. For demo: store chassis in a variable so frontend can show it
#                     #     print("====================================")
#                     #     # print("📌 OCR RESULT (RAW TEXT):")
#                     #     # print(result["text"])
#                     #     print("------------------------------------")
#                     #     print("🚗 Detected Chassis Number:")
#                     #     print(chassis_number)
#                     #     print("====================================")
#                     #
#                     #     # 5. Respond to user
#                     #     if chassis_number:
#                     #         reply = f"Detected chassis number: {chassis_number}"
#                     #     else:
#                     #         reply = "Sorry, I could not detect any chassis/VIN in the image."
#                     #
#                     #     _send_whatsapp_text(user_id, reply)
#                     #     return jsonify({"status": "ok"})

#                 # -----------------------------
#                 # AUDIO MESSAGE
#                 # -----------------------------
#                 if msg_type == "audio":
#                     media_id = msg["audio"]["id"]
#                     media_url = _get_media_url(media_id)

#                     from ..services.media_service import download_whatsapp_media
#                     audio_bytes = download_whatsapp_media(media_url)

#                     # 1. Transcribe with language detection
#                     from ..services.whisper_service import transcribe_audio, clean_voice_text

#                     raw_text, user_lang = transcribe_audio(audio_bytes)
#                     print("RAW:", raw_text, "LANG:", user_lang)

#                     # 2. Clean text + english version for processing
#                     cleaned_json = clean_voice_text(raw_text, user_lang)
#                     parsed = json.loads(cleaned_json)

#                     english_text = parsed["english"]
#                     native_text = parsed["native"]

#                     # 3. Process backend logic always in English
#                     response_text = _process_user_message(user_id, english_text)

#                     # 4. Reply in user's language
#                     if user_lang == "en":
#                         final_reply = response_text
#                     else:
#                         final_reply = GPTService().translation_service.translate(
#                             response_text, user_lang
#                         )

#                     _send_whatsapp_text(user_id, final_reply)
#                     continue  # next message

#     # Done processing all entries/messages
#     return


# def _process_user_message(user_id: str, message: str) -> str:
#     print("gpt service intialisation started")
#     gpt = GPTService()

#     # STEP 1 — Intent Classification (GPT #1)
#     intent_data = gpt.extract_intent(message)
#     print("intent extracted")
#     intent = intent_data["intent"]
#     confidence = intent_data.get("confidence", 0.0)
#     language = intent_data.get("language", "en")

#     # 🔥 Save LEAD only ONCE here
#     LeadService().create_lead(
#         whatsapp_user_id=user_id,
#         query_text=message,
#         intent=intent,
#     )

#     # Fallback menu trigger
#     if intent_data.get("fallback_required"):
#         return gpt.get_fallback_menu(language)

#     # Force English for structured searches only
#     if intent in ["part_number", "chassis_number"]:
#         print("Part number intent")
#         language = "en"

#     # Handle greeting intent with GPT #2
#     if intent == "greeting":
#         structured = gpt.generate_structured_request(message, intent)
#         print("returned greetings")
#         return structured.get("message", "Hello! How can I assist you?")

#     # Slang / abusive intent: calm message + redirect
#     if intent == "slang_abuse":
#         structured = gpt.generate_structured_request(message, intent)
#         reply = structured.get("message", "I understand you're upset.")
#         reply = gpt.translation_service.translate(reply, language)
#         return reply + "\n\n" + gpt.get_fallback_menu(language)

#     # STEP 2 — Structured Entity Extraction (GPT #2)
#     structured = gpt.generate_structured_request(message, intent)

#     if structured.get("needs_more_info", True):
#         return gpt.get_fallback_menu(language)

#     entities = structured.get("entities", {})

#     # STEP 3 — Database Search
#     search_results = []

#     if intent == "part_number":
#         print("Part number......")
#         pn = entities.get("part_number")
#         if pn:
#             parts = (
#                 db.session.query(Stock)
#                 .filter(Stock.brand_part_no.ilike(f"%{pn}%"))
#                 .limit(10)
#                 .all()
#             )
#             search_results = [_serialize_part(p) for p in parts]
#         print("Part found")

#     # elif intent == "chassis_number":
#     #     chassis = entities.get("chassis")
#     #     if chassis:
#     #         chassis_service = ChassisService()
#     #         vehicle_data = chassis_service.lookup_vehicle(chassis)
#     #
#     #         if vehicle_data:
#     #             parts = (
#     #                 db.session.query(Part)
#     #                 .join(Vehicle, Part.vehicle_id == Vehicle.id)
#     #                 .filter(Vehicle.chassis_number == vehicle_data.get("chassis_number"))
#     #                 .limit(10)
#     #                 .all()
#     #             )
#     #             search_results = [_serialize_part(p) for p in parts]

#     if not search_results:
#         return gpt.format_response([], intent, language)

#     # STEP 4 — Format Final Response (Existing GPT Formatter)
#     formatted_reply = gpt.format_response(search_results, intent, language)
#     print("formation of reply completed")
#     return formatted_reply


# def _serialize_part(p):
#     return {
#         "name": p.item_desc,      # GPT uses "name", so map item_desc to name
#         "part_number": p.brand_part_no,
#         "brand": p.brand,
#         "price": float(p.price) if p.price is not None else None,
#         "qty": p.qty,
#     }


# def _send_whatsapp_text(wa_id: str, text: str) -> None:
#     token = current_app.config.get("META_ACCESS_TOKEN")
#     phone_id = current_app.config.get("META_PHONE_NUMBER_ID")
#     if not token or not phone_id:
#         return

#     url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json",
#     }
#     data = {
#         "messaging_product": "whatsapp",
#         "to": wa_id,
#         "type": "text",
#         "text": {"body": text},
#     }
#     try:
#         print("text sent")
#         requests.post(url, headers=headers, json=data, timeout=10)
#     except Exception as e:
#         print(f"Error sending WhatsApp message: {e}")


# def _get_media_url(media_id):
#     token = current_app.config.get("META_ACCESS_TOKEN")
#     resp = requests.get(
#         f"https://graph.facebook.com/v18.0/{media_id}",
#         headers={"Authorization": f"Bearer {token}"},
#         timeout=10,
#     )
#     data = resp.json()
#     return data.get("url")
