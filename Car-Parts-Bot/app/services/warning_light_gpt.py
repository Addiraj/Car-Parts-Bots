# warning_light_vision.py

import base64
import json
from typing import Dict, Any
from flask import current_app
from openai import OpenAI

from .warning_light_knowledge import WARNING_LIGHTS


# warning_light_vision.py
SYSTEM_PROMPT = """
You are an automotive dashboard warning light expert.

You understand:
- Dashboard warning symbols across major car brands
- Color-based urgency:
  Red = critical, stop immediately
  Yellow/Amber = caution, inspect soon
  Green/White = informational
  Blue = indicator
- Real driving safety risks and mechanical consequences

Rules:
- Be conservative and safety-first
- Never invent facts
- If uncertain, say so clearly
- Prefer stopping the vehicle when risk is high
"""



def run_warning_light_gpt(img_bytes: bytes, content_type: str) -> dict:
    client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"])
    model = "gpt-4o"  # Correct model for vision reasoning

    image_b64 = base64.b64encode(img_bytes).decode()
    mime = content_type or "image/jpeg"

    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        max_tokens=500,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze this dashboard warning light image.\n\n"
                            "Identify:\n"
                            "- warning symbol name\n"
                            "- color and urgency\n"
                            "- what it means (simple language)\n"
                            "- possible causes\n"
                            "- what actions the driver should take now\n"
                            "- whether it is safe to continue driving\n\n"
                            "Return STRICT JSON only:\n"
                            "{\n"
                            "  \"symbol_name\": \"string\",\n"
                            "  \"color\": \"red|yellow|green|blue|white|unknown\",\n"
                            "  \"severity\": \"critical|high|medium|low|info\",\n"
                            "  \"meaning\": \"string\",\n"
                            "  \"possible_causes\": [\"...\"],\n"
                            "  \"recommended_actions\": [\"...\"],\n"
                            "  \"can_continue_driving\": true|false,\n"
                            "  \"confidence\": 0.0\n"
                            "}"
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

    payload = response.choices[0].message.content.strip()

    if payload.startswith("```"):
        payload = "\n".join(payload.splitlines()[1:-1])

    return json.loads(payload)

def format_warning_gpt(data: dict) -> str:
    return (
        f"🚨 *{data['symbol_name']}*\n\n"
        f"*Severity:* {data['severity'].upper()}\n"
        f"*Color:* {data['color']}\n\n"
        f"*What it means:*\n{data['meaning']}\n\n"
        f"*Possible causes:*\n"
        + "\n".join(f"• {c}" for c in data["possible_causes"])
        + "\n\n*What you should do now:*\n"
        + "\n".join(f"• {a}" for a in data["recommended_actions"])
        + (
            "\n\n✅ Safe to continue driving (with caution).\n\nWould you like me to recommend a reliable workshop in *Sharjah*?\n\n"
            "Reply *Give me workshop recommendations* and I’ll share nearby service center options."
            if data["can_continue_driving"]
            else "\n\n🛑 *Do NOT continue driving.*\n\n"
            "Would you like me to recommend a reliable workshop in *Sharjah*?\n\n"
            "Reply *Give me workshop recommendations* and I’ll share nearby service center options."
        )
    )

# def _safe_parse(payload: str) -> Dict[str, Any]:
#     try:
#         if payload.startswith("```"):
#             payload = "\n".join(payload.splitlines()[1:-1])
#         return json.loads(payload)
#     except Exception:
#         return {"type": "unknown", "confidence": 0.4}
