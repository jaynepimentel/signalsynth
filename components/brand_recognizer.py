# brand_recognizer.py — brand detection with semantic + fuzzy fallback and alias expansion

import re
from difflib import get_close_matches
from sentence_transformers import SentenceTransformer, util

# 🔍 Known brands and aliases
BRAND_KEYWORDS = {
    "eBay": [
        "ebay", "ebay live", "ebay vault", "standard envelope",
        "authenticity guarantee", "auth guarantee"
    ],
    "Fanatics Collect": [
        "fanatics", "fanatics collect", "fanatics vault", "fanatics live"
    ],
    "WhatNot": [
        "whatnot", "whatnot app", "whatnot live"
    ],
    "Alt": [
        "alt", "alt marketplace"
    ],
    "Loupe": [
        "loupe", "loupe app"
    ],
    "Goldin": [
        "goldin", "goldin auctions", "goldin marketplace"
    ],
    "PSA": [
        "psa", "grading psa", "psa grading", "psa integration"
    ],
    "COMC": [
        "comc", "check out my cards", "check out cards"
    ]
}

# Flatten terms and generate semantic embeddings
ALL_TERMS = [term for values in BRAND_KEYWORDS.values() for term in values]
model = SentenceTransformer("all-MiniLM-L6-v2")
term_embeddings = model.encode(ALL_TERMS)

# 🔍 Main detection function
def recognize_brand(text, debug=False):
    text_lower = text.lower()

    # 1. Direct match
    for brand, terms in BRAND_KEYWORDS.items():
        for term in terms:
            if term in text_lower:
                if debug:
                    print(f"[BRAND] Direct match: '{term}' → {brand}")
                return brand

    # 2. Semantic similarity fallback
    try:
        embedding = model.encode(text_lower)
        scores = util.cos_sim(embedding, term_embeddings)[0]
        best_idx = scores.argmax().item()
        matched_term = ALL_TERMS[best_idx]
        for brand, terms in BRAND_KEYWORDS.items():
            if matched_term in terms:
                if debug:
                    print(f"[BRAND] Semantic match: '{matched_term}' → {brand}")
                return brand
    except Exception as e:
        if debug:
            print(f"[BRAND] Semantic model error: {e}")

    # 3. Fuzzy fallback
    words = re.findall(r"\b\w+\b", text_lower)
    fuzzy_match = get_close_matches(" ".join(words), ALL_TERMS, n=1, cutoff=0.85)
    if fuzzy_match:
        for brand, terms in BRAND_KEYWORDS.items():
            if fuzzy_match[0] in terms:
                if debug:
                    print(f"[BRAND] Fuzzy match: '{fuzzy_match[0]}' → {brand}")
                return brand

    if debug:
        print("[BRAND] No match found. Returning 'Unknown'.")
    return "Unknown"
