# brand_recognizer.py — brand detection with fuzzy + pattern matching
import re
from difflib import get_close_matches

BRAND_KEYWORDS = {
    "eBay": ["ebay", "ebay live", "ebay vault", "standard envelope"],
    "Fanatics Collect": ["fanatics", "fanatics collect", "fanatics vault"],
    "WhatNot": ["whatnot", "whatnot app"],
    "Alt": ["alt", "alt marketplace"],
    "Loupe": ["loupe", "loupe app"],
    "Goldin": ["goldin", "goldin auctions"]
}

ALL_TERMS = [term for values in BRAND_KEYWORDS.values() for term in values]

def recognize_brand(text):
    text_lower = text.lower()

    # Pattern match
    for brand, terms in BRAND_KEYWORDS.items():
        for term in terms:
            if term in text_lower:
                return brand

    # Fuzzy fallback
    words = re.findall(r"\b\w+\b", text_lower)
    close = get_close_matches(" ".join(words), ALL_TERMS, n=1, cutoff=0.8)
    if close:
        for brand, terms in BRAND_KEYWORDS.items():
            if close[0] in terms:
                return brand

    return "Unknown"
