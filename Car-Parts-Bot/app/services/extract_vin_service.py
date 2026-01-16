import re
from typing import Optional

VIN_REGEX = re.compile(
    r"\b[A-HJ-NPR-Z0-9]{17}\b",
    re.IGNORECASE
)

def extract_vin_from_text(text: str) -> Optional[str]:
    """
    Extract a valid 17-character VIN from text.
    Returns VIN if found, else None.
    """
    if not text:
        return None

    match = VIN_REGEX.search(text.upper())
    return match.group(0) if match else None
