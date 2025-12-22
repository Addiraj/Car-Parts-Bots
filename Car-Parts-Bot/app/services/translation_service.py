
# from deep_translator import GoogleTranslator
# # from langdetect import detect, DetectorFactory
# import re
# import fasttext
# import os

# # DetectorFactory.seed = 0
# PART_PATTERN = re.compile(r"^[A-Za-z0-9\s\-\/\.\+]+$", re.UNICODE)

# class TranslationService:

#     BASE_LANG = "en"  # internal language for NLU + DB lookups
#     BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#     MODEL_PATH = os.path.join(BASE_DIR, "models", "lid.176.bin")

#     model = fasttext.load_model(MODEL_PATH)
#     FULL_SUPPORT_LANGS = {
#         "en", "ar", "hi", "ur", "es", "fr", "pt", "de", "ru", "zh", "it", "ja"
#     }

#     # Regex for extracting words with meaningful letters
#     WORD_REGEX = re.compile(r"[A-Za-z\u0600-\u06FF]+", re.UNICODE)
#     VOWEL_REGEX = re.compile(r"[aeiouAEIOU\u0621-\u064A]", re.UNICODE)
    
#     # def contains_real_word(self, text: str) -> bool:
#     #     words = self.WORD_REGEX.findall(text)
#     #     return any(len(w) >= 3 for w in words)


#     def contains_real_word(self, text: str) -> bool:
#         words = self.WORD_REGEX.findall(text)
#         return any(len(w) >= 3 and self.VOWEL_REGEX.search(w) for w in words)

#     # def detect_language(self, text: str) -> str:
#     #     text = text.strip()

#     #     if not text:
#     #         return self.BASE_LANG

#     #     # 🔒 No real words → force English
#     #     if not self.contains_real_word(text):
#     #         print("No real words detected, defaulting to ENGLISH")
#     #         return self.BASE_LANG

#     #     # Pure part-number-like text → force English
#     #     if PART_PATTERN.match(text):
#     #         print("Detected part-number-like text, defaulting to ENGLISH")
#     #         return self.BASE_LANG

#     #     try:
#     #         label, score = self.model.predict(text)
#     #         lang = label[0].replace("__label__", "")
#     #         print(f"Detected language via FastText: {lang} (score={score[0]:.2f})")
#     #         return lang or self.BASE_LANG
#     #     except Exception as e:
#     #         print("FastText detection failed:", e)
#     #         return self.BASE_LANG

#     def detect_language(self, text: str) -> str:
#         text = text.strip()
#         if not text:
#             return self.BASE_LANG


#         # Pure part-number-like text → force English
#         if PART_PATTERN.match(text):
#             print("Detected part-number-like text, defaulting to ENGLISH")
#             return self.BASE_LANG

#         try:
#             label, score = self.model.predict(text)
#             lang = label[0].replace("__label__", "")
#             print(f"Detected language via FastText: {lang} (score={score[0]:.2f})")
#             return lang or self.BASE_LANG
#         except Exception as e:
#             print("FastText detection failed:", e)
#             return self.BASE_LANG
        
#     def to_base_language(self, text: str) -> tuple[str, str]:
#         lang = self.detect_language(text)

#         if lang == self.BASE_LANG:
#             return text, lang

#         if lang in self.FULL_SUPPORT_LANGS:
#             try:
#                 translated = GoogleTranslator(source=lang, target=self.BASE_LANG).translate(text)
#                 return translated or text, lang
#             except Exception as e:
#                 print(f"Google Translate failed: {e}")
#                 return text, lang

#         return text, lang


#     # Convert English responses → user's language (UI text only)
#     def from_base_language(self, text: str, target_language: str) -> str:
#         if not text or target_language == self.BASE_LANG:
#             return text

#         if target_language not in self.FULL_SUPPORT_LANGS:
#             return text  # safer fallback

#         try:
#             print("Translating from BASE_LANG to", target_language)
#             translated = GoogleTranslator(source=self.BASE_LANG, target=target_language).translate(text)
#             return translated or text
#         except Exception as e:
#             print(f"Google Translate failed: {e}")
#             return text


#     # Generic translate if needed
#     def translate(self, text: str, target_language: str) -> str:
#         if not text or target_language == self.BASE_LANG:
#             return text

#         try:
#             return GoogleTranslator(source="auto", target=target_language).translate(text) or text
#         except Exception as e:
#             print(f"Translate failed: {e}")
#             return text


# # def detect_language(self, text: str) -> str:
        
#     #     text = text.strip()
#     #     if not text:
#     #         return self.BASE_LANG

#     #     try:
#     #         lang = detect(text)
#     #         print(f"FROM LANGDETECT language: {lang}")
#     #         return lang if lang else self.BASE_LANG
#     #     except Exception:
#     #         print("Language detection failed, defaulting to ENGLISH")
#     #         return self.BASE_LANG

import os
import re
import fasttext
import urllib.request
from deep_translator import GoogleTranslator


# -------------------- CONSTANTS --------------------

BASE_LANG = "en"

FULL_SUPPORT_LANGS = {
    "en", "ar", "hi", "ur", "es", "fr", "pt", "de", "ru", "zh", "it", "ja"
}

FASTTEXT_MODEL_URL = (
    "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
)

# Part-number–like input (force English)
PART_PATTERN = re.compile(r"^[A-Za-z0-9\s\-\/\.\+]+$", re.UNICODE)

# Word detection
WORD_REGEX = re.compile(r"[A-Za-z\u0600-\u06FF]+", re.UNICODE)
VOWEL_REGEX = re.compile(r"[aeiouAEIOU\u0621-\u064A]", re.UNICODE)


# -------------------- HELPERS --------------------

def get_model_path() -> str:
    """
    Resolve model path.
    Uses persistent disk on Render if available.
    """
    base_dir = os.getenv("RENDER_DISK_PATH") or os.getcwd()
    return os.path.join(base_dir, "models", "lid.176.bin")


def ensure_fasttext_model(path: str) -> None:
    """
    Download fastText model if missing.
    """
    if os.path.exists(path):
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    print("Downloading fastText language detection model...")

    urllib.request.urlretrieve(FASTTEXT_MODEL_URL, path)

    print("fastText model downloaded.")


# -------------------- SERVICE --------------------

class TranslationService:
    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            model_path = get_model_path()
            ensure_fasttext_model(model_path)
            cls._model = fasttext.load_model(model_path)
        return cls._model

    @staticmethod
    def _contains_real_word(text: str) -> bool:
        words = WORD_REGEX.findall(text)
        return any(len(w) >= 3 and VOWEL_REGEX.search(w) for w in words)

    # -------------------- LANGUAGE DETECTION --------------------

    def detect_language(self, text: str) -> str:
        text = text.strip()
        if not text:
            return BASE_LANG

        # Part numbers / codes → English
        if PART_PATTERN.match(text):
            return BASE_LANG

        try:
            model = self._get_model()
            labels, scores = model.predict(text)
            lang = labels[0].replace("__label__", "")
            return lang or BASE_LANG
        except Exception as e:
            print("FastText detection failed:", e)
            return BASE_LANG

    # -------------------- TRANSLATION FLOWS --------------------

    def to_base_language(self, text: str) -> tuple[str, str]:
        """
        Detect language and translate input → BASE_LANG.
        Returns: (translated_text, detected_language)
        """
        lang = self.detect_language(text)

        if lang == BASE_LANG:
            return text, lang

        if lang in FULL_SUPPORT_LANGS:
            try:
                translated = GoogleTranslator(
                    source=lang, target=BASE_LANG
                ).translate(text)
                return translated or text, lang
            except Exception as e:
                print("Google Translate failed:", e)

        return text, lang

    def from_base_language(self, text: str, target_language: str) -> str:
        """
        Translate BASE_LANG response → user's language (UI only).
        """
        if not text or target_language == BASE_LANG:
            return text

        if target_language not in FULL_SUPPORT_LANGS:
            return text

        try:
            return GoogleTranslator(
                source=BASE_LANG, target=target_language
            ).translate(text) or text
        except Exception as e:
            print("Google Translate failed:", e)
            return text

    def translate(self, text: str, target_language: str) -> str:
        """
        Generic translation (auto → target).
        """
        if not text or target_language == BASE_LANG:
            return text

        try:
            return GoogleTranslator(
                source="auto", target=target_language
            ).translate(text) or text
        except Exception as e:
            print("Translate failed:", e)
            return text
