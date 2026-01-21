"""
GPT/OpenAI service for natural language understanding and response formatting.
Handles multilingual queries and generates conversational responses.
"""

from email.mime import message
from typing import Any
from openai import OpenAI
from flask import current_app
from .translation_service import TranslationService
import json
import re
import time
from ..models import IntentPrompt  
import hashlib
from rapidfuzz import fuzz
from ..redis_client import redis_client
import hashlib
import json
from typing import Dict, List

class GPTService:
    
    def intent_cache_key(self, message: str) -> str:
        normalized = message.strip().lower()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"intent:v2:{digest}"

    @staticmethod
    def get_fallback_menu(user_language: str = "en") -> str:
        translator = TranslationService()

        base_message = (
                "*CarParts AI Support*🚀\n\n"
                "We assist with *auto spare parts* for:\n"
                "• BMW\n"
                "• Mercedes-Benz\n"
                "• Rolls-Royce\n"
                "• Mini Cooper\n"
                "• Honda\n\n"
                "Please share your *VIN number* or *part number*, and I’ll help you further.😊"
            )


        # Force English if language is invalid or empty
        if not user_language or user_language.lower().startswith("en"):
            return base_message

        # Translate ONLY the plain text (safe)
        return translator.from_base_language(base_message, user_language)
    """Service for GPT-based natural language understanding and response generation."""

    # Class-level metrics (in-memory, no database)
    total_intent_checks = 0
    correct_intent_predictions = 0
    incorrect_intent_predictions = 0
    response_times = []  # Store last 100 latencies only

    def __init__(self):
        self.client = None
        api_key = current_app.config.get("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
        self.translation_service = TranslationService()


    def extract_intent(self, user_message: str) -> dict[str, Any]:
        print( "EXTRACT INTENT CALLED")
        """
        Extract intent using DB-driven dynamic GPT classification.
        Fallback → "unknown" if low confidence or unsupported intent.
        """

        clean_text =user_message.strip()

        # ✅ Build cache key ONCE, correctly
        cache_key = self.intent_cache_key(clean_text)

        # 🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨
        print("Deleting cache key:", cache_key)
        redis_client.delete(cache_key)

        # 1. Check Redis cache
        cached = redis_client.get(cache_key)
        if cached:
            print("🚀 Cache hit for intent extraction", cached)
            return json.loads(cached)

        print("NOT A CACHE")

        SUPPORTED_BRANDS = {
            "bmw",
            "mercedes",
            "mercedes-benz",
            "benz",
            "rolls royce",
            "mini cooper",
            "honda",
        }

        def normalize_text(text: str) -> str:
            text = text.lower()
            text = re.sub(r"[^a-z0-9\s]", " ", text)  # remove symbols
            text = re.sub(r"\s+", " ", text).strip()
            return text

        def detect_brand(text: str, brands: set[str], threshold: int = 80) -> str | None:
            text = text.lower()

            for brand in brands:
                score = fuzz.token_set_ratio(brand, text)
                if score >= threshold:
                    return brand

            return None
        
        # text = normalize_text(user_message.lower())
        # detected_brand = detect_brand(text, SUPPORTED_BRANDS)
        # brand_detected = detected_brand is not None
        # print("BRAND DETECTED:", detected_brand)
        # if brand_detected:
        #     return {
        #         "intent": "brand_support_check",
        #         "entities": {},
        #         "language": "en",
        #         "confidence": 0.95,
        #         "fallback_required": False
        #     }
        # clean_upper = clean_text.upper()

        # ---------- VIN FAST PATH ----------
        # VIN_REGEX = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
        # lines = [l.strip() for l in clean_text.splitlines() if l.strip()]

        # for line in lines:
        #     if VIN_REGEX.fullmatch(line.upper()):
        #         print("FAST PATH VIN MATCH")
        #         result = {
        #             "intent": "vin_handling",
        #             "entities": {},
        #             "language": "en",
        #             "confidence": 0.9,
        #             "fallback_required": False
        #         }
        #         redis_client.setex(cache_key, 3600, json.dumps(result))
        #         return result

        # 2. Fast Path: Regex for Part Numbers
        # If it looks like a part number usage (mostly alphanumeric, dashes, short), skip GPT
        # Pattern: 4 to 20 chars, alphanumeric/dashes, no spaces or few spaces
        PART_NUMBER_REGEX = re.compile(
            r"^[A-Z0-9]{2,}[A-Z0-9\-\.]{1,}$"
        )
        if (PART_NUMBER_REGEX.fullmatch(clean_text.upper()) and sum(c.isdigit() for c in clean_text) >= 2 and " " not in clean_text.strip()):
             print("FAST PATH PART NUMBER MATCH")
             result = {
                 "intent": "part_number_handling",
                 "entities": {"part_numbers": [clean_text.upper()], "part_number": clean_text.upper()}, 
                 "language": "en", # Assume EN for codes
                 "confidence": 1.0,
                 "fallback_required": False
             }
             redis_client.setex(cache_key, 3600, json.dumps(result))
             print("Fast path part number detected:", clean_text)
             return result

        if not self.client:
            print("GPT client not configured, using fallback intent extraction.")
            return {"intent": "unknown", "entities": {}, "language": "en"}

        # Fetch allowed intents dynamically from DB
        # active_prompts = IntentPrompt.query.filter_by(is_active=True).all()
        active_prompts = (
            IntentPrompt.query
            .filter_by(is_active=True, intent_type="text")
            .all()
        )
        intent_keys = [row.intent_key for row in active_prompts]
        if not intent_keys:
            current_app.logger.error("No active intents found in DB!")
            return {"intent": "unknown", "entities": {}, "language": "en"}
        # Build dynamic summary text for GPT
        intent_list_text = "\n".join([f"- {key}" for key in intent_keys])
        print("checking from DB intents:")
        system_prompt = f"""
                    You are an intent classification model for a car parts assistant.

                    You are given a list of valid intents from the database.
                    Each intent has a key and a description.

                    Your job:
                    - Read the user's message.
                    - Infer the user's intent based on meaning, tone, and context.
                    - Choose the single BEST matching intent key from the list.
                    - Do NOT invent new intents.
                    - If nothing matches clearly, return "unknown".

                    Valid intents:
                    {intent_list_text}

                    Guidelines:
                    - Use semantic understanding, not keyword matching.
                    - Detect hostility, abuse, or anger by tone and language, even if indirect.
                    - Detect greetings by conversational intent, not just words like "hi".
                   
                    - Prefer the closest intent rather than "unknown" when the message is car-related.

                    Return a confidence score reflecting how sure you are.

                    Output STRICT JSON only:
                    {{
                    "intent": "<intent_key_or_unknown>",
                    "confidence": <number between 0 and 1>
                    }}
                    """
        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                # response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=100,
            )
            latency = time.time() - start_time
            self._record_latency(latency)

            data = json.loads(response.choices[0].message.content)
            intent = data.get("intent", "unknown")
            confidence = float(data.get("confidence", 0.0))
            clean_text = user_message.replace("\n", " ").replace("\r", " ").strip()
            # language = self.translation_service.detect_language(user_message) or "en"
            language = self.translation_service.detect_language(clean_text) or "en"
            print("DETEECTED LANGUAGE😕",language)
            # Check fallback conditions
            fallback_required = False
            if intent not in intent_keys:  # GPT hallucinated new intent
                fallback_required = True
            elif intent == "unknown":  # nonsense or abusive
                fallback_required = True
            elif confidence < 0.60:  # weak prediction? skip it
                fallback_required = True

            result = {
                "intent": intent,
                "entities": {},
                "language": language,
                "confidence": confidence,
                "fallback_required": fallback_required,
            }
            # print(result)
            # 3. Cache Result (1 hour)
            if intent != "unknown":
                 redis_client.setex(cache_key, 3600, json.dumps(result))
            
            return result

        except Exception as e:
            current_app.logger.warning(f"Dynamic intent extraction failed: {e}")
            return {"intent": "unknown", "entities": {}, "language": "en", "confidence": 0.0}


    def generate_plain_response(self, user_message: str, intent_key: str) -> str:
        """
        Generate a plain-text response for reply-only intents.
        NO JSON. NO entity extraction.
        """
        if not self.client:
            return ""

        # Fetch intent prompt from DB
        row = IntentPrompt.query.filter_by(
            intent_key=intent_key,
            is_active=True
        ).first()

        if not row or not row.prompt_text:
            return ""

        system_prompt = row.prompt_text
        print("TIME FOR GPT")
        try:
            response = self.client.chat.completions.create(
                model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=3000,
            )

            reply = response.choices[0].message.content
            return reply.strip() if reply else ""

        except Exception as e:
            current_app.logger.warning(f"Plain response generation failed: {e}")
            return ""

    def run_system_prompt(
        self,
        prompt_text: str,
        user_text: str,
        temperature: float = 0.0,
        max_tokens: int = 3000
    ) -> str:
        """
        Runs a strict system prompt with a user message.
        Returns raw assistant content (string).
        """

        response = self.client.chat.completions.create(
            model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "system",
                    "content": prompt_text
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        )

        return response.choices[0].message.content.strip()
    
    def extract_part_name_with_gpt(self, message: str) -> str | None:
        prompt = IntentPrompt.query.filter_by(
            intent_key="normalize_part_name",
            intent_type="text",
            is_active=True
        ).first()
        PART_NAME_EXTRACTION_PROMPT = prompt.prompt_text

        raw = self.run_system_prompt(
            prompt_text=PART_NAME_EXTRACTION_PROMPT,
            user_text=message,
            temperature=0
        )

        try:
            data = json.loads(raw)
            return data.get("part_name")
        except Exception:
            return None

    def generate_structured_request(self, user_message: str, intent_key: str) -> dict:
        """
        Uses DB-stored prompt to extract required structured data (entities).
        If missing required fields → GPT creates question for user.
        """
        clean_text = user_message.replace("\n", " ").replace("\r", " ").strip()
        print("DETEECTED CLEAN TEXT",clean_text)
        # language = self.translation_service.detect_language(user_message) or "en"
        language = self.translation_service.detect_language(clean_text) or "en"
        if not self.client:
            return {"needs_more_info": True, "message": "Please provide part number or chassis number."}

        # Fetch intent prompt from DB
        row = IntentPrompt.query.filter_by(intent_key=intent_key, is_active=True).first()
        if not row:
            print("DETEECTED LANGUAGE")
            return {"needs_more_info": True, "message": self.get_fallback_menu(language)}

        system_prompt = row.prompt_text
        # detect_text = self.normalize_for_detection(user_message)
        # print("DETEECTED text",detect_text)
        try:
            response = self.client.chat.completions.create(
            model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": clean_text}],
                },
            ],
            temperature=0.0,
            max_tokens=3000,
        )
            data = json.loads(response.choices[0].message.content)
            print("Structured data extracted:", data)
            return data

        except Exception as e:
            print("exception")
            current_app.logger.warning(f"GPT structured extraction failed: {e}")
            return {"needs_more_info": True, "message": self.get_fallback_menu(language)}

    def format_response(
        self,
        search_results: Dict[str, List[dict]],
        intent: str,
        language: str = "en",
        is_multi_input: bool = False,
        vehicle_info: Dict[str, str] = None,
    ) -> str:
        """
        Format search results into a natural language WhatsApp-style response.
        Handles both single and multi part-number inputs.
        """

        if not self.client:
            return self._fallback_response(search_results, language)

        model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

        # ----------------------------
        # Build results text (STRICT)
        # ----------------------------
        # ✅ Correct empty check
        if not search_results:
            results_text = "No parts found matching your query."
        else:
            results_text = ""

            for tag, items in search_results.items():
                if not items:
                    continue  # skip empty groups safely

                results_text += f"\n🔹 {tag}\n"

                for r in items:
                    results_text += f"• *Item:* {r.get('name', 'N/A')}\n"
                    if r.get("brand"):
                        results_text += f"• *Brand:* {r.get('brand')}\n"
                    if r.get("price") is not None:
                        results_text += f"• *Price:* {r.get('price')} AED\n"
                    results_text += "\n"
        # ----------------------------
        # Helper line based on input
        # ----------------------------
        if is_multi_input:
            helper_line = (
                "Here are the compatible parts found across the part numbers you provided."
            )
        else:
            helper_line = "Here are the available parts for your request."

        # ----------------------------
        # Vehicle Info Block
        # ----------------------------
        vehicle_block = ""
        if vehicle_info:
            vehicle_block = (
                f"**Brand:** {vehicle_info.get('brand', 'N/A')}\n"
                f"**Name:** {vehicle_info.get('name', 'N/A')}\n"
                f"**Year:** {vehicle_info.get('date', 'N/A')}\n"
            )

        # ----------------------------
        # User prompt
        # ----------------------------
        user_prompt = f"""
            You are formatting car part search results into a professional, conversational WhatsApp-style message.

            🚨 NON-NEGOTIABLE RULES ABOUT LANGUAGE 🚨
            - Respond ONLY in this language: {language}
            - Translate ONLY:
            ✔ Greetings
            ✔ Explanations
            ✔ UI labels (e.g. "Item", "Brand", "Price")
            - DO NOT translate database fields:
            ✖ Product names
            ✖ Brand names
            ✖ Part numbers
            ✖ Price values
            - Product details MUST remain EXACTLY as given in the input text, including uppercase.

            🚨 VERY IMPORTANT
            - Product descriptions are NOT normal sentences.
            - NEVER modify, rewrite, localize, or translate:
            product names, brand names, part numbers, or prices.
            - You may translate labels ONLY.

            Formatting rules:
            - WhatsApp-friendly
            - Use bullet points
            - Use *bold* (single asterisk) for labels ONLY
            - No markdown like **bold**
            - Clean line breaks
            - Max 1–2 emojis

            ---

            Vehicle Information (if present, show exactly as is):
            {vehicle_block}

            Database results (DO NOT MODIFY):

            {results_text}

            ---

            Response structure:
            1️⃣ Friendly greeting in {language}
            Vehicle Details Block (ONLY IF PROVIDED ABOVE):
            **Brand:** ...
            **Name:** ...
            **Year:** ...
            (Use double asterisks for bolding headers in this specific block if requested)
            2️⃣ Short helper line (translated): "{helper_line}"
            3️⃣ Database Results (Preserve Grouping):
               - If a line starts with 🔹, keep it EXACTLY as is (do not translate or remove).
               - Then list items for that group:
               • *Item:* <EXACT Product Name>
               • *Brand:* <EXACT Brand Name>
               • *Price:* <EXACT Price Value>
            5️⃣ Closing sentence (translated):
            "If you need any help, I’m here to help you 😊"
            """

        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a multilingual WhatsApp car parts assistant. "
                            "Follow EXACTLY the rules in the user message. "
                            "Translate ONLY UI text. "
                            "DO NOT translate product names, brand names, part numbers, or prices. "
                            f"User language must be: {language}."
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.6,
                max_tokens=3000,
            )

            self._record_latency(time.time() - start_time)
            return response.choices[0].message.content.strip()

        except Exception as e:
            current_app.logger.warning(
                f"GPT response formatting failed: {e}, using fallback"
            )
            return self._fallback_response(search_results, language)


    def format_multi_part_response(self, results_by_pn: dict, language: str = "en") -> str:
        """
        Format grouped results for multiple part numbers in one WhatsApp message.
        """
        response = "Hello! 😊 Here are the car parts you requested:\n\n"

        for pn, items in results_by_pn.items():
            response += f"🔹 *{pn}*\n"
            
            if not items:
                response += "  - ❌ Not found\n\n"
                continue
            
            for p in items:
                name = p.get("name", "N/A")
                brand = p.get("brand", "N/A")
                price = p.get("price", "N/A")
                qty = p.get("qty", "N/A")

                response += f"  - *{name}* | {brand} | {price} AED | Qty: {qty}\n"

            response += "\n"

        response += "Would you like to see more details about any of these parts? 🚗✨"

        if language != "en":
            response = self.translation_service.from_base_language(response, language)

        return response.strip()

    def _fallback_multi_response(self, results_by_pn, language="en"):
        response = "Here are the results:\n\n"
        
        for pn, items in results_by_pn.items():
            response += f"🔹 *{pn}*\n"
            if not items:
                response += "❌ Not found\n\n"
            else:
                for p in items:
                    response += f"- *{p['name']}* | {p['brand']} | {p['price']} AED | Qty: {p['qty']}\n"
                response += "\n"
        return response.strip()

    def _fallback_intent(self, message: str) -> dict[str, Any]:
        """Fallback intent extraction without GPT."""
        clean_text = message.replace("\n", " ").replace("\r", " ").strip()

            # language = self.translation_service.detect_language(user_message) or "en"
        language = self.translation_service.detect_language(clean_text) or "en"
        message_lower = message.lower()

        # Simple keyword-based intent detection
        if any(word in message_lower for word in ["hello", "hi", "hey", "مرحبا"]):
            return {"intent": "greeting", "entities": {}, "language": language or "en"}

        # Check for part number pattern (alphanumeric, often with dashes)
        if re.search(r"\b[A-Z0-9\-]{4,}\b", message.upper()):
            return {"intent": "part_number_handling", "entities": {}, "language": language or "en"}

        # Check for chassis/VIN pattern
        if "chassis" in message_lower or "vin" in message_lower:
            return {"intent": "chassis", "entities": {}, "language": language or "en"}

        # Assume car + part query
        return {"intent": "car_part", "entities": {}, "language": language or "en"}

    def _fallback_response(self, results: list[dict], language: str) -> str:
        """Fallback response formatting without GPT."""
        base_language = language or "en"
        if not results:
            fallback = "Sorry, we couldn't find any parts matching your query. Please try again with different keywords."
            return self._translate_if_needed(fallback, base_language)

        msg = f"Found {len(results)} part(s):\n\n"
        for r in results[:5]:
            msg += f"{r.get('name', 'N/A')} - Part #{r.get('part_number', 'N/A')}"
            if r.get("price"):
                msg += f" | Price: {r.get('price')} AED"
            if r.get("brand"):
                msg += f" | Brand: {r.get('brand')}"
            msg += "\n"

        if len(results) > 5:
            msg += f"\n... and {len(results) - 5} more. Please contact us for details."

        return self._translate_if_needed(msg, base_language)

    def _translate_if_needed(self, text: str, target_language: str) -> str:
        if not target_language or target_language.lower().startswith("en"):
            return text
        return self.translation_service.translate(text, target_language)

    def _record_latency(self, latency: float) -> None:
        """Record GPT API latency (keep last 100 only)."""
        GPTService.response_times.append(latency)
        if len(GPTService.response_times) > 100:
            GPTService.response_times.pop(0)

    def _is_intent_correct(self, intent: str, results: list[dict]) -> bool:
        """
        Improved accuracy rules:
        - greeting → always correct
        - part_number → correct ONLY if parts found (DB or external)
        - chassis → correct ONLY if parts/vehicle found (results non-empty)
        - car_part → correct ONLY if search returned any matching parts
        - unknown → always incorrect
        """
        if intent == "greeting":
            return True

        if intent in ("part_number", "car_part", "chassis"):
            return bool(results) and len(results) > 0

        return False
    
    def record_intent_accuracy(self, intent: str, search_results: list[dict]):
        GPTService.total_intent_checks += 1

        if self._is_intent_correct(intent, search_results):
            GPTService.correct_intent_predictions += 1
        else:
            GPTService.incorrect_intent_predictions += 1


    def generate_greeting(self, language: str = "en") -> str:
        """Generate greeting in user's language using GPT, fallback to translation."""
        if not self.client:
            english_greeting = "Hello! How can I help you find car parts today?"
            return self._translate_if_needed(english_greeting, language)

        model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": f"You are a helpful car parts assistant. Respond in {language} language."},
                    {"role": "user", "content": f"Generate a friendly greeting for a car parts customer. Language: {language}"}
                ],
                temperature=0.7,
                max_tokens=3000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            current_app.logger.warning(f"GPT greeting failed: {e}, using translation")
            english_greeting = "Hello! How can I help you find car parts today?"
            return self._translate_if_needed(english_greeting, language)

    def generate_error_message(self, error_type: str, language: str = "en") -> str:
        """Generate error message in user's language using GPT, fallback to translation."""
        errors = {
            "chassis_not_found": "Sorry, we couldn't find vehicle information for this chassis number. Please verify the number and try again.",
            "no_parts_found": "Sorry, we couldn't find any parts matching your query. Please try again with different keywords.",
            "general_error": "Sorry, we encountered an error. Please try again later."
        }
        
        english_message = errors.get(error_type, errors["general_error"])
        
        if not self.client:
            return self._translate_if_needed(english_message, language)

        model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": f"You are a helpful car parts assistant. Respond in {language} language."},
                    {"role": "user", "content": f"Translate to {language}: {english_message}"}
                ],
                temperature=0.3,
                max_tokens=3000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            current_app.logger.warning(f"GPT error message failed: {e}, using translation")
            return self._translate_if_needed(english_message, language)
