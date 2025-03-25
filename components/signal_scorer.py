# signal_scorer.py — now with smarter keyword triggers + OpenAI fallback tagging + model-ready structure
import re
from components.enhanced_classifier import enhance_insight
from components.ai_suggester import generate_pm_ideas

# Improved trigger lists
FEATURE_PATTERNS = [
    "should add", "wish", "would love", "need to", "feature request", "add support", "can you add", "enable", "introduce", "please include"
]

COMPLAINT_PHRASES = [
    "issue", "bug", "broken", "doesn’t work", "not working", "stuck", "error", "won’t load", "refund", "delay", "never received"
]

CONFUSION_PHRASES = [
    "how do", "i don’t understand", "what does", "how should", "why does", "can someone explain", "is this normal", "do i need to"
]

MARKETPLACE_CHATTER = [
    "fs/ft", "for sale", "sold", "buy it now", "offer up", "dm me", "mail day"
]

def classify_type(text):
    text = text.lower()

    if any(p in text for p in MARKETPLACE_CHATTER):
        return {"label": "Marketplace Chatter", "confidence": 95, "reason": "Selling or trading language"}

    if any(p in text for p in FEATURE_PATTERNS):
        return {"label": "Feature Request", "confidence": 90, "reason": "Detected feature-request phrasing"}

    if any(p in text for p in COMPLAINT_PHRASES):
        return {"label": "Complaint", "confidence": 88, "reason": "Detected bug or complaint language"}

    if any(p in text for p in CONFUSION_PHRASES):
        return {"label": "Confusion", "confidence": 85, "reason": "Detected confusion or how-to phrasing"}

    # Fallback if no strong pattern match
    return {"label": "Discussion", "confidence": 70, "reason": "Defaulted to general discussion"}

def classify_effort(idea_text):
    idea_text = " ".join(idea_text).lower()
    if any(x in idea_text for x in ["tooltip", "label", "nudge"]):
        return "Low"
    if any(x in idea_text for x in ["breakdown", "chart", "comps"]):
        return "Medium"
    if any(x in idea_text for x in ["integration", "automation", "workflow", "sync"]):
        return "High"
    return "Medium"

def score_insight(text):
    score = 0
    lowered = text.lower()
    for keyword in ["vault", "psa", "graded", "shipping", "authenticity", "whatnot", "fanatics"]:
        if keyword in lowered:
            score += 5
    if "scam" in lowered or "broken" in lowered:
        score += 8
    return score

def filter_relevant_insights(insights, min_score=3):
    enriched = []
    for i in insights:
        text = i.get("text", "")
        i["score"] = score_insight(text)

        # --- Add type classification
        tag_result = classify_type(text)
        i["type_tag"] = tag_result["label"]
        i["type_confidence"] = tag_result["confidence"]
        i["type_reason"] = tag_result["reason"]

        # --- AI-enhanced insight processing (sentiment, brand, subtag, etc.)
        i = enhance_insight(i)

        # --- Generate ideas (cached GPT)
        i["ideas"] = generate_pm_ideas(text, i.get("target_brand"))
        i["effort"] = classify_effort(i["ideas"])

        if i["type_tag"] != "Marketplace Chatter" and i["score"] >= min_score:
            enriched.append(i)

    return enriched
