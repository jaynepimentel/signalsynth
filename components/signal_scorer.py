# signal_scorer.py — enhanced version with AI suggestions, sentiment, brand detection
import re
from components.enhanced_classifier import enhance_insight
from components.ai_suggester import generate_pm_ideas

# Keyword scoring config
KEY_PATTERNS = [
    "psa", "vault", "graded", "shipping", "fees", "tracking", "eBay", "goldin", "pop report", "autopay"
]
LOW_VALUE_PATTERNS = [
    "mail day", "look what I got", "for sale", "got this", "pc", "show off"
]

# Marketplace chatter / noise
MARKETPLACE_CHATTER = [
    "fs/ft", "for sale", "looking to move", "nft", "anyone want this", "dm me", "sold", "buy it now", "offers"
]

# Phrase triggers
COMPLAINT_PHRASES = [
    "scam", "delay", "issue", "problem", "error", "not working", "late", "no response", "waste", "never received", "fake", "poor service"
]
FEATURE_PATTERNS = [
    "can i", "should add", "wish there was", "would be great if", "there needs to be", "enable", "add", "introduce", "automate", "allow me to", "is there a way to"
]
CONFUSION_PHRASES = [
    "how do i", "should i", "what should", "why does", "is it normal", "i don't understand", "do i need to", "can someone explain"
]

# Brand keyword map
BRAND_PATTERNS = {
    "eBay Live": ["ebay live"],
    "Fanatics Collect": ["fanatics collect", "fanatics vault", "fanatics"],
    "WhatNot": ["whatnot"],
    "Alt": ["alt marketplace"],
    "Loupe": ["loupe app"]
}

# --------------------------------------
# Core scoring logic
# --------------------------------------

def score_insight(text):
    text = text.lower()
    score = 0
    for word in KEY_PATTERNS:
        if word in text:
            score += 8
    if "psa" in text and "vault" in text:
        score += 12
    if "ebay" in text:
        score += 10
    if re.search(r"(how|why|can|should|where).*\?", text):
        score += 6
    for noise in LOW_VALUE_PATTERNS:
        if noise in text:
            score -= 10
    if len(text.split()) < 6:
        score -= 5
    return score

def detect_target_brand(text):
    text = text.lower()
    for brand, keywords in BRAND_PATTERNS.items():
        for term in keywords:
            if term in text:
                return brand
    return "eBay" if "ebay" in text else "Unknown"

def classify_type(text):
    text = text.lower()
    if any(x in text for x in MARKETPLACE_CHATTER):
        return {"label": "Marketplace Chatter", "confidence": 98, "reason": "Selling language: FS/NFT, for sale, offers"}
    if any(x in text for x in COMPLAINT_PHRASES):
        return {"label": "Complaint", "confidence": 90, "reason": "Includes complaint term like scam, delay, issue"}
    if any(x in text for x in FEATURE_PATTERNS):
        return {"label": "Feature Request", "confidence": 85, "reason": "Phrasing implies request for functionality"}
    if any(x in text for x in CONFUSION_PHRASES):
        return {"label": "Confusion", "confidence": 82, "reason": "Phrasing indicates user doesn’t understand something"}
    if len(text.split()) < 10:
        return {"label": "Unknown", "confidence": 60, "reason": "Too short to infer intent"}
    return {"label": "Discussion", "confidence": 75, "reason": "Default to discussion if no strong signals"}

def classify_effort(idea_text):
    idea_text = " ".join(idea_text).lower()
    if any(x in idea_text for x in ["tooltip", "label", "reminder", "nudge"]):
        return "Low"
    if any(x in idea_text for x in ["breakdown", "comps", "meter", "ETA", "alert"]):
        return "Medium"
    if any(x in idea_text for x in ["integration", "tracking", "automation", "workflow"]):
        return "High"
    return "Medium"

# --------------------------------------
# Core processing pipeline
# --------------------------------------

def filter_relevant_insights(insights, min_score=3):
    filtered = []

    for i in insights:
        text = i.get("text", "")
        score = score_insight(text)
        i["score"] = score

        # Run LLM-enhanced classification
        i = enhance_insight(i)

        # Detect brand (fallback if not handled in enhance)
        i["target_brand"] = i.get("target_brand") or detect_target_brand(text)

        # Generate PM ideas via OpenAI
        i["ideas"] = generate_pm_ideas(text, i["target_brand"])

        # Effort classification
        i["effort"] = classify_effort(i["ideas"])

        if i["type_tag"] != "Marketplace Chatter" and score >= min_score:
            filtered.append(i)

    return filtered
