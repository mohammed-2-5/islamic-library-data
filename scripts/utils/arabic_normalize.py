"""Arabic text normalization utilities for Islamic library data processing."""

import re
import unicodedata

# Arabic diacritics (tashkeel) pattern
_DIACRITICS = re.compile(
    r'[\u064B-\u0652'  # Fathatan through Sukun
    r'\u0670'           # Superscript Alef
    r'\u06D6-\u06ED'    # Small high ligatures, Quranic annotations
    r'\u0640'           # Tatweel (kashida)
    r'\u0617-\u061A'    # Small Fatha, Damma, Kasra, etc.
    r'\u08F0-\u08F3'    # Extended Arabic diacritics
    r']'
)

# Hamza normalization map
_HAMZA_MAP = str.maketrans({
    '\u0622': '\u0627',  # Alef with Madda → Alef
    '\u0623': '\u0627',  # Alef with Hamza above → Alef
    '\u0625': '\u0627',  # Alef with Hamza below → Alef
    '\u0671': '\u0627',  # Alef Wasla → Alef
    '\u0624': '\u0648',  # Waw with Hamza → Waw
    '\u0626': '\u064A',  # Ya with Hamza → Ya
})

# Alef Maksura / Ya normalization
_YA_MAP = str.maketrans({
    '\u0649': '\u064A',  # Alef Maksura → Ya
})

# Ta Marbuta normalization
_TA_MAP = str.maketrans({
    '\u0629': '\u0647',  # Ta Marbuta → Ha
})


def strip_diacritics(text: str) -> str:
    """Remove all Arabic diacritical marks (tashkeel)."""
    return _DIACRITICS.sub('', text)


def normalize_hamza(text: str) -> str:
    """Normalize all Hamza variants to their base letter."""
    return text.translate(_HAMZA_MAP)


def normalize_ya(text: str) -> str:
    """Normalize Alef Maksura to Ya."""
    return text.translate(_YA_MAP)


def normalize_ta_marbuta(text: str) -> str:
    """Normalize Ta Marbuta to Ha."""
    return text.translate(_TA_MAP)


def normalize_arabic(text: str) -> str:
    """Full Arabic normalization for search and deduplication.

    Applies: strip diacritics → normalize hamza → normalize ya → normalize ta marbuta → collapse whitespace.
    """
    text = strip_diacritics(text)
    text = normalize_hamza(text)
    text = normalize_ya(text)
    text = normalize_ta_marbuta(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_text(text: str) -> str:
    """Clean Arabic text for display: normalize whitespace, strip control chars."""
    # Remove zero-width characters
    text = re.sub(r'[\u200B-\u200F\u202A-\u202E\uFEFF]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def strip_html(text: str) -> str:
    """Remove HTML tags from text (for Shamela data)."""
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&nbsp;', ' ')
    return clean_text(text)


def build_search_text(text: str) -> str:
    """Build a normalized search-friendly version of Arabic text."""
    return normalize_arabic(text).lower()


def truncate_arabic(text: str, max_chars: int = 80) -> str:
    """Truncate Arabic text to max_chars, ending at a word boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Try to end at a space
    last_space = truncated.rfind(' ')
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated + '...'
