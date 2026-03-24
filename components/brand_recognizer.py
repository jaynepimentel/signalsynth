# components/brand_recognizer.py — brand detection with lexical + fuzzy matching

from difflib import get_close_matches

BRAND_KEYWORDS = {
    "eBay": ["ebay", "ebay live", "ebay vault", "standard envelope", "authenticity guarantee", "auth guarantee"],
    "Fanatics Collect": ["fanatics", "fanatics collect", "fanatics vault", "fanatics live"],
    "WhatNot": ["whatnot", "whatnot app", "whatnot live"],
    "Alt": ["alt", "alt marketplace"],
    "Loupe": ["loupe", "loupe app"],
    "Goldin": ["goldin", "goldin auctions", "goldin marketplace"],
    "PSA": ["psa", "grading psa", "psa grading", "psa integration"],
    "COMC": ["comc", "check out my cards", "check out cards"]
}

ALL_TERMS = [t for terms in BRAND_KEYWORDS.values() for t in terms]

def recognize_brand(text: str, debug: bool=False) -> str:
    """Recognize brand from text using lexical matching only (no embeddings for fast startup)."""
    tl = (text or "").lower()

    # 1) Lexical matching
    for brand, terms in BRAND_KEYWORDS.items():
        if any(term in tl for term in terms):
            if debug: print(f"[BRAND] Lexical → {brand}")
            return brand

    # 2) Fuzzy matching
    fuzzy = get_close_matches(tl, ALL_TERMS, n=1, cutoff=0.88)
    if fuzzy:
        for brand, terms in BRAND_KEYWORDS.items():
            if fuzzy[0] in terms:
                if debug: print(f"[BRAND] Fuzzy '{fuzzy[0]}' → {brand}")
                return brand

    if debug: print("[BRAND] Unknown")
    return "Unknown"