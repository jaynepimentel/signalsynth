# brand_recognizer.py — brand detection with semantic fallback
import re
from difflib import get_close_matches
from sentence_transformers import SentenceTransformer, util

BRAND_KEYWORDS = {
    "eBay": ["ebay", "ebay live", "ebay vault", "standard envelope"],
    "Fanatics Collect": ["fanatics", "fanatics collect", "fanatics vault"],
    "WhatNot": ["whatnot", "whatnot app"],
    "Alt": ["alt", "alt marketplace"],
    "Loupe": ["loupe", "loupe app"],
    "Goldin": ["goldin", "goldin auctions"]
}

ALL_TERMS = [term for values in BRAND_KEYWORDS.values() for term in values]
model = SentenceTransformer("all-MiniLM-L6-v2")
term_embeddings = model.encode(ALL_TERMS)

def recognize_brand(text):
    text_lower = text.lower()
    for brand, terms in BRAND_KEYWORDS.items():
        for term in terms:
            if term in text_lower:
                return brand

    # Semantic fallback
    embedding = model.encode(text_lower)
    scores = util.cos_sim(embedding, term_embeddings)[0]
    best_match_idx = scores.argmax().item()
    matched_term = ALL_TERMS[best_match_idx]

    for brand, terms in BRAND_KEYWORDS.items():
        if matched_term in terms:
            return brand
    return "Unknown"