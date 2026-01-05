# services/image_intent_router.py

import base64
import json
from typing import Literal
from flask import current_app
from openai import OpenAI


# ImageIntent = Literal["vin_plate", "dashboard_warning", "unknown"]

ImageIntent = Literal["vin_plate", "dashboard_warning", "headlight_part", "unknown"]


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

    # resp = client.chat.completions.create(
    #     model=model,
    #     temperature=0,
    #     max_tokens=50,
    #     messages=[
    #         {
    #             "role": "system",
    #             "content": (
    #                 "You are an image classifier for automotive support.\n"
    #                 "Classify the image ONLY.\n"
    #                 "Return strict JSON."
    #             ),
    #         },
    #         {
    #             "role": "user",
    #             "content": [
    #                 {
    #                     "type": "text",
    #                     "text": (
    #                         "Classify this image into ONE category:\n"
    #                         "- vin_plate (VIN/chassis number label)\n"
    #                         "- dashboard_warning (dashboard warning light icon)\n"
    #                         "- unknown\n\n"
    #                         "Return JSON:\n"
    #                         "{ \"type\": \"vin_plate|dashboard_warning|unknown\" }"
    #                     ),
    #                 },
    #                 {
    #                     "type": "image_url",
    #                     "image_url": {
    #                         "url": f"data:{mime};base64,{image_b64}"
    #                     },
    #                 },
    #             ],
    #         },
    #     ],
    # )
    resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=50,
            messages=[
                {
                    "role": "system",
                    "content": (
                        """You are a strict image intent classifier for an automotive support system.

                        Your task is to classify the image based on visible visual characteristics ONLY.

                        Use these visual rules:

                        - vin_plate:
                        An image containing printed or stamped alphanumeric text used as a vehicle identification number,
                        usually on a metal plate or sticker.

                        - dashboard_warning:
                        An image showing a flat dashboard warning or indicator symbol,
                        typically an icon, light, or pictogram on a vehicle instrument cluster.

                        - headlight_part:
                        An image showing a physical vehicle headlight or headlamp assembly,
                        including lenses, reflectors, LED strips, projector bowls, or housing.
                        These images are photographic, three-dimensional, and not flat icons.

                        - unknown:
                        Anything that does not clearly match the above categories.

                        Do NOT identify vehicle brand, model, or year.
                        Do NOT explain your reasoning.

                        Return STRICT JSON only."""
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                """Classify the image into ONE category ONLY.
                                Return JSON strictly in this format:
                                { "type": "vin_plate | dashboard_warning | headlight_part | unknown" }"""

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
