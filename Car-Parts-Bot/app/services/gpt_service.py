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

    # @staticmethod
    # def get_fallback_menu(user_language: str = "en") -> str:
    #     """Build a multilingual fallback menu dynamically based on DB intents."""

    #     # from ..services.translation_service import TranslationService
    #     translator = TranslationService()

    #     # Fetch active intent prompts
    #     active_prompts = IntentPrompt.query.filter_by(is_active=True).all()

    #     # Hide non-search intents like greeting
    #     excluded = {"greeting", "slang_abuse"}
    #     keys = [p.intent_key for p in active_prompts if p.intent_key not in excluded]

    #     if not keys:
    #         base_menu = "How can I assist you today?"
    #         return translator.translate(base_menu, user_language) if user_language != "en" else base_menu

    #     # Convert database intent keys into display-friendly labels
    #     def pretty_label(key: str) -> str:
    #         return key.replace("_", " ").capitalize()

    #     # Build English menu first
    #     lines = ["I can help you with:"]
    #     for i, key in enumerate(keys, start=1):
    #         lines.append(f"🔵 Can you provide me {pretty_label(key)} ?")

    #     menu = "\n".join(lines)

    #     # If language is English → skip translation
    #     if not user_language or user_language.lower().startswith("en"):
    #         return menu

    #     # Translate full menu to user's language
    #     return translator.translate(menu, user_language)

    """Service for GPT-based natural language understanding and response generation."""

    # Class-level metrics (in-memory, no database)
    total_intent_checks = 0
    correct_intent_predictions = 0
    incorrect_intent_predictions = 0
    response_times = []  # Store last 100 latencies only

    # def __init__(self):
    #     self.client = None
    #     api_key = current_app.config.get("OPENAI_API_KEY")
    #     if api_key:
    #         self.client = OpenAI(api_key=api_key)
    #     self.translation_service = TranslationService()
    
    # gpt_service.py
    def __init__(self, api_key, translation_service=None):
        self.api_key = api_key
        self.translation_service = translation_service

    def extract_intent(self, user_message: str) -> dict[str, Any]:
        print( "EXTRACT INTENT CALLED")
        """
        Extract intent using DB-driven dynamic GPT classification.
        Fallback → "unknown" if low confidence or unsupported intent.
        """
        from ..redis_client import redis_client
        import hashlib
        import json

        clean_text = user_message.strip()

        # ✅ Build cache key ONCE, correctly
        cache_key = self.intent_cache_key(clean_text)

        # 🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨
        # print("Deleting cache key:", cache_key)
        # redis_client.delete(cache_key)

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
        
        text = normalize_text(user_message.lower())
        detected_brand = detect_brand(text, SUPPORTED_BRANDS)
        brand_detected = detected_brand is not None
        print("BRAND DETECTED:", brand_detected)
        if brand_detected:
            return {
                "intent": "brand_support_check",
                "entities": {},
                "language": "en",
                "confidence": 0.95,
                "fallback_required": False
            }
        # 2. Fast Path: Regex for Part Numbers
        # If it looks like a part number usage (mostly alphanumeric, dashes, short), skip GPT
        # Pattern: 4 to 20 chars, alphanumeric/dashes, no spaces or few spaces
        if re.fullmatch(r"^[A-Z0-9\-\s/]{3,25}$", clean_text.upper()) and any(c.isdigit() for c in clean_text):
             # Highly likely a part number
             result = {
                 "intent": "part_number",
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
        active_prompts = IntentPrompt.query.filter_by(is_active=True).all()
        intent_keys = [row.intent_key for row in active_prompts]
        if not intent_keys:
            current_app.logger.error("No active intents found in DB!")
            return {"intent": "unknown", "entities": {}, "language": "en"}
        # Build dynamic summary text for GPT
        intent_list_text = "\n".join([f"- {key}" for key in intent_keys])

        # system_prompt = f"""
        #     You are an intent classifier for a car parts assistant.

        #     Allowed Intents:
        #     {intent_list_text}

        #     Classification Rules (EXTREMELY IMPORTANT):
        #     - If the message consists ONLY of part numbers or looks like one or more part codes,
        #     ALWAYS classify as "part_number".
        #     - Part numbers may contain letters, digits, spaces, dashes, or slashes.
        #     Examples that MUST be classified as part_number:
        #         "2 5 11 1083"
        #         "BKR6E-11"
        #         "8990 CHF"
        #         "BKR6EIX"
        #         "HDS85.00253"
        #         "DPN-1110-12.0124"
        #         "444-1401L-UE-C"
        #         "4.2604E+12"
        #         "K-1286-01-I"
        #         "21829"
        #         "MXWB-24/YDA-405-24"


        #     - Even if unsure, if the message resembles a car part code, classify intent="part_number" with lower confidence.

        #     - If message contains insults, abusive language, or anger → intent="slang_abuse".
        #     - If the message is about greetings or asking how you are → intent="greeting".
        #     - If the message is about car service questions, pricing, availability, or asking for parts but without a code → closest matching valid intent (NOT "unknown").

        #     - If message is unrelated to cars or meaningless → intent="unknown".

        #     Confidence Rules:
        #     - Strong clear match → confidence >= 0.85
        #     - If guessing but still likely → confidence 0.50–0.84
        #     - Very uncertain → confidence below 0.50

        #     Output Format (STRICT JSON ONLY):
        #     {{
        #     "intent": "<intent_key_or_unknown>",
        #     "confidence": 0.8
        #     }}
        #     """
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
                    - Detect part numbers if the message primarily consists of codes, identifiers, or part-like strings.
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

        try:
            response = self.client.chat.completions.create(
                model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=400,
            )

            reply = response.choices[0].message.content
            return reply.strip() if reply else ""

        except Exception as e:
            current_app.logger.warning(f"Plain response generation failed: {e}")
            return ""


    def generate_structured_request(self, user_message: str, intent_key: str) -> dict:
        """
        Uses DB-stored prompt to extract required structured data (entities).
        If missing required fields → GPT creates question for user.
        """
        clean_text = user_message.replace("\n", " ").replace("\r", " ").strip()

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

        try:
            response = self.client.chat.completions.create(
                model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                # response_format={"type": "json_object"},  # enforces JSON entities
                temperature=0.0,
                max_tokens=200,
            )

            data = json.loads(response.choices[0].message.content)
            print("Structured data extracted:", data)
            # Example expected output JSON:
            # {
            #   "entities": { "part_number": "90915YZZE2" },
            #   "needs_more_info": false,
            #   "message": ""
            # }

            return data

        except Exception as e:
            print("exception")
            current_app.logger.warning(f"GPT structured extraction failed: {e}")
            return {"needs_more_info": True, "message": self.get_fallback_menu(language)}

    def format_response(
        self, search_results: list[dict], intent: str, language: str = "en"
    ) -> str:
        """
        Format search results into a natural language response.
        Supports multilingual responses.
        """
        if not self.client:
            return self._fallback_response(search_results, language)

        model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

        # Build context about results
        results_text = ""
        if search_results:
            for r in search_results[:5]:  # Limit to top 5 for context
                results_text += f"- {r.get('name', 'N/A')} (Brand Part # {r.get('brand_part_no', 'N/A')})"
                if r.get("price"):
                    results_text += f" - Price: {r.get('price')} AED"
                if r.get("brand"):
                    results_text += f" - Brand: {r.get('brand')}"
                results_text += "\n"
        else:
            results_text = "No parts found matching your query."
        # print(language)
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

                🚨 VERY IMPORTANT: Product descriptions ARE NOT normal sentences.
                ABSOLUTELY DO NOT modify, rewrite, localize, or translate product names, brand names, price currency, or part numbers.
                You can add translated label names before them, but NEVER alter the product field values.

                ---

                Formatting rules:
                - Use bullet points
                - Use *bold* (single asterisk) for labels ONLY
                - Do not include markdown syntax like **bold**
                - Add clean line breaks for easy reading
                - Use minimal emojis (1 or 2 max)

                ---

                Here are the database results (DO NOT MODIFY THESE VALUES):

                {results_text}

                ---

                Response Structure:
                1️⃣ Friendly greeting in {language}
                2️⃣ Short translated helper line
                3️⃣ Bullet list for each item:
                • *Item:* <EXACT Product Name>
                • *Brand:* <EXACT Brand Name>
                • *Price:* <EXACT Price Value>
                4️⃣ Closing sentence offering images or assistance — translated
                """

        try:
            print("format response GPTSERVICE-->",language)
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a multilingual WhatsApp car parts assistant. "
                            "Follow EXACTLY the rules in the user message: "
                            "Translate ONLY UI text. "
                            "DO NOT translate product names, brand names, part numbers, or prices. "
                            
                            f"User language for UI labels and sentences must be: {language}."
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            latency = time.time() - start_time
            self._record_latency(latency)
            return response.choices[0].message.content.strip()
        except Exception as e:
            current_app.logger.warning(f"GPT response formatting failed: {e}, using fallback")
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

    # def format_multi_part_response(self, results_by_pn: dict, language: str = "en") -> str:
    #     """
    #     Format grouped results for multiple part numbers in WhatsApp-style format.
    #     Preserves exact product values. UI elements translated only.
    #     """
    #     if not self.client or not results_by_pn:
    #         return self._fallback_multi_response(results_by_pn, language)

    #     model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

    #     # Build detailed context for GPT - properly formatted
    #     context_text = ""
    #     for pn, items in results_by_pn.items():
    #         context_text += f"Part Number: {pn}\n"
            
    #         if not items:
    #             context_text += "  ❌ Not found\n\n"
    #         else:
    #             for p in items:
    #                 context_text += (
    #                     f"  Name: {p.get('name', 'N/A')}\n"
    #                     f"  Brand: {p.get('brand', 'N/A')}\n"
    #                     f"  Price: {p.get('price', 'N/A')}\n"
    #                     f"  Qty: {p.get('qty', 'N/A')}\n\n"
    #                 )

    #     user_prompt = f"""
    #                 You are formatting multiple grouped car part search results 
    #                 into a professional, conversational WhatsApp-style message.

    #                 🚨 NON-NEGOTIABLE RULES 🚨
    #                 - Respond ONLY in this language: {language}
    #                 - Translate ONLY labels and sentences
    #                 - NEVER modify product names, brands, part numbers, prices, or quantities
    #                 - Preserve capitalization EXACTLY
    #                 - Values must appear EXACTLY as provided

    #                 Formatting rules:
    #                 - Greeting + short helper line
    #                 - Group by Part Number heading
    #                 - Bullet list inside each group:
    #                     • *Item:* <EXACT name>
    #                     • *Brand:* <EXACT brand>
    #                     • *Price:* <EXACT price> AED
    #                     • *Quantity:* <EXACT qty>
    #                 - Add a blank line between groups
    #                 - Minimal emojis (1–2 total)

    #                 The results to format:
    #                 {context_text}

    #                 Final response structure:
    #                 1️⃣ Friendly greeting in {language}
    #                 2️⃣ Helper text in {language}
    #                 3️⃣ Sections labeled by part number (never translate part numbers):
    #                 - Headings with: 🔹 *<Part Number>*
    #                 - Bullets exactly formatted as specified above
    #                 4️⃣ Closing support message in {language}
    #                 """

    #     try:
    #         start_time = time.time()
    #         response = self.client.chat.completions.create(
    #             model=model,
    #             messages=[
    #                 {
    #                     "role": "system",
    #                     "content": (
    #                         "You are a multilingual WhatsApp car parts assistant. "
    #                         "Translate ONLY UI text — never database product fields. "
    #                         "Preserve exact values from database."
    #                     ),
    #                 },
    #                 {"role": "user", "content": user_prompt},
    #             ],
    #             temperature=0.6,
    #             max_tokens=650,
    #         )
    #         latency = time.time() - start_time
    #         self._record_latency(latency)
    #         return response.choices[0].message.content.strip()

    #     except Exception as e:
    #         current_app.logger.warning(f"GPT multi-format failed: {e}, using fallback")
    #         return self._fallback_multi_response(results_by_pn, language)


    # def _fallback_multi_response(self, results_by_pn: dict, language: str) -> str:
    #     """
    #     Fallback formatter for multiple part numbers when GPT is unavailable.
    #     """
    #     response = "Hello! 😊\nHere are the parts you requested:\n\n"

    #     for pn, items in results_by_pn.items():
    #         response += f"🔹 *{pn}*\n"
            
    #         if not items:
    #             response += "  ❌ Not found\n\n"
    #         else:
    #             for p in items:
    #                 response += (
    #                     f"  • *Item:* {p.get('name', 'N/A')}\n"
    #                     f"    *Brand:* {p.get('brand', 'N/A')}\n"
    #                     f"    *Price:* {p.get('price', 'N/A')} AED\n"
    #                     f"    *Quantity:* {p.get('qty', 'N/A')}\n\n"
    #                 )

    #     response += "If you need images or more details, let me know! 🚗✨"

    #     if language != "en" and self.translation_service:
    #         response = self.translation_service.translate(response, language)

    #     return response.strip()


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
            return {"intent": "part_number", "entities": {}, "language": language or "en"}

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

    # def record_intent_accuracy(self, intent: str, search_results: list[dict]) -> None:
    #     """Record intent accuracy based on search results."""
    #     GPTService.total_intent_checks += 1
    #     if self._is_intent_correct(intent, search_results):
    #         GPTService.correct_intent_predictions += 1

    # def _is_intent_correct(self, intent: str, results: list[dict]) -> bool:
    #     """
    #     Simple accuracy rule:
    #     - if intent is 'part_number' and results exist → correct
    #     - if intent is 'chassis' and VIN/chassis detected → correct
    #     - greeting is always correct
    #     - else incorrect
    #     """
    #     if intent == "greeting":
    #         return True
    #     if intent == "part_number" and len(results) > 0:
    #         return True
    #     if intent == "chassis" and intent == "chassis":
    #         return True
    #     return False
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
                max_tokens=100,
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
                max_tokens=150,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            current_app.logger.warning(f"GPT error message failed: {e}, using translation")
            return self._translate_if_needed(english_message, language)
