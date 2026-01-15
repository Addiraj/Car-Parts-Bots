from urllib import response
from app.models import IntentPrompt
from flask import current_app
from openai import OpenAI
import base64
import json

def run_image_intent(intent_key: str, img_bytes: bytes, content_type: str) -> dict:
    prompt = IntentPrompt.query.filter_by(
        intent_key=intent_key,
        intent_type="image",
        is_active=True
    ).first()
    if intent_key == "unknown" or not prompt:
        return {
            "message": "Our Team is working to support this image type. Please try again later."
        }
    

    client = OpenAI(api_key=current_app.config["OPENAI_API_KEY"])
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

    img_b64 = base64.b64encode(img_bytes).decode()
    mime = content_type or "image/jpeg"

    SYSTEM_WRAPPER = """
        You are an automotive image analysis assistant.

        IMPORTANT OUTPUT RULES (MANDATORY):
        - Respond in STRICT JSON only
        - Use EXACTLY this schema:

        {
        "message": "<final response for the user>"
        }

        - Do NOT add extra keys
        - Do NOT add explanations outside JSON
        - If the reference contains multiple sections,
        - ALL sections MUST appear in the output.
        - Omitting any section is INVALID.


        SOURCE-LOCK RULE (STRICT)

        For each section:
        - Use ONLY sentences or bullet points that already exist in the reference document
        - Do NOT paraphrase
        - Do NOT summarize
        - Do NOT simplify
        - Do NOT replace wording with your own

        You may:
        - Remove emojis
        - Remove formatting symbols
        - Split long sentences into bullet points ONLY if wording stays the same

        If exact wording is not possible, copy the closest sentence from the reference without changing meaning.


    """

    reference_block = prompt.reference_text 
    # system_prompt = f"""
    # {SYSTEM_WRAPPER}
    # REFERENCE:
    # {reference_block}
    # TASK:
    # {prompt.prompt_text}
    # """

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=3000,
        messages = [
            {
                "role": "system",
                "content": SYSTEM_WRAPPER
            },
            {
                "role": "system",
                "content": f"""
                REFERENCE (USE ALL SECTIONS EXACTLY AS PROVIDED):
                {reference_block}

                RULES (MANDATORY):
                - Use ONLY information from the reference
                - Include ALL sections present in the reference
                - Preserve section order
                - Do NOT summarize or omit sections
                - Do NOT add new information
                """
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt.prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{img_b64}"
                        }
                    }
                ]
            }
        ]

    )
    raw = response.choices[0].message.content.strip()

    # ✅ STEP 1: remove ```json fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1]).strip()

    # ✅ STEP 2: parse clean JSON
    try:
        data = json.loads(raw)
        return {
            "message": data.get("message", "").strip()
        }
    except Exception:
        # last-resort fallback: return clean text ONLY
        return {
            "message": raw.replace("```", "").strip()
        }


