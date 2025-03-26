# utils/load_scraped_insights.py — with cleaning logic

import os

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
    path = "data/scraped_community_posts.txt"
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    insights = []
    for line in lines:
        if is_high_signal(line):
            insights.append({
                "text": line,
                "source": "reddit",
                "type_tag": "Discussion",  # default until scored
            })

    return insights

def process_insights(insights):
    # Additional post-cleaning can go here later
    return insights
