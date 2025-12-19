# warning_light_formatter.py

from typing import Dict, Any


def format_warning_response(result: Dict[str, Any]) -> str:
    """
    Convert detected warning light data into a clear user-facing message.
    """
    if result.get("detected") in (None, "unknown"):
        return (
            "⚠️ I can see a dashboard warning light, but I can’t confidently identify it.\n\n"
            "Please send a clearer photo (focused, no glare) or share your car model."
        )

    explanation = result.get("explanation")
    if not explanation:
        return "⚠️ Warning light detected, but no explanation is available."

    return (
        f"🚨 **{explanation['name']}**\n\n"
        f"**Severity:** {explanation['severity']}\n\n"
        f"**What it means:**\n{explanation['meaning']}\n\n"
        f"**What you should do now:**\n"
        + "\n".join(f"• {step}" for step in explanation["what_to_do"])+ "\n\n"
        f"Would you like me to recommend a reliable workshop in **Sharjah**?"
    )
