# precompute_insights.py — upgraded modular pipeline with logging, flags, and validation

import os
import json
import time
import argparse
from dotenv import load_dotenv
from utils.load_scraped_insights import load_scraped_posts, process_insights
from components.signal_scorer import filter_relevant_insights
from components.trend_logger import log_insights_over_time

# Setup
load_dotenv()
os.environ["RUNNING_IN_STREAMLIT"] = "0"

PRECOMPUTED_PATH = "precomputed_insights.json"
TREND_LOG_PATH = "trend_log.jsonl"

def log_step(msg):
    print(f"\n🟢 {msg} — {time.strftime('%H:%M:%S')}")

def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def show_diagnostics(insights):
    print("\n🔍 Diagnostic Summary:")
    brands = sorted(set(i.get("target_brand", "Unknown") for i in insights))
    types = sorted(set(i.get("type_tag", "Unknown") for i in insights))
    print(f"- Total insights: {len(insights)}")
    print(f"- Brands mentioned: {', '.join(brands)}")
    print(f"- Types tagged: {', '.join(types)}")

def main(limit=None, dry_run=False):
    print("🧠 Mode: PRECOMPUTE (GPT calls ENABLED)")
    key = os.getenv("OPENAI_API_KEY")
    print(f"🔑 OpenAI key loaded: {key[:6]}..." if key else "❌ Missing API key! GPT enrichment will fail.")

    # Step 1: Load scraped posts
    log_step("Loading raw scraped posts")
    raw = load_scraped_posts()
    print(f"📄 Loaded {len(raw)} raw posts")
    if limit:
        raw = raw[:limit]

    # Step 2: Clean + prep
    log_step("Preprocessing posts")
    processed = process_insights(raw)

    # Step 3: Enrich via AI
    log_step("Scoring and enriching insights with AI")
    start = time.time()
    enriched = filter_relevant_insights(processed, min_score=3)
    duration = round(time.time() - start, 2)
    print(f"✅ Enriched {len(enriched)} insights in {duration}s")

    if not enriched:
        print("⚠️ No enriched insights passed the filter. Exiting early.")
        return

    # Diagnostics
    show_diagnostics(enriched)

    if dry_run:
        print("🧪 Dry run — skipping file write.")
        return

    # Step 4: Save JSON
    log_step(f"Saving enriched insights to {PRECOMPUTED_PATH}")
    save_json(enriched, PRECOMPUTED_PATH)

    # Step 5: Append to trend timeline
    log_step(f"Appending to {TREND_LOG_PATH}")
    log_insights_over_time(enriched)

    log_step(f"🎉 Done! {len(enriched)} insights saved + logged.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of posts processed")
    parser.add_argument("--dry-run", action="store_true", help="Skip saving to disk (use for debugging)")
    args = parser.parse_args()
    main(limit=args.limit, dry_run=args.dry_run)