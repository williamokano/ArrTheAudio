"""Language code conversion utilities."""

# ISO 639-1 (2-letter) to ISO 639-2/B (3-letter) mapping
# TMDB uses ISO 639-1, audio tracks typically use ISO 639-2
ISO_639_1_TO_639_2 = {
    # Common languages
    "en": "eng",  # English
    "es": "spa",  # Spanish
    "fr": "fre",  # French
    "de": "ger",  # German
    "it": "ita",  # Italian
    "pt": "por",  # Portuguese
    "ru": "rus",  # Russian
    "ja": "jpn",  # Japanese
    "ko": "kor",  # Korean
    "zh": "chi",  # Chinese
    "ar": "ara",  # Arabic
    "hi": "hin",  # Hindi
    "nl": "dut",  # Dutch
    "pl": "pol",  # Polish
    "tr": "tur",  # Turkish
    "sv": "swe",  # Swedish
    "da": "dan",  # Danish
    "no": "nor",  # Norwegian
    "fi": "fin",  # Finnish
    "cs": "cze",  # Czech
    "hu": "hun",  # Hungarian
    "ro": "rum",  # Romanian
    "th": "tha",  # Thai
    "vi": "vie",  # Vietnamese
    "id": "ind",  # Indonesian
    "he": "heb",  # Hebrew
    "el": "gre",  # Greek
    "uk": "ukr",  # Ukrainian
    "ca": "cat",  # Catalan
    "sk": "slo",  # Slovak
    "hr": "hrv",  # Croatian
    "sr": "srp",  # Serbian
    "bg": "bul",  # Bulgarian
    "lt": "lit",  # Lithuanian
    "lv": "lav",  # Latvian
    "et": "est",  # Estonian
    "sl": "slv",  # Slovenian
    "fa": "per",  # Persian
    "ms": "may",  # Malay
    "ta": "tam",  # Tamil
    "te": "tel",  # Telugu
    "bn": "ben",  # Bengali
    "mr": "mar",  # Marathi
}


def convert_iso639_1_to_2(code: str) -> str:
    """Convert ISO 639-1 (2-letter) code to ISO 639-2/B (3-letter).

    Args:
        code: 2-letter language code (e.g., 'en')

    Returns:
        3-letter language code (e.g., 'eng'), or original if not found
    """
    if not code:
        return code

    # If already 3 letters, return as-is
    if len(code) == 3:
        return code.lower()

    # Convert 2-letter to 3-letter
    code_lower = code.lower()
    return ISO_639_1_TO_639_2.get(code_lower, code_lower)


def normalize_language_code(code: str) -> str:
    """Normalize language code to 3-letter ISO 639-2 format.

    Handles both 2-letter and 3-letter codes.

    Args:
        code: Language code (2 or 3 letters)

    Returns:
        Normalized 3-letter code
    """
    if not code:
        return code

    return convert_iso639_1_to_2(code)


# Language name to ISO 639-2 (3-letter) mapping
# Sonarr v4 provides language names like "Japanese", "English"
LANGUAGE_NAME_TO_639_2 = {
    "english": "eng",
    "spanish": "spa",
    "french": "fre",
    "german": "ger",
    "italian": "ita",
    "portuguese": "por",
    "russian": "rus",
    "japanese": "jpn",
    "korean": "kor",
    "chinese": "chi",
    "arabic": "ara",
    "hindi": "hin",
    "dutch": "dut",
    "polish": "pol",
    "turkish": "tur",
    "swedish": "swe",
    "danish": "dan",
    "norwegian": "nor",
    "finnish": "fin",
    "czech": "cze",
    "hungarian": "hun",
    "romanian": "rum",
    "thai": "tha",
    "vietnamese": "vie",
    "indonesian": "ind",
    "hebrew": "heb",
    "greek": "gre",
    "ukrainian": "ukr",
    "catalan": "cat",
    "slovak": "slo",
    "croatian": "hrv",
    "serbian": "srp",
    "bulgarian": "bul",
    "lithuanian": "lit",
    "latvian": "lav",
    "estonian": "est",
    "slovenian": "slv",
    "persian": "per",
    "malay": "may",
    "tamil": "tam",
    "telugu": "tel",
    "bengali": "ben",
    "marathi": "mar",
}


def language_name_to_code(name: str) -> str:
    """Convert language name to ISO 639-2 (3-letter) code.

    Handles names from Sonarr v4 like "Japanese", "English".

    Args:
        name: Language name (e.g., "Japanese", "English")

    Returns:
        3-letter ISO 639-2 code (e.g., "jpn", "eng"), or original if not found
    """
    if not name:
        return name

    # Normalize to lowercase for lookup
    name_lower = name.lower()
    return LANGUAGE_NAME_TO_639_2.get(name_lower, name_lower)
