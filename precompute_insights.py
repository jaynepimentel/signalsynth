from utils.load_scraped_insights import load_scraped_posts, process_insights
from components.signal_scorer import filter_relevant_insights
import json

raw = load_scraped_posts()
processed = process_insights(raw)
scored = filter_relevant_insights(processed, min_score=3)

with open("precomputed_insights.json", "w", encoding="utf-8") as f:
    json.dump(scored, f, ensure_ascii=False, indent=2)

print(f"✅ Saved {len(scored)} precomputed insights")
