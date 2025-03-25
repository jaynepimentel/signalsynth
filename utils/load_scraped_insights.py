# utils/load_scraped_insights.py

import os

def load_scraped_posts():
    path = "data/scraped_community_posts.txt"
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    insights = []
    for line in lines:
        insights.append({
            "text": line,
            "source": "reddit",
            "type_tag": "Discussion",  # default until scored
        })

    return insights

def process_insights(insights):
    # Placeholder in case you want to add cleaning logic later
    return insights
