# load_scraped_insights.py
import os

DATA_FILES = [
    "scraped_reddit_posts.txt",
    "scraped_community_posts.txt"
]

def load_scraped_posts():
    combined_posts = []
    for filename in DATA_FILES:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                combined_posts.extend(lines)
    return combined_posts

def process_insights(raw_posts):
    insights = []
    for text in raw_posts:
        source = "Reddit" if "reddit.com" in text else "Community"
        insights.append({
            "source": source,
            "text": text,
            "persona": "Buyer" if "buy" in text.lower() else "Seller",
            "cluster": [text],
            "ideas": [],
            "status": "Discovery",
            "team": "Triage",
            "last_updated": "2025-03-24"
        })
    return insights
