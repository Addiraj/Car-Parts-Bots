
from deep_translator import GoogleTranslator
# from langdetect import detect, DetectorFactory
import re
import fasttext
import os

# DetectorFactory.seed = 0
PART_PATTERN = re.compile(r"^[A-Za-z0-9\s\-\/\.\+]+$", re.UNICODE)

class TranslationService:

    BASE_LANG = "en"  # internal language for NLU + DB lookups
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MODEL_PATH = os.path.join(BASE_DIR, "models", "lid.176.bin")

    model = fasttext.load_model(MODEL_PATH)
    FULL_SUPPORT_LANGS = {
        "en", "ar", "hi", "ur", "es", "fr", "pt", "de", "ru", "zh", "it", "ja"
    }

    # Regex for extracting words with meaningful letters
    WORD_REGEX = re.compile(r"[A-Za-z\u0600-\u06FF]+", re.UNICODE)
    VOWEL_REGEX = re.compile(r"[aeiouAEIOU\u0621-\u064A]", re.UNICODE)
    
    # def contains_real_word(self, text: str) -> bool:
    #     words = self.WORD_REGEX.findall(text)
    #     return any(len(w) >= 3 for w in words)


    def contains_real_word(self, text: str) -> bool:
        words = self.WORD_REGEX.findall(text)
        return any(len(w) >= 3 and self.VOWEL_REGEX.search(w) for w in words)

    # def detect_language(self, text: str) -> str:
    #     text = text.strip()

    #     if not text:
    #         return self.BASE_LANG

    #     # 🔒 No real words → force English
    #     if not self.contains_real_word(text):
    #         print("No real words detected, defaulting to ENGLISH")
    #         return self.BASE_LANG

    #     # Pure part-number-like text → force English
    #     if PART_PATTERN.match(text):
    #         print("Detected part-number-like text, defaulting to ENGLISH")
    #         return self.BASE_LANG

    #     try:
    #         label, score = self.model.predict(text)
    #         lang = label[0].replace("__label__", "")
    #         print(f"Detected language via FastText: {lang} (score={score[0]:.2f})")
    #         return lang or self.BASE_LANG
    #     except Exception as e:
    #         print("FastText detection failed:", e)
    #         return self.BASE_LANG

    def detect_language(self, text: str) -> str:
        text = text.strip()
        if not text:
            return self.BASE_LANG


        # Pure part-number-like text → force English
        if PART_PATTERN.match(text):
            print("Detected part-number-like text, defaulting to ENGLISH")
            return self.BASE_LANG

        try:
            label, score = self.model.predict(text)
            lang = label[0].replace("__label__", "")
            print(f"Detected language via FastText: {lang} (score={score[0]:.2f})")
            return lang or self.BASE_LANG
        except Exception as e:
            print("FastText detection failed:", e)
            return self.BASE_LANG
        
    def to_base_language(self, text: str) -> tuple[str, str]:
        lang = self.detect_language(text)

        if lang == self.BASE_LANG:
            return text, lang

        if lang in self.FULL_SUPPORT_LANGS:
            try:
                translated = GoogleTranslator(source=lang, target=self.BASE_LANG).translate(text)
                return translated or text, lang
            except Exception as e:
                print(f"Google Translate failed: {e}")
                return text, lang

        return text, lang


    # Convert English responses → user's language (UI text only)
    def from_base_language(self, text: str, target_language: str) -> str:
        if not text or target_language == self.BASE_LANG:
            return text

        if target_language not in self.FULL_SUPPORT_LANGS:
            return text  # safer fallback

        try:
            print("Translating from BASE_LANG to", target_language)
            translated = GoogleTranslator(source=self.BASE_LANG, target=target_language).translate(text)
            return translated or text
        except Exception as e:
            print(f"Google Translate failed: {e}")
            return text


    # Generic translate if needed
    def translate(self, text: str, target_language: str) -> str:
        if not text or target_language == self.BASE_LANG:
            return text

        try:
            return GoogleTranslator(source="auto", target=target_language).translate(text) or text
        except Exception as e:
            print(f"Translate failed: {e}")
            return text


# def detect_language(self, text: str) -> str:
        
    #     text = text.strip()
    #     if not text:
    #         return self.BASE_LANG

    #     try:
    #         lang = detect(text)
    #         print(f"FROM LANGDETECT language: {lang}")
    #         return lang if lang else self.BASE_LANG
    #     except Exception:
    #         print("Language detection failed, defaulting to ENGLISH")
    #         return self.BASE_LANG