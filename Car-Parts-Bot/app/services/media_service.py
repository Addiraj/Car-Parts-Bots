import requests
from flask import current_app
from ..services.vin_ocr import download_media_blob, run_chassis_ocr
from ..services.image_intent_router import detect_image_intent
from ..services.extract_vin_service import extract_vin_from_text
from ..services.image_intent_executor import run_image_intent
from app.services.scraper.partsouq_xpath_scraper import get_scraper
from app.session_store import get_session, save_session
import time

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


def process_image_media(user_id,media_id: str) -> dict:
    try:
        # 1️⃣ Download image
        content, content_type = download_media_blob(media_id)
        print("✅ Downloaded media:", media_id, "Type:", content_type)
        # 2️⃣ Detect image intent
        intent_key = detect_image_intent(content, content_type)

        print("🔍 Detected image intent:", intent_key)
         # 4️⃣ All other image intents → DB driven
        result = run_image_intent(intent_key, content, content_type)
        print(result.get("message"))
        message = result.get("message", "")

        # 4️⃣ 🔥 Extract VIN from LLM message
        vin = extract_vin_from_text(message)
        print("Extracted VIN:", vin)
        if vin:
            session = get_session(user_id)
            session["entities"]["vin"] = vin
            session["context"]["vin_set_at"] = time.time()
            save_session(user_id, session)
            scraper = get_scraper()
            if scraper is None:
                return "SCRAPER NOT ACCESSIBLE"
            vehicle_info = scraper.get_vehicle_details(vin)

            if vehicle_info:
                # 3. Format the Response
                return (
                    f"🚗 **Vehicle Identified!**\n"
                    f"**Brand:** {vehicle_info.get('brand', 'N/A')}\n"
                    f"**Name:** {vehicle_info.get('name', 'N/A')}\n"
                    f"**Year:** {vehicle_info.get('date', 'N/A')}\n\n"
                    f"I've saved this chassis number. Please tell me which part you need! 🔧"
                )
            print(session)

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