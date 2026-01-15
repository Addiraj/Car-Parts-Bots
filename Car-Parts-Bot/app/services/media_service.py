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

from ..services.vin_ocr import download_media_blob, run_chassis_ocr
from ..services.image_intent_router import detect_image_intent
from ..services.warning_light_gpt import run_warning_light_gpt, format_warning_gpt
from ..services.image_intent_executor import run_image_intent
# NEW imports for headlight handling
from ..services.headlight_vision import analyze_headlight_image
from ..services.headlight_formatter import format_headlight_response


def process_image_media(media_id: str) -> dict:
    try:
        # 1️⃣ Download image
        content, content_type = download_media_blob(media_id)
        print("✅ Downloaded media:", media_id, "Type:", content_type)
        # 2️⃣ Detect image intent
        intent_key = detect_image_intent(content, content_type)

        # # 3️⃣ Route to correct pipeline
        # if intent_key == "vin_plate":
        #     ocr_result = run_chassis_ocr(content, content_type)
        #     return {
        #         "type": "vin",
        #         "value": ocr_result.get("chassis"),
        #     }
        print("🔍 Detected image intent:", intent_key)
         # 4️⃣ All other image intents → DB driven
        result = run_image_intent(intent_key, content, content_type)
        print(result.get("message"))

        # Ensure consistent output
        return {
            "intent": intent_key,
            "message": result.get("message", "Image processed.")
        }

    except Exception as exc:
        print("❌ Image processing failed:", exc)
        return {
            "intent": "No intent Found",
            "message": "Image processing failed. Please try again."
        }