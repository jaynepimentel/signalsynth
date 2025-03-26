# load_scraped_insights.py — with dual-source support for Reddit + Twitter

import os

# Noise and signal keywords
NOISE_PHRASES = [
    "mail day", "for sale", "look at this", "showing off", "pickup post",
    "got this", "check this out", "look what i found", "haul", "pc update"
]

REQUIRED_KEYWORDS = [
    "ebay", "grading", "vault", "shipping", "return", "refund",
    "authentication", "delay", "scam", "psa", "whatnot", "fanatics", "alt marketplace"
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
    files = [
        "C:/Users/jayne/signalsynth/scraped_community_posts.txt",
        "C:/Users/jayne/signalsynth/scraped_twitter_posts.txt"
    ]

    insights = []
    for path in files:
        if not os.path.exists(path):
            print(f"❌ File not found: {path}")
            continue

        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        for line in lines:
            if is_high_signal(line):
                insights.append({
                    "text": line,
                    "source": "twitter" if "twitter" in path.lower() else "reddit",
                    "type_tag": "Discussion",  # default until AI classifies
                })

    return insights

def process_insights(insights):
    # Placeholder for future data cleaning logic
    return insights
