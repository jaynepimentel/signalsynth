# load_scraped_insights.py — dual-source parsing + AI-ready preprocessing for insights
import os
from components.enhanced_classifier import enhance_insight

NOISE_PHRASES = [
    "mail day", "for sale", "look at this", "showing off", "pickup post",
    "got this", "check this out", "look what i found", "haul", "pc update"
]

REQUIRED_KEYWORDS = [
    "ebay", "grading", "vault", "shipping", "return", "refund",
    "authentication", "delay", "scam", "psa", "whatnot", "fanatics", "alt marketplace"
]

SOURCE_PATHS = [
    "scraped_community_posts.txt",
    "scraped_twitter_posts.txt"
]

def is_high_signal(text):
    t = text.lower()
    if len(t) < 40:
        return False
    if any(noise in t for noise in NOISE_PHRASES):
        return False
    if any(required in t for required in REQUIRED_KEYWORDS):
        return True
    return False

def load_scraped_posts():
    insights = []
    for file_path in SOURCE_PATHS:
        if not os.path.exists(file_path):
            print(f"❌ Missing: {file_path}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        for line in lines:
            if is_high_signal(line):
                insights.append({
                    "text": line,
                    "source": "twitter" if "twitter" in file_path.lower() else "reddit",
                    "type_tag": "Discussion"
                })
    return insights

def process_insights(raw):
    return [enhance_insight(i) for i in raw if isinstance(i, dict) and i.get("text")]
