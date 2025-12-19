# services/image_intent_router.py

import base64
import json
from typing import Literal
from flask import current_app
from openai import OpenAI


ImageIntent = Literal["vin_plate", "dashboard_warning", "unknown"]


def detect_image_intent(img_bytes: bytes, content_type: str) -> ImageIntent:
    """
    Decide what the image contains:
    - VIN plate / chassis number
    - Dashboard warning light
    """
    client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"])
    model = current_app.config.get("OPENAI_MODEL") or "gpt-4o-mini"

    image_b64 = base64.b64encode(img_bytes).decode()
    mime = content_type or "image/jpeg"

    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=50,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an image classifier for automotive support.\n"
                    "Classify the image ONLY.\n"
                    "Return strict JSON."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Classify this image into ONE category:\n"
                            "- vin_plate (VIN/chassis number label)\n"
                            "- dashboard_warning (dashboard warning light icon)\n"
                            "- unknown\n\n"
                            "Return JSON:\n"
                            "{ \"type\": \"vin_plate|dashboard_warning|unknown\" }"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{image_b64}"
                        },
                    },
                ],
            },
        ],
    )

    payload = resp.choices[0].message.content.strip()

    try:
        if payload.startswith("```"):
            payload = "\n".join(payload.splitlines()[1:-1])
        data = json.loads(payload)
        return data.get("type", "unknown")
    except Exception:
        return "unknown"
