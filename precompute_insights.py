# precompute_insights.py — clean mode logging + enrichment cache builder
import os
import json
import time
from utils.load_scraped_insights import load_scraped_posts, process_insights
from components.signal_scorer import filter_relevant_insights
from components.trend_logger import log_insights_over_time
from dotenv import load_dotenv

load_dotenv()
os.environ["RUNNING_IN_STREAMLIT"] = "0"  # ✅ GPT-safe mode for enrichment

def log_step(msg):
    print(f"\n🟢 {msg} — {time.strftime('%H:%M:%S')}")

# Show OpenAI key check
key = os.getenv("OPENAI_API_KEY")
if key:
    print(f"🔑 OpenAI key loaded: {key[:6]}... (safe mode)")
else:
    print("❌ Missing OpenAI API key! Enrichment will fail.")

print("🧠 Mode: PRECOMPUTE (GPT calls ENABLED)")

# Step 1: Load raw scraped posts
log_step("Loading raw scraped posts")
raw = load_scraped_posts()
print(f"📄 Loaded {len(raw)} raw posts")

# Step 2: Process raw posts
log_step("Preprocessing posts")
processed = process_insights(raw)

# Step 3: Run AI enrichment (PM ideas, tagging, scoring)
log_step("Scoring and enriching insights with AI")
start = time.time()
filtered = filter_relevant_insights(processed, min_score=3)
print(f"✅ Enriched {len(filtered)} insights in {round(time.time() - start, 2)}s")

# Step 4: Save results for Streamlit app to load
log_step("Saving results to precomputed_insights.json")
with open("precomputed_insights.json", "w", encoding="utf-8") as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)

# Step 5: Log to trend timeline for dashboards
log_step("Appending to trend_log.jsonl")
log_insights_over_time(filtered)

log_step(f"🎉 Done! {len(filtered)} total insights enriched + saved + logged.")
