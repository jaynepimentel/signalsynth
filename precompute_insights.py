# precompute_insights.py — now with clarity tagging, sentiment stats, and GPT diagnostics

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

load_dotenv()
os.environ["RUNNING_IN_STREAMLIT"] = "0"

PRECOMPUTED_PATH = "precomputed_insights.json"
TREND_LOG_PATH = "trend_log.jsonl"
CLUSTER_CACHE_PATH = "precomputed_clusters.json"

def log_step(msg):
    print(f"\n🟢 {msg} — {time.strftime('%H:%M:%S')}")

def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def show_diagnostics(insights):
    print("\n🔍 Diagnostic Summary:")
    print(f"- Total new insights: {len(insights)}")
    print(f"- Avg PM Priority: {round(sum(i.get('pm_priority_score', 0) for i in insights)/len(insights), 2)}")
    print(f"- Top Complaint Tag: {top_complaint_tag(insights)}")
    print(f"- Sentiment Breakdown: {Counter(i.get('brand_sentiment') for i in insights)}")
    print(f"- Journey stages: {Counter(i.get('journey_stage') for i in insights)}")

def top_complaint_tag(insights):
    tags = [i.get("type_subtag", "General") for i in insights if i.get("brand_sentiment") == "Complaint"]
    return Counter(tags).most_common(1)[0][0] if tags else "N/A"

def hash_insight(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()

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

def infer_clarity(text):
    text = text.strip().lower()
    if len(text) < 40 or "???" in text or "idk" in text or "confused" in text:
        return "Needs Clarification"
    return "Clear"

def enrich_titles_and_journey(insights):
    for i in insights:
        i["title"] = generate_insight_title(i["text"])
        i["journey_stage"] = classify_journey_stage(i["text"])
        i["clarity"] = infer_clarity(i["text"])
    return insights

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

def main(limit=None, dry_run=False):
    print("🧠 Mode: PRECOMPUTE + Signal Enrichment")
    key = os.getenv("OPENAI_API_KEY")
    print(f"🔑 OpenAI key loaded: {key[:6]}..." if key else "❌ Missing API key!")

    log_step("Loading raw scraped posts")
    raw = load_scraped_posts()
    print(f"📄 Loaded {len(raw)} raw posts")
    if limit:
        raw = raw[:limit]

    log_step("Preprocessing posts")
    processed = process_insights(raw)
    for i in processed:
        i["hash"] = hash_insight(i["text"])

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
    print(f"🆕 Found {len(new_only)} new posts")

    if not new_only:
        print("⚠️ No new insights to enrich. Exiting.")
        return

    log_step("Scoring and enriching insights")
    start = time.time()
    enriched = filter_relevant_insights(new_only, min_score=3)
    duration = round(time.time() - start, 2)
    print(f"✅ Enriched {len(enriched)} insights in {duration}s")

    if not enriched:
        print("⚠️ No insights passed enrichment filter.")
        return

    log_step("Adding titles, clarity, journey stages, and keywords")
    enriched = enrich_titles_and_journey(enriched)
    enriched = inject_keywords(enriched)

    show_diagnostics(enriched)

    if dry_run:
        print("🧪 Dry run complete. Insights preview:")
        for e in enriched[:5]:
            print(f"- {e['title']} [{e.get('type_tag')}] — {e.get('clarity')}")
        return

    log_step("Saving enriched insights")
    combined = previous + enriched
    save_json(combined, PRECOMPUTED_PATH)

    log_step("Appending to trend timeline")
    log_insights_over_time(enriched)

    if os.path.exists(CLUSTER_CACHE_PATH):
        os.remove(CLUSTER_CACHE_PATH)
        print(f"🧹 Cleared cluster cache")

    log_step(f"🎉 Done! {len(enriched)} new insights processed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of posts processed")
    parser.add_argument("--dry-run", action="store_true", help="Skip saving to disk (debug mode)")
    args = parser.parse_args()
    main(limit=args.limit, dry_run=args.dry_run)
