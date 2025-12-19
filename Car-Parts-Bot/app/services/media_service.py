import requests
from flask import current_app

def download_whatsapp_media(url: str) -> bytes:
    token = current_app.config["META_ACCESS_TOKEN"]

    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    # print(resp.content)
    return resp.content

# from ..services.vin_ocr import run_chassis_ocr  # We'll define this below
from ..services.vin_ocr import download_media_blob
from ..services.image_intent_router import detect_image_intent
from ..services.vin_ocr import run_chassis_ocr
# from ..services.warning_light_vision import run_warning_light_vision
from ..services.warning_light_formatter import format_warning_response
from ..services.warning_light_gpt import run_warning_light_gpt
from ..services.warning_light_gpt import format_warning_gpt


def process_image_media(media_id: str) -> dict:
    try:
        # 1️⃣ Download image
        content, content_type = download_media_blob(media_id)

        # 2️⃣ Detect image intent
        intent = detect_image_intent(content, content_type)

        # 3️⃣ Route to correct pipeline
        if intent == "vin_plate":
            ocr_result = run_chassis_ocr(content, content_type)
            return {
                "type": "vin",
                "value": ocr_result.get("chassis"),
            }

        if intent == "dashboard_warning":
            data = run_warning_light_gpt(content, content_type)
            message = format_warning_gpt(data)
            return {
                "type": "warning_light",
                "message": message,
            }

        return {
            "type": "unknown",
            "message": "I couldn’t identify what this image contains. Please send a VIN plate or dashboard warning light."
        }

    except Exception as exc:
        print("❌ Image processing failed:", exc)
        return {
            "type": "error",
            "message": "Image processing failed. Please try again."
        }
