#!/usr/bin/env python3
"""
process_scraped_data_light.py — Lightweight processing with ZERO GPT API calls.

Uses only:
  - Local RoBERTa sentiment classifier (cardiffnlp/twitter-roberta-base-sentiment)
  - Local e5-base-v2 semantic scoring
  - Regex detectors (payments, UPI, liquidity, competitors, topics)
  - SimHash deduplication

Skips: gpt_estimate_sentiment_subtag, enrich_with_gpt_tags, generate_pm_ideas
"""
import json
import os
import sys
import re
import hashlib
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Local-only imports (no GPT) ──
from components.scoring_utils import (
    detect_payments_upi_highasp,
    detect_competitor_and_partner_mentions,
    detect_liquidity_signals,
    estimate_severity,
    calculate_pm_priority,
    infer_clarity,
    generate_insight_title,
    tag_topic_focus,
    classify_opportunity_type,
    classify_action_type,
    calculate_cluster_ready_score,
)
from components.brand_recognizer import recognize_brand

# ── Load local models ──
print("Loading local models (no GPT)...")

# Sentiment model (RoBERTa)
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from scipy.special import softmax

SENT_MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment"
sent_tokenizer = AutoTokenizer.from_pretrained(SENT_MODEL_NAME)
sent_model = AutoModelForSequenceClassification.from_pretrained(SENT_MODEL_NAME)

# NOTE: e5-base-v2 semantic scoring skipped in light mode (too slow per-post on CPU).
# Embeddings are precomputed separately via: python -m components.hybrid_retrieval

HEURISTIC_KEYWORDS = {
    "scam": 8, "fraud": 8, "trust issue": 10, "bid cancel": 10,
    "auction integrity": 12, "cancelled bid": 8, "high bid pulled": 10,
    "counterfeit": 10, "authentication error": 10, "return fraud": 10,
}

# Keyword subtag map (from enhanced_classifier.py)
SUBTAG_MAP = {
    "delay": "Delays", "scam": "Fraud Concern", "slow": "Speed Issue",
    "authentication": "Trust Issue", "refund": "Refund Issue", "tracking": "Tracking Confusion",
    "fees": "Fee Frustration", "grading": "Grading Complaint", "shipping": "Shipping Concern",
    "vault": "Vault Friction", "fake": "Counterfeit Concern", "pop report": "Comps/Valuation",
    "turnaround": "Speed Issue", "verification": "Trust Issue",
    "instant offer": "Instant Offers", "buyback": "Instant Offers", "buy back": "Instant Offers",
    "cash out": "Liquidity", "liquidat": "Liquidity", "sell now": "Liquidity",
    "quick flip": "Liquidity", "psa offers": "Instant Offers", "courtyard": "Liquidity Platform",
    "arena club": "Liquidity Platform", "free up funds": "Liquidity", "reinvest": "Liquidity",
}

# Vault friction signals — these override sentiment to Complaint even if RoBERTa says Praise/Neutral
VAULT_FRICTION_PHRASES = [
    "vault isn't working", "vault not working", "vault issue", "vault problem",
    "stuck in vault", "can't withdraw", "vault withdraw", "vault transfer",
    "vault to vault", "psa vault to psa vault", "vault to psa",
    "in-gate", "ingate", "in gate", "in-gated", "vault sell",
    "vault payout", "vault shipping", "vault locked", "vault delay",
    "not being able to select", "not being able to keep",
    "app isn't working", "app not working", "app isn't working fully",
    "mobile app isn't working", "mobile app not working",
    "current issues with ebay", "wait for it to be in",
    "business days for cards to transfer", "original method is restored",
    "no way to transfer", "managed to mess up",
    "ship the card out of their warehouse back to themselves",
    "shipped back to themselves", "wait for it to be in-gated",
]

print("Models loaded.\n")

# ── Input/Output ──
SCRAPED_FILES = [
    "data/scraped_reddit_posts.json",
    "data/scraped_bluesky_posts.json",
    "data/scraped_ebay_forums.json",
    "data/scraped_community_posts.json",
    "data/all_scraped_posts.json",
]
OUTPUT_PATH = "precomputed_insights.json"


def classify_sentiment_local(text: str) -> dict:
    """Classify sentiment using local RoBERTa — no GPT."""
    try:
        encoded = sent_tokenizer(text, return_tensors='pt', truncation=True, padding=True, max_length=512)
        with torch.no_grad():
            output = sent_model(**encoded)
            scores = softmax(output.logits[0].numpy())
            labels = ["Negative", "Neutral", "Positive"]
            label = labels[scores.argmax()]
            confidence = round(float(scores.max()) * 100, 2)
        sentiment = {"Positive": "Praise", "Negative": "Complaint", "Neutral": "Neutral"}.get(label, "Neutral")
        return {"sentiment": sentiment, "confidence": confidence}
    except Exception:
        return {"sentiment": "Neutral", "confidence": 0}


def detect_subtags_local(text: str) -> list:
    """Keyword-based subtag detection — no GPT."""
    found = set()
    lo = text.lower()
    for key, label in SUBTAG_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", lo):
            found.add(label)
    return list(found) if found else ["General"]


def score_heuristic(text: str) -> int:
    lo = text.lower()
    return sum(v for k, v in HEURISTIC_KEYWORDS.items() if k in lo)


def enrich_light(post: dict) -> dict | None:
    """Full enrichment with zero GPT calls."""
    text = post.get("text", "")
    if not text or len(text.strip()) < 30:
        return None

    i = {
        "text": text,
        "title": post.get("title", ""),
        "source": post.get("source", "Unknown"),
        "url": post.get("url", ""),
        "post_date": post.get("post_date", datetime.now().strftime("%Y-%m-%d")),
        "_logged_date": post.get("_logged_date", datetime.now().isoformat()),
        "subreddit": post.get("subreddit", ""),
        "forum_section": post.get("forum_section", ""),
        "username": post.get("username", ""),
        "score": post.get("score", 0),
        "num_comments": post.get("num_comments", 0),
    }

    # Local sentiment
    sent = classify_sentiment_local(text)
    i["brand_sentiment"] = sent["sentiment"]
    i["sentiment_confidence"] = sent["confidence"]

    # Override: vault friction signals should always be Complaint
    lo = text.lower()
    _is_vault_friction = any(phrase in lo for phrase in VAULT_FRICTION_PHRASES)
    if _is_vault_friction and i["brand_sentiment"] != "Complaint":
        i["brand_sentiment"] = "Complaint"
        i["_vault_override"] = True

    # Brand detection (regex)
    i["target_brand"] = recognize_brand(text.lower())

    # Subtags (keyword) — vault friction takes priority over refund
    subtags = detect_subtags_local(text)
    if _is_vault_friction and "Vault Friction" not in subtags:
        subtags = ["Vault Friction"] + [s for s in subtags if s != "Refund Issue"]
    i["type_subtags"] = subtags
    i["type_subtag"] = subtags[0]

    # Heuristic scoring only (semantic scoring done later via precomputed embeddings)
    heuristic = score_heuristic(text)
    i["semantic_score"] = 0.0
    i["heuristic_score"] = heuristic

    # Default frustration/impact (would normally come from GPT)
    frustration = 3 if (sent["sentiment"] == "Complaint" or _is_vault_friction) else 1
    impact = 2
    i["frustration"] = frustration
    i["impact"] = impact
    i["score"] = round((0.3 * heuristic) + (0.1 * frustration * 10) + (0.1 * impact * 10) + (sent["confidence"] * 0.3), 2)

    # Severity (regex-based)
    severity, reason = estimate_severity(text)
    i["severity_score"] = severity
    i["severity_reason"] = reason
    i["frustration_flag"] = severity >= 85
    i["pm_priority_score"] = calculate_pm_priority(i)

    # GPT placeholders
    i["gpt_sentiment"] = None
    i["gpt_subtags"] = None
    i["pm_summary"] = ""
    i["ideas"] = []
    i["effort"] = "Unknown"
    i["shovel_ready"] = frustration >= 4 and impact >= 3

    # Persona (simple heuristic)
    lo = text.lower()
    if any(w in lo for w in ["seller", "selling", "listed", "my listing"]):
        i["persona"] = "Seller"
    elif any(w in lo for w in ["buyer", "bought", "purchased", "won auction"]):
        i["persona"] = "Buyer"
    elif any(w in lo for w in ["collector", "collection", "graded", "psa", "bgs"]):
        i["persona"] = "Collector"
    else:
        i["persona"] = "General"

    # Regex detectors
    mentions = detect_competitor_and_partner_mentions(text)
    i["mentions_competitor"] = mentions.get("competitors", [])
    i["mentions_ecosystem_partner"] = mentions.get("partners", [])
    i["mentions"] = mentions

    flags = detect_payments_upi_highasp(text)
    i["_payment_issue"] = flags.get("_payment_issue", False)
    i["_upi_flag"] = flags.get("_upi_flag", False)
    i["_high_end_flag"] = flags.get("_high_end_flag", False)
    i["payment_issue_types"] = flags.get("payment_issue_types", [])

    liq = detect_liquidity_signals(text)
    i["_liquidity_signal"] = liq.get("_liquidity_signal", False)
    i["liquidity_signal_types"] = liq.get("liquidity_signal_types", [])
    i["liquidity_platforms"] = liq.get("liquidity_platforms", [])

    i["action_type"] = classify_action_type(text)
    i["topic_focus"] = tag_topic_focus(text)
    i["journey_stage"] = "Discovery"
    i["clarity"] = infer_clarity(text)
    i["title"] = generate_insight_title(text)
    i["opportunity_tag"] = classify_opportunity_type(text)

    # Payment/liquidity promotions
    topic = list(i["topic_focus"])
    if i["_payment_issue"] and "Payments" not in topic:
        topic.append("Payments")
    if i["_upi_flag"] and "UPI" not in topic:
        topic.append("UPI")
    if i["_liquidity_signal"] and "Instant Offers / Liquidity" not in topic:
        topic.append("Instant Offers / Liquidity")
    i["topic_focus"] = topic

    # Taxonomy (normalized)
    type_tag = "Complaint" if sent["sentiment"] == "Complaint" else "Discussion"
    if any(w in lo for w in ["wish", "should", "would be great", "please add", "feature request"]):
        type_tag = "Feature Request"
    if any(w in lo for w in ["leaving ebay", "switched to", "done with ebay", "moving to"]):
        type_tag = "Churn Signal"
    if _is_vault_friction:
        type_tag = "Complaint"
    i["type_tag"] = type_tag
    i["type_confidence"] = sent["confidence"]

    canonical_topic = subtags[0] if subtags[0] != "General" else (topic[0] if topic else "General")
    i["taxonomy"] = {"type": type_tag, "topic": canonical_topic, "theme": canonical_topic}
    i["subtag"] = canonical_topic
    i["theme"] = canonical_topic

    i["cluster_ready_score"] = calculate_cluster_ready_score(i["score"], frustration, impact)
    i["fingerprint"] = hashlib.md5(text.lower().encode()).hexdigest()

    # Min score filter
    return i if i["score"] >= 3 else None


def main():
    print("🔄 Processing scraped data (LIGHT mode — no GPT calls)...\n")

    print("📥 Loading scraped data...")
    all_posts = []
    for path in SCRAPED_FILES:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        print(f"  📂 {path}: {len(data)} posts")
                        all_posts.extend(data)
            except Exception as e:
                print(f"  ⚠️ {path}: {e}")

    print(f"\n📊 Total posts loaded: {len(all_posts)}")
    if not all_posts:
        print("❌ No scraped data found!")
        return

    # Fast exact-prefix dedup (O(n), handles 26K+ posts instantly)
    print("\n🔄 Deduplicating raw posts...")
    before = len(all_posts)
    seen = set()
    unique = []
    for p in all_posts:
        key = (p.get("text", "") or "").strip()[:200].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    all_posts = unique
    print(f"  {before} → {len(all_posts)} ({before - len(all_posts)} exact dupes removed)")

    # Enrich
    print(f"\n🔬 Enriching {len(all_posts)} posts (local only)...")
    insights = []
    errors = 0
    for idx, post in enumerate(all_posts):
        try:
            enriched = enrich_light(post)
            if enriched:
                insights.append(enriched)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ⚠️ Error at {idx}: {e}")

        if (idx + 1) % 500 == 0:
            print(f"  {idx + 1}/{len(all_posts)} processed ({len(insights)} enriched)...", flush=True)

    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done: {len(insights)} insights saved to {OUTPUT_PATH}")
    print(f"  Errors: {errors}")
    print(f"  Pass rate: {len(insights) / max(len(all_posts), 1):.1%}")

    # Quick stats
    sources = defaultdict(int)
    sentiments = defaultdict(int)
    for i in insights:
        sources[i.get("source", "Unknown")] += 1
        sentiments[i.get("brand_sentiment", "Neutral")] += 1

    print(f"\n📊 Sentiment: {dict(sentiments)}")
    print(f"📍 Sources:")
    for src, cnt in sorted(sources.items(), key=lambda x: -x[1])[:10]:
        print(f"  {src}: {cnt}")

    # Save pipeline meta
    meta = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "mode": "light",
        "total_posts_loaded": len(all_posts),
        "insights_generated": len(insights),
        "errors": errors,
    }
    with open("_pipeline_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    main()
