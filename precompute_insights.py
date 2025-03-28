# precompute_insights.py — deduplicated AI enrichment with keyword & journey tagging

import os
import json
import time
import argparse
import re
import hashlib
from collections import Counter
from dotenv import load_dotenv
from utils.load_scraped_insights import load_scraped_posts, process_insights
from components.signal_scorer import filter_relevant_insights
from components.trend_logger import log_insights_over_time

# Setup
load_dotenv()
os.environ["RUNNING_IN_STREAMLIT"] = "0"

PRECOMPUTED_PATH = "precomputed_insights.json"
TREND_LOG_PATH = "trend_log.jsonl"

# --- Utility functions ---
def log_step(msg):
    print(f"\n🟢 {msg} — {time.strftime('%H:%M:%S')}")

def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def show_diagnostics(insights):
    print("\n🔍 Diagnostic Summary:")
    brands = sorted(set(i.get("target_brand", "Unknown") for i in insights))
    types = sorted(set(i.get("type_tag", "Unknown") for i in insights))
    print(f"- Total new insights: {len(insights)}")
    print(f"- Brands mentioned: {', '.join(brands)}")
    print(f"- Types tagged: {', '.join(types)}")

def hash_insight(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

# --- Journey stage and title helpers ---
def generate_insight_title(text):
    return text.strip().capitalize()[:60] + "..." if len(text) > 60 else text.strip().capitalize()

def classify_journey_stage(text):
    text = text.lower()
    if any(x in text for x in ["search", "browse", "can't find", "filter", "looking for"]):
        return "Discovery"
    elif any(x in text for x in ["buy", "add to cart", "checkout", "purchase", "payment"]):
        return "Purchase"
    elif any(x in text for x in ["ship", "shipping", "tracking", "delivered", "delay", "package"]):
        return "Fulfillment"
    elif any(x in text for x in ["return", "refund", "problem", "issue", "feedback", "support", "bad experience"]):
        return "Post-Purchase"
    return "Unknown"

def enrich_titles_and_journey(insights):
    for i in insights:
        i["title"] = generate_insight_title(i["text"])
        i["journey_stage"] = classify_journey_stage(i["text"])
    return insights

# --- Trend keyword extraction ---
def extract_trend_keywords(text, top_k=5):
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    stopwords = set([
        "this", "that", "with", "have", "been", "from", "will", "they", "just",
        "like", "what", "when", "which", "should", "could", "would", "really",
        "still", "every", "where", "there", "because", "getting", "using"
    ])
    keywords = [w for w in words if w not in stopwords]
    top = [w for w, _ in Counter(keywords).most_common(top_k)]
    return top

def inject_keywords(insights):
    for i in insights:
        i["_trend_keywords"] = extract_trend_keywords(i.get("text", ""))
    return insights

# --- Main pipeline ---
def main(limit=None, dry_run=False):
    print("🧠 Mode: PRECOMPUTE with deduplication")
    key = os.getenv("OPENAI_API_KEY")
    print(f"🔑 OpenAI key loaded: {key[:6]}..." if key else "❌ Missing API key! GPT enrichment will fail.")

    # Step 1: Load scraped posts
    log_step("Loading raw scraped posts")
    raw = load_scraped_posts()
    print(f"📄 Loaded {len(raw)} raw posts")
    if limit:
        raw = raw[:limit]

    # Step 2: Clean and hash insights
    log_step("Preprocessing posts")
    processed = process_insights(raw)
    for i in processed:
        i["hash"] = hash_insight(i["text"])

    # Step 3: Load previously enriched insights
    log_step("Loading existing precomputed insights")
    if os.path.exists(PRECOMPUTED_PATH):
        with open(PRECOMPUTED_PATH, "r", encoding="utf-8") as f:
            try:
                previous = json.load(f)
                existing_hashes = set(i.get("hash") for i in previous if "hash" in i)
            except:
                previous = []
                existing_hashes = set()
    else:
        previous = []
        existing_hashes = set()

    new_only = [i for i in processed if i["hash"] not in existing_hashes]
    print(f"🆕 Found {len(new_only)} new posts to enrich")

    # Step 4: AI enrichment
    if not new_only:
        print("⚠️ No new insights to enrich. Exiting early.")
        return

    log_step("Scoring and enriching insights with AI")
    start = time.time()
    enriched = filter_relevant_insights(new_only, min_score=3)
    duration = round(time.time() - start, 2)
    print(f"✅ Enriched {len(enriched)} new insights in {duration}s")

    if not enriched:
        print("⚠️ No enriched insights passed the filter.")
        return

    # Step 5: Add titles, journey stages, and keywords
    log_step("Generating titles, journey stages, and keyword metadata")
    enriched = enrich_titles_and_journey(enriched)
    enriched = inject_keywords(enriched)

    # Diagnostics
    show_diagnostics(enriched)

    if dry_run:
        print("🧪 Dry run — skipping file write.")
        return

    # Step 6: Save combined file
    log_step(f"Saving enriched insights to {PRECOMPUTED_PATH}")
    combined = previous + enriched
    save_json(combined, PRECOMPUTED_PATH)

    # Step 7: Log to trend timeline
    log_step(f"Appending to {TREND_LOG_PATH}")
    log_insights_over_time(enriched)

    log_step(f"🎉 Done! {len(enriched)} new insights saved + logged.")

# Entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of posts processed")
    parser.add_argument("--dry-run", action="store_true", help="Skip saving to disk (use for debugging)")
    args = parser.parse_args()
    main(limit=args.limit, dry_run=args.dry_run)
