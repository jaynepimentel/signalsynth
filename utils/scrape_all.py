# scrape_all.py — Master scraper that runs all sources and consolidates data
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any

# Import individual scrapers
try:
    from utils.scrape_reddit import run_reddit_scraper
except ImportError:
    from scrape_reddit import run_reddit_scraper

try:
    from utils.scrape_bluesky import run_bluesky_scraper
except ImportError:
    from scrape_bluesky import run_bluesky_scraper

try:
    from utils.scrape_ebay_forums import run_ebay_forums_scraper
except ImportError:
    from scrape_ebay_forums import run_ebay_forums_scraper

try:
    from utils.scrape_competitors import run_competitor_scraper
except ImportError:
    from scrape_competitors import run_competitor_scraper

try:
    from utils.scrape_cllct import run_cllct_scraper
except ImportError:
    from scrape_cllct import run_cllct_scraper

try:
    from utils.scrape_news_rss import run_news_rss_scraper
except ImportError:
    from scrape_news_rss import run_news_rss_scraper

try:
    from utils.scrape_blowout_indirect import run_blowout_scraper
except ImportError:
    from scrape_blowout_indirect import run_blowout_scraper

try:
    from utils.scrape_twitter import run_twitter_scraper
except ImportError:
    from scrape_twitter import run_twitter_scraper

try:
    from utils.scrape_youtube import run_youtube_scraper
except ImportError:
    from scrape_youtube import run_youtube_scraper

CONSOLIDATED_PATH = "data/all_scraped_posts.json"


def consolidate_posts(all_posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Consolidate and normalize posts from all sources."""
    
    # Ensure consistent schema
    normalized = []
    for post in all_posts:
        normalized.append({
            # Core fields
            "text": post.get("text", ""),
            "title": post.get("title", ""),
            "source": post.get("source", "Unknown"),
            "url": post.get("url", ""),
            "username": post.get("username", "unknown"),
            "post_date": post.get("post_date", datetime.now().strftime("%Y-%m-%d")),
            "_logged_date": post.get("_logged_date", datetime.now().isoformat()),
            
            # Source-specific metadata
            "subreddit": post.get("subreddit", ""),
            "forum_section": post.get("forum_section", ""),
            "search_term": post.get("search_term", ""),
            
            # Engagement metrics
            "score": post.get("score", 0),
            "like_count": post.get("like_count", 0),
            "repost_count": post.get("repost_count", 0),
            "num_comments": post.get("num_comments", 0),
            
            # IDs
            "post_id": post.get("post_id", ""),
        })
    
    return normalized


def deduplicate_posts(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate posts based on text similarity."""
    seen_text = set()
    seen_urls = set()
    unique = []
    
    for post in posts:
        text_hash = post.get("text", "")[:150].lower().strip()
        url = post.get("url", "")
        
        # Skip if we've seen this exact text or URL
        if text_hash and text_hash in seen_text:
            continue
        if url and url in seen_urls:
            continue
        
        if text_hash:
            seen_text.add(text_hash)
        if url:
            seen_urls.add(url)
        
        unique.append(post)
    
    return unique


def run_all_scrapers(
    include_reddit: bool = True,
    include_bluesky: bool = True,
    include_ebay_forums: bool = True,
    include_competitors: bool = True,
    include_cllct: bool = True,
    include_news_rss: bool = True,
    include_blowout: bool = True,
    include_twitter: bool = True,
    include_youtube: bool = True,
) -> List[Dict[str, Any]]:
    """Run all scrapers and consolidate results."""
    
    print("=" * 60)
    print("🚀 SIGNALSYNTH MASTER SCRAPER")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_posts = []
    source_counts = {}
    
    # Reddit
    if include_reddit:
        print("\n" + "=" * 40)
        print("📍 REDDIT")
        print("=" * 40)
        try:
            posts = run_reddit_scraper(include_comments=True, include_search=True)
            all_posts.extend(posts)
            source_counts["Reddit"] = len(posts)
        except Exception as e:
            print(f"❌ Reddit scraper failed: {e}")
            source_counts["Reddit"] = 0
    
    # Bluesky
    if include_bluesky:
        print("\n" + "=" * 40)
        print("📍 BLUESKY")
        print("=" * 40)
        try:
            posts = run_bluesky_scraper()
            all_posts.extend(posts)
            source_counts["Bluesky"] = len(posts)
        except Exception as e:
            print(f"❌ Bluesky scraper failed: {e}")
            source_counts["Bluesky"] = 0
    
    # eBay Forums
    if include_ebay_forums:
        print("\n" + "=" * 40)
        print("📍 EBAY FORUMS")
        print("=" * 40)
        try:
            posts = run_ebay_forums_scraper()
            all_posts.extend(posts)
            source_counts["eBay Forums"] = len(posts)
        except Exception as e:
            print(f"❌ eBay Forums scraper failed: {e}")
            source_counts["eBay Forums"] = 0
    
    # Competitors & Subsidiaries
    if include_competitors:
        print("\n" + "=" * 40)
        print("📍 COMPETITORS & SUBSIDIARIES")
        print("=" * 40)
        try:
            posts = run_competitor_scraper()
            all_posts.extend(posts)
            source_counts["Competitors"] = len(posts)
        except Exception as e:
            print(f"❌ Competitor scraper failed: {e}")
            source_counts["Competitors"] = 0
    
    # Cllct.com News
    if include_cllct:
        print("\n" + "=" * 40)
        print("📍 CLLCT.COM NEWS")
        print("=" * 40)
        try:
            posts = run_cllct_scraper()
            all_posts.extend(posts)
            source_counts["Cllct"] = len(posts)
        except Exception as e:
            print(f"❌ Cllct scraper failed: {e}")
            source_counts["Cllct"] = 0
    
    # RSS News Feeds (Beckett, Sports Collectors Daily, Cardlines, etc.)
    if include_news_rss:
        print("\n" + "=" * 40)
        print("📍 NEWS RSS FEEDS")
        print("=" * 40)
        try:
            posts = run_news_rss_scraper()
            all_posts.extend(posts)
            source_counts["News RSS"] = len(posts)
        except Exception as e:
            print(f"❌ News RSS scraper failed: {e}")
            source_counts["News RSS"] = 0
    
    # Twitter/X (via Google News indexed tweets)
    if include_twitter:
        print("\n" + "=" * 40)
        print("\U0001f4cd TWITTER/X")
        print("=" * 40)
        try:
            posts = run_twitter_scraper()
            all_posts.extend(posts)
            source_counts["Twitter/X"] = len(posts)
        except Exception as e:
            print(f"\u274c Twitter/X scraper failed: {e}")
            source_counts["Twitter/X"] = 0
    
    # YouTube (transcripts + comments)
    if include_youtube:
        print("\n" + "=" * 40)
        print("\U0001f3ac YOUTUBE")
        print("=" * 40)
        try:
            posts = run_youtube_scraper()
            all_posts.extend(posts)
            source_counts["YouTube"] = len(posts)
        except Exception as e:
            print(f"\u274c YouTube scraper failed: {e}")
            source_counts["YouTube"] = 0
    
    # Blowout Cards (indirect via Reddit, Bluesky, Google News)
    if include_blowout:
        print("\n" + "=" * 40)
        print("📍 BLOWOUT CARDS (INDIRECT)")
        print("=" * 40)
        try:
            posts = run_blowout_scraper()
            all_posts.extend(posts)
            source_counts["Blowout (indirect)"] = len(posts)
        except Exception as e:
            print(f"❌ Blowout indirect scraper failed: {e}")
            source_counts["Blowout (indirect)"] = 0
    
    # Consolidate and deduplicate
    print("\n" + "=" * 40)
    print("📊 CONSOLIDATING RESULTS")
    print("=" * 40)
    
    normalized = consolidate_posts(all_posts)
    unique = deduplicate_posts(normalized)
    
    # Sort by date (newest first)
    unique.sort(key=lambda x: x.get("post_date", ""), reverse=True)
    
    # Save consolidated file
    os.makedirs(os.path.dirname(CONSOLIDATED_PATH) if os.path.dirname(CONSOLIDATED_PATH) else ".", exist_ok=True)
    with open(CONSOLIDATED_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    # Summary
    print("\n" + "=" * 60)
    print("📈 SCRAPING SUMMARY")
    print("=" * 60)
    print(f"\n📊 Posts by source:")
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count:,}")
    
    print(f"\n📦 Total raw posts: {len(all_posts):,}")
    print(f"✅ Unique posts after dedup: {len(unique):,}")
    print(f"💾 Saved to: {CONSOLIDATED_PATH}")
    
    # Date range
    if unique:
        dates = [p.get("post_date", "") for p in unique if p.get("post_date")]
        if dates:
            print(f"📅 Date range: {min(dates)} to {max(dates)}")
    
    print("\n" + "=" * 60)
    print("✅ SCRAPING COMPLETE")
    print("=" * 60)
    
    return unique


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SignalSynth Master Scraper")
    parser.add_argument("--no-reddit", action="store_true", help="Skip Reddit scraping")
    parser.add_argument("--no-bluesky", action="store_true", help="Skip Bluesky scraping")
    parser.add_argument("--no-ebay", action="store_true", help="Skip eBay Forums scraping")
    parser.add_argument("--no-cllct", action="store_true", help="Skip Cllct.com scraping")
    parser.add_argument("--no-news-rss", action="store_true", help="Skip RSS news feeds scraping")
    parser.add_argument("--no-blowout", action="store_true", help="Skip Blowout Cards indirect scraping")
    parser.add_argument("--no-twitter", action="store_true", help="Skip Twitter/X scraping")
    parser.add_argument("--no-youtube", action="store_true", help="Skip YouTube scraping")
    
    args = parser.parse_args()
    
    run_all_scrapers(
        include_reddit=not args.no_reddit,
        include_bluesky=not args.no_bluesky,
        include_ebay_forums=not args.no_ebay,
        include_cllct=not args.no_cllct,
        include_news_rss=not args.no_news_rss,
        include_blowout=not args.no_blowout,
        include_twitter=not args.no_twitter,
        include_youtube=not args.no_youtube,
    )
