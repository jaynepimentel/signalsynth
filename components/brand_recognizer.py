# components/brand_recognizer.py — brand detection with env/local model + alias expansion

import os, re
from difflib import get_close_matches
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util

load_dotenv()

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

def _load_embed():
    name = os.getenv("SS_EMBED_MODEL", "intfloat/e5-base-v2")
    try:
        local = f"models/{name.replace('/','_')}"
        m = SentenceTransformer(local) if os.path.isdir(local) else SentenceTransformer(name)
    except Exception:
        m = SentenceTransformer("all-MiniLM-L6-v2")
    m.max_seq_length = int(os.getenv("SS_MAX_SEQ_LEN", "384"))
    return m

_model = _load_embed()
_term_emb = _model.encode(ALL_TERMS, normalize_embeddings=True)

def recognize_brand(text: str, debug: bool=False) -> str:
    tl = (text or "").lower()

    # 1) Lexical
    for brand, terms in BRAND_KEYWORDS.items():
        if any(term in tl for term in terms):
            if debug: print(f"[BRAND] Lexical → {brand}")
            return brand

    # 2) Semantic
    try:
        emb = _model.encode(tl, normalize_embeddings=True)
        sims = util.cos_sim(emb, _term_emb)[0].cpu().numpy()
        best = ALL_TERMS[int(sims.argmax())]
        for brand, terms in BRAND_KEYWORDS.items():
            if best in terms:
                if debug: print(f"[BRAND] Semantic '{best}' → {brand}")
                return brand
    except Exception as e:
        if debug: print("[BRAND] Semantic error:", e)

    # 3) Fuzzy
    fuzzy = get_close_matches(tl, ALL_TERMS, n=1, cutoff=0.88)
    if fuzzy:
        for brand, terms in BRAND_KEYWORDS.items():
            if fuzzy[0] in terms:
                if debug: print(f"[BRAND] Fuzzy '{fuzzy[0]}' → {brand}")
                return brand

    if debug: print("[BRAND] Unknown")
    return "Unknown"