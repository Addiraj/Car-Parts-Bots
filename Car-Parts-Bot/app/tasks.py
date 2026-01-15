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
from .services.media_service import process_image_media, download_whatsapp_media
from .services.whisper_service import transcribe_audio, clean_voice_text
from .services.media_utils import get_media_url
from .services.intent_formater import img_format_response
# from app import create_app

# _app = create_app()
# _app.app_context().push()
# ✅ DO NOT PING REDIS HERE
task_queue = Queue("whatsapp", connection=redis_client)


def process_whatsapp_message(user_id, content, msg_type="text"):
    # ---- TEXT ----
    if msg_type == "text":
        reply = process_user_message(user_id, content)
        return send_whatsapp_text(user_id, reply)

    # ---- IMAGE ----
    if msg_type == "image":
        result = process_image_media(content)
        # print(result['message'])
        friendly_reply = img_format_response(result)
        return send_whatsapp_text(user_id, friendly_reply)


    # ---- AUDIO ----
    if msg_type == "audio":
        url = get_media_url(content)
        audio_bytes = download_whatsapp_media(url)

        raw_text, user_lang = transcribe_audio(audio_bytes)
        parsed = json.loads(clean_voice_text(raw_text, user_lang))
        english_text = parsed["english"]

        reply = process_user_message(user_id, english_text)

        final = (
            reply
            if user_lang == "en"
            else GPTService().translation_service.translate(reply, user_lang)
        )

        return send_whatsapp_text(user_id, final)
