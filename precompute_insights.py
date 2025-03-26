# precompute_insights.py — now with granular progress logging
import os
import json
import time
from utils.load_scraped_insights import load_scraped_posts, process_insights
from components.signal_scorer import filter_relevant_insights
from components.trend_logger import log_insights_over_time
from dotenv import load_dotenv
load_dotenv()
print("🔑 OPENAI key loaded:", os.getenv("OPENAI_API_KEY")[:6] if os.getenv("OPENAI_API_KEY") else "❌ Missing")


os.environ["RUNNING_IN_STREAMLIT"] = "0"

def log_step(msg):
    print(f"\n🟢 {msg} — {time.strftime('%H:%M:%S')}")

# Step 1: Load raw scraped posts
log_step("Loading raw scraped posts")
raw = load_scraped_posts()
print(f"Loaded {len(raw)} raw posts")

# Step 2: Process posts
log_step("Preprocessing posts")
processed = process_insights(raw)

# Step 3: AI scoring + enrichment
log_step("Scoring and enriching insights with AI")
start = time.time()
filtered = filter_relevant_insights(processed, min_score=3)
print(f"Enriched {len(filtered)} insights in {round(time.time() - start, 2)} seconds")

# Step 4: Save results
log_step("Saving to precomputed_insights.json")
with open("precomputed_insights.json", "w", encoding="utf-8") as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)

# Step 5: Append to trend log
log_step("Logging insights to trend_log.jsonl")
log_insights_over_time(filtered)

log_step(f"✅ Done! {len(filtered)} total insights enriched + logged")
