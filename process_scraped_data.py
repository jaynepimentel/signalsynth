#!/usr/bin/env python3
"""
process_scraped_data.py - Process scraped data through signal scorer and save to precomputed_insights.json
"""
import json
import os
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from components.signal_scorer import enrich_single_insight
from components.scoring_utils import detect_payments_upi_highasp, detect_competitor_and_partner_mentions

# Input files
SCRAPED_FILES = [
    "data/scraped_reddit_posts.json",
    "data/scraped_bluesky_posts.json",
    "data/scraped_ebay_forums.json",
    "data/scraped_community_posts.json",  # Main scraper output
    "data/all_scraped_posts.json",
]

OUTPUT_PATH = "precomputed_insights.json"


def load_scraped_data():
    """Load all scraped data from various sources."""
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
    
    return all_posts


def process_insight(post):
    """Process a single post through the signal scorer."""
    text = post.get("text", "")
    if not text or len(text) < 30:
        return None
    
    # Base insight
    insight = {
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
    
    # Enrich with signal scorer
    try:
        enriched = enrich_single_insight(insight)
        if enriched:
            # Add payment/UPI/high-ASP flags
            flags = detect_payments_upi_highasp(text)
            enriched["_payment_issue"] = flags.get("payment_issue", False)
            enriched["_upi_flag"] = flags.get("upi_flag", False)
            enriched["_high_end_flag"] = flags.get("high_asp_flag", False)
            enriched["payment_issue_types"] = flags.get("payment_types", [])
            
            # Add competitor/partner mentions
            mentions = detect_competitor_and_partner_mentions(text)
            enriched["mentions_competitor"] = mentions.get("competitors", [])
            enriched["mentions_ecosystem_partner"] = mentions.get("partners", [])
            
            return enriched
    except Exception as e:
        print(f"  ⚠️ Enrichment error: {e}")
    
    return None


def main():
    print("🔄 Processing scraped data into insights...")
    print()
    
    # Load all scraped data
    print("📥 Loading scraped data...")
    posts = load_scraped_data()
    print(f"\n📊 Total posts loaded: {len(posts)}")
    
    if not posts:
        print("❌ No scraped data found!")
        return
    
    # Process each post
    print("\n🔬 Enriching insights...")
    insights = []
    processed = 0
    skipped = 0
    
    for i, post in enumerate(posts):
        enriched = process_insight(post)
        if enriched:
            insights.append(enriched)
            processed += 1
        else:
            skipped += 1
        
        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(posts)}...")
    
    # Deduplicate by text
    seen = set()
    unique = []
    for insight in insights:
        text_hash = insight.get("text", "")[:150]
        if text_hash not in seen:
            seen.add(text_hash)
            unique.append(insight)
    
    print(f"\n✅ Processed: {processed}")
    print(f"⏭️ Skipped: {skipped}")
    print(f"🔄 Deduplicated: {len(insights)} → {len(unique)}")
    
    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Saved {len(unique)} insights to {OUTPUT_PATH}")
    
    # Summary stats
    payment_count = sum(1 for i in unique if i.get("_payment_issue"))
    upi_count = sum(1 for i in unique if i.get("_upi_flag"))
    high_asp_count = sum(1 for i in unique if i.get("_high_end_flag"))
    pg_count = sum(1 for i in unique if i.get("is_price_guide_signal"))
    
    print(f"\n📊 Signal breakdown:")
    print(f"  💳 Payment friction: {payment_count}")
    print(f"  ⚠️ UPI signals: {upi_count}")
    print(f"  💎 High-ASP: {high_asp_count}")
    print(f"  📊 Price Guide: {pg_count}")
    
    # Source breakdown
    sources = {}
    for i in unique:
        src = i.get("source", "Unknown")
        sources[src] = sources.get(src, 0) + 1
    
    print(f"\n📍 By source:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")


if __name__ == "__main__":
    main()
