# load_scraped_insights.py — Enhanced preprocessing with GPT filtering, metadata, and traceability
import os
import re
import hashlib
from components.enhanced_classifier import enhance_insight
from components.scoring_utils import gpt_estimate_sentiment_subtag

# Configuration
NOISE_PHRASES = [
    "mail day", "for sale", "look at this", "showing off", "pickup post",
    "got this", "check this out", "look what i found", "haul", "pc update"
]

REQUIRED_KEYWORDS = [
    "ebay", "grading", "vault", "shipping", "return", "refund",
    "authentication", "delay", "scam", "psa", "whatnot", "fanatics", "alt marketplace"
]

USE_GPT_OVERRIDE = True
DATA_FOLDER = "data"
SOURCE_PATHS = [os.path.join(DATA_FOLDER, f) for f in os.listdir(DATA_FOLDER) if f.endswith(".txt")]

# Utility functions
def hash_text(text):
    return hashlib.md5(text.strip().encode()).hexdigest()

def clean_text(text):
    text = re.sub(r"http\S+", "", text)  # remove URLs
    text = re.sub(r"[^\x00-\x7F]+", " ", text)  # remove non-ASCII/emojis
    return re.sub(r"\s+", " ", text).strip()

def is_high_signal(text):
    t = text.lower()
    if len(t) < 40:
        return False
    if any(noise in t for noise in NOISE_PHRASES):
        return False
    if any(required in t for required in REQUIRED_KEYWORDS):
        return True
    if USE_GPT_OVERRIDE:
        result = gpt_estimate_sentiment_subtag(text)
        return result.get("sentiment") != "Neutral" or result.get("impact", 1) >= 3
    return False

# Main loaders
def load_scraped_posts():
    insights = []
    for file_path in SOURCE_PATHS:
        if not os.path.exists(file_path):
            print(f"❌ Missing: {file_path}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        count = 0
        for line in lines:
            if is_high_signal(line):
                cleaned = clean_text(line)
                insights.append({
                    "post_id": hash_text(line),
                    "raw_text": line,
                    "text": cleaned,
                    "source": "twitter" if "twitter" in file_path.lower() else "reddit",
                    "source_file": file_path,
                    "char_count": len(line),
                    "type_tag": "Discussion"
                })
                count += 1

        print(f"✅ {count} high-signal posts from {file_path} ({round(100 * count / max(len(lines),1), 1)}%)")
    return insights

def process_insights(raw):
    return [enhance_insight(i) for i in raw if isinstance(i, dict) and i.get("text")]
