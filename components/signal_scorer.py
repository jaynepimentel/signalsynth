# signal_scorer.py — full version with classification, scoring, brand sentiment
import re
from components.brand_sentiment_classifier import classify_brand_sentiment
from components.enhanced_classifier import enhance_insight

KEY_PATTERNS = [
    "psa", "vault", "graded", "shipping", "fees", "tracking", "eBay", "goldin", "pop report", "autopay"
]

LOW_VALUE_PATTERNS = [
    "mail day", "look what I got", "for sale", "got this", "pc", "show off"
]

BRAND_PATTERNS = {
    "eBay Live": ["ebay live"],
    "Fanatics Collect": ["fanatics collect", "fanatics vault", "fanatics"],
    "WhatNot": ["whatnot"],
    "Alt": ["alt marketplace"],
    "Loupe": ["loupe app"]
}

COMPLAINT_PHRASES = [
    "scam", "delay", "issue", "problem", "error", "not working", "late", "no response", "waste", "never received", "fake", "poor service"
]

FEATURE_PATTERNS = [
    "can i", "should add", "wish there was", "would be great if", "there needs to be", "enable", "add", "introduce", "automate", "allow me to", "is there a way to"
]

CONFUSION_PHRASES = [
    "how do i", "should i", "what should", "why does", "is it normal", "i don't understand", "do i need to", "can someone explain"
]

MARKETPLACE_CHATTER = [
    "fs/ft", "for sale", "looking to move", "nft", "anyone want this", "dm me", "sold", "buy it now", "offers"
]

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
    return "eBay" if "ebay" in text else "General"

def generate_ideas(text):
    text = text.lower()
    ideas = []
    if "psa" in text and "value" in text:
        ideas.append("Add graded value tooltip (e.g. PSA 10 = 1.7x vs raw)")
        ideas.append("Confidence meter for price based on historical PSA comps")
    if "shipping" in text:
        ideas.append("Show real-time shipping ETA based on buyer location")
    if "vault" in text and "delay" in text:
        ideas.append("Display PSA → Vault intake status in seller flow")
    if "fees" in text or "cut" in text:
        ideas.append("Show seller fee breakdown before listing submission")
    if "refund" in text:
        ideas.append("Auto-trigger refund for authentication delay >5 days")
    if "sgc" in text and "vault" in text:
        ideas.append("Enable non-PSA slabs to be sent to vault with eligibility UX")
    if "get it graded" in text:
        ideas.append("Educational nudge: grading 101 module or link in seller tools")
    if "whatnot" in text and "shipping" in text:
        ideas.append("Highlight eBay Live's combined shipping advantage vs. WhatNot")
    if not ideas:
        ideas.append("Suggest listing improvements or clarify pricing guidance")
    return ideas

def classify_effort(idea_text):
    idea_text = " ".join(idea_text).lower()
    if any(x in idea_text for x in ["tooltip", "label", "reminder", "nudge"]):
        return "Low"
    if any(x in idea_text for x in ["breakdown", "comps", "meter", "ETA", "alert"]):
        return "Medium"
    if any(x in idea_text for x in ["integration", "tracking", "automation", "workflow"]):
        return "High"
    return "Medium"

def classify_type(text):
    text = text.lower()
    reason = ""
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

def filter_relevant_insights(insights, min_score=3):
    filtered = []
    for i in insights:
        text = i.get("text", "")
        score = score_insight(text)
        i["score"] = score

        # Enhance with smart AI classifier
        i = enhance_insight(i)

        i["ideas"] = generate_ideas(text)
        i["effort"] = classify_effort(i["ideas"])

        if i["type_tag"] != "Marketplace Chatter" and score >= min_score:
            filtered.append(i)

    return filtered
