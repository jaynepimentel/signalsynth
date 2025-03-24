# brand_sentiment_classifier.py — Classifies brand mentions as Praise, Complaint, or Neutral
import re

PRAISE_KEYWORDS = [
    "love", "fast", "quick", "easy", "reliable", "awesome", "best", "great", "smooth", "affordable", "super impressed", "good deal", "got it fast"
]

COMPLAINT_KEYWORDS = [
    "slow", "broken", "bad", "issue", "problem", "delay", "scam", "waste", "frustrated", "glitch", "too expensive", "fees", "doesn't work", "never received"
]

PRAISE_PATTERNS = [
    r"i (really )?(love|like|appreciate) .*?\\b({brand})\\b",
    r"({brand}) .*? is (so )?(easy|smooth|great|fast|awesome)"
]

COMPLAINT_PATTERNS = [
    r"({brand}) .*? (is|was|has been)? .*? (terrible|scam|problem|issue|slow|broken)",
    r"(hate|can't stand|avoid) .*?({brand})"
]

def classify_brand_sentiment(text, brand):
    text = text.lower()
    brand = brand.lower()

    # Keyword detection
    if any(p in text for p in PRAISE_KEYWORDS) and brand in text:
        return "Praise"
    if any(c in text for c in COMPLAINT_KEYWORDS) and brand in text:
        return "Complaint"

    # Regex pattern matching
    for pat in PRAISE_PATTERNS:
        if re.search(pat.format(brand=brand), text):
            return "Praise"

    for pat in COMPLAINT_PATTERNS:
        if re.search(pat.format(brand=brand), text):
            return "Complaint"

    return "Neutral"
