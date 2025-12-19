from .redis_client import redis_client
from rq import Queue
from .services.gpt_service import GPTService
from .services.lead_service import LeadService
from .extensions import db
from .models import Stock
from sqlalchemy import func
import json
import requests
from .services.message_processor import process_user_message
from .services.whatsapp_sender import send_whatsapp_text
from .services.media_service import process_image_media,download_whatsapp_media
from .services.whisper_service import transcribe_audio, clean_voice_text
from .services.media_utils import get_media_url
redis_client.ping()

task_queue = Queue("whatsapp", connection=redis_client)

def process_whatsapp_message(user_id, content, msg_type="text"):
    
    # TEXT
    if msg_type == "text":
        reply = process_user_message(user_id, content)
        print(reply)
        result = send_whatsapp_text(user_id, reply)
        print("sending wa text", result)
        return result

    # IMAGE
    # if msg_type == "image":
        
    #     img_media_id = content
    #     chassis = process_image_media(img_media_id)
    #     reply = f"Thank you for the VIN. kindly wait for 5 minutes to get details." if chassis else "Sorry, unable to detect a VIN"
    #     return send_whatsapp_text(user_id, reply)
    if msg_type == "image":
        result = process_image_media(content)

        if result["type"] == "vin":
            reply = (
                "✅ VIN detected. Please wait while I fetch vehicle details."
                if result["value"]
                else "❌ I couldn’t detect a VIN. Please send a clearer image."
            )
            return send_whatsapp_text(user_id, reply)

        if result["type"] == "warning_light":
            return send_whatsapp_text(user_id, result["message"])

        return send_whatsapp_text(user_id, result["message"])


    # AUDIO
    if msg_type == "audio":
        
        media_id = content
        url = get_media_url(media_id)
        audio_bytes = download_whatsapp_media(url)

        raw_text, user_lang = transcribe_audio(audio_bytes)
        parsed = json.loads(clean_voice_text(raw_text, user_lang))
        english_text = parsed["english"]
        print("english_text", english_text)
        reply = process_user_message(user_id, english_text)
        final = reply if user_lang == "en" else GPTService().translation_service.translate(reply, user_lang)

        return send_whatsapp_text(user_id, final)
