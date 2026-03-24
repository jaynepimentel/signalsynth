#!/usr/bin/env python3
"""
Scraper for additional forums and communities via RSS feeds and direct HTML.
No Google search dependency — uses RSS feeds, direct page scraping, and
feedparser for reliable, rate-limit-free data collection.

Sources:
- Sports Card Forum (sportscardforum.com) — RSS
- Freedom Cardboard (freedomcardboard.com) — RSS
- Beckett Message Boards (beckett.com/forums) — RSS
- Collectors Universe / PSA Forums (forums.collectors.com) — direct
- Cardboard Connection Forums — RSS
- PokeBeach Forums (pokebeach.com/forums) — RSS
- Sports Card Club (sportscardclub.com) — RSS
- Gold Card Auctions blog (goldcardauctions.com) — RSS
- ConsumerAffairs eBay reviews — direct
"""

import json
import os
import re
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Any

import requests
import feedparser

OUTPUT_PATH = "data/scraped_new_forums_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _fetch(url: str, timeout: int = 20) -> str:
    """Fetch a URL with error handling."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"    ⚠️ {e}")
        return ""


def _html_to_text(html: str, max_len: int = 2000) -> str:
    """Strip HTML tags, decode entities, clean whitespace."""
    if not html:
        return ""
    text = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]


def _parse_rss_feed(feed_url: str, source_name: str, max_items: int = 50) -> List[Dict[str, Any]]:
    """Parse an RSS/Atom feed and return normalized posts."""
    posts = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            # Get content from summary or content
            text = ""
            if hasattr(entry, "content") and entry.content:
                text = _html_to_text(entry.content[0].get("value", ""))
            elif hasattr(entry, "summary"):
                text = _html_to_text(entry.summary)
            if not text:
                text = title

            link = entry.get("link", "")
            published = entry.get("published", "") or entry.get("updated", "")
            # Try to parse date
            post_date = datetime.now().strftime("%Y-%m-%d")
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    post_date = time.strftime("%Y-%m-%d", entry.published_parsed)
                except Exception:
                    pass

            if len(text) < 30:
                continue

            posts.append({
                "text": text,
                "title": title,
                "source": source_name,
                "url": link,
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "score": 0,
                "num_comments": 0,
            })
    except Exception as e:
        print(f"    ⚠️ RSS parse error for {source_name}: {e}")
    return posts


# ─────────────────────────────────────────────
# RSS Feed sources
# ─────────────────────────────────────────────

RSS_FEEDS = {
    # Forums with RSS feeds
    "Sports Card Forum": [
        "https://www.sportscardforum.com/forums/-/index.rss",
    ],
    "Freedom Cardboard": [
        "https://www.freedomcardboard.com/forum/forums/-/index.rss",
    ],
    "Beckett Forums": [
        "https://www.beckett.com/forums/external?type=RSS2",
    ],
    "Cardboard Connection": [
        "https://www.cardboardconnection.com/feed",
    ],
    "PokeBeach": [
        "https://www.pokebeach.com/feed",
    ],
    "Sports Card Club": [
        "https://sportscardclub.com/forums/-/index.rss",
    ],
    "Gold Card Auctions": [
        "https://goldcardauctions.com/feed/",
    ],
    # Collectors Universe / PSA parent
    "Collectors Universe": [
        "https://forums.collectors.com/categories/sports-cards-memorabilia-forum.rss",
        "https://forums.collectors.com/categories/us-coins-forum.rss",
    ],
}


def scrape_rss_sources() -> List[Dict[str, Any]]:
    """Scrape all RSS feed sources."""
    all_posts = []
    for source_name, feed_urls in RSS_FEEDS.items():
        print(f"\n  📡 {source_name}")
        source_total = 0
        for feed_url in feed_urls:
            posts = _parse_rss_feed(feed_url, source_name)
            source_total += len(posts)
            all_posts.extend(posts)
        print(f"    ✅ {source_total} posts")
    return all_posts


# ─────────────────────────────────────────────
# Direct HTML scrapers (for sources without RSS)
# ─────────────────────────────────────────────

def scrape_consumer_affairs() -> List[Dict[str, Any]]:
    """Scrape ConsumerAffairs reviews for eBay and competitors."""
    posts = []
    pages = [
        ("https://www.consumeraffairs.com/online/ebay.html", "ConsumerAffairs:eBay"),
        ("https://www.consumeraffairs.com/online/ebay.html?page=2", "ConsumerAffairs:eBay"),
        ("https://www.consumeraffairs.com/online/ebay.html?page=3", "ConsumerAffairs:eBay"),
    ]

    for url, source in pages:
        print(f"    📄 {source} ({url})")
        html = _fetch(url)
        if not html:
            continue

        # Extract review blocks — ConsumerAffairs uses <div class="rvw-bd">
        review_blocks = re.findall(
            r'<div[^>]*class="[^"]*rvw-bd[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL | re.IGNORECASE
        )
        # Fallback: look for <p> blocks within review containers
        if not review_blocks:
            review_blocks = re.findall(
                r'<div[^>]*data-testid="review-content"[^>]*>(.*?)</div>',
                html, re.DOTALL | re.IGNORECASE
            )

        for block in review_blocks:
            text = _html_to_text(block)
            if len(text) < 50:
                continue
            posts.append({
                "text": text,
                "title": text[:100] + "..." if len(text) > 100 else text,
                "source": source,
                "url": url,
                "post_date": datetime.now().strftime("%Y-%m-%d"),
                "_logged_date": datetime.now().isoformat(),
                "score": 0,
                "num_comments": 0,
            })
        time.sleep(2)

    return posts


def scrape_collectors_universe_direct() -> List[Dict[str, Any]]:
    """Scrape Collectors Universe forums directly."""
    posts = []
    base_urls = [
        "https://forums.collectors.com/categories/sports-cards-memorabilia-forum",
        "https://forums.collectors.com/categories/buy-sell-trade-sports",
    ]

    for url in base_urls:
        print(f"    📄 {url}")
        html = _fetch(url)
        if not html:
            continue

        # Extract discussion titles and links
        # Pattern: <a href="/discussion/..." class="Title">
        discussions = re.findall(
            r'<a[^>]*href="(/discussion/[^"]+)"[^>]*class="[^"]*Title[^"]*"[^>]*>(.*?)</a>',
            html, re.IGNORECASE
        )

        for href, title_html in discussions[:30]:
            title = _html_to_text(title_html)
            full_url = f"https://forums.collectors.com{href}"

            # Fetch discussion page for content
            disc_html = _fetch(full_url)
            if not disc_html:
                continue

            # Extract first post content
            body_match = re.search(
                r'<div[^>]*class="[^"]*Message[^"]*"[^>]*>(.*?)</div>',
                disc_html, re.DOTALL | re.IGNORECASE
            )
            text = _html_to_text(body_match.group(1)) if body_match else title

            if len(text) < 50:
                continue

            posts.append({
                "text": text,
                "title": title,
                "source": "Collectors Universe",
                "url": full_url,
                "post_date": datetime.now().strftime("%Y-%m-%d"),
                "_logged_date": datetime.now().isoformat(),
                "score": 0,
                "num_comments": 0,
            })
            time.sleep(1)

    return posts


# ─────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────

def run_new_forums_scraper() -> List[Dict[str, Any]]:
    """Run all new forum scrapers."""
    all_posts = []

    print("=" * 60)
    print("🏛️  NEW FORUMS & COMMUNITIES SCRAPER")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Phase 1: RSS feeds (fast, reliable)
    print("\n── Phase 1: RSS Feeds ──")
    rss_posts = scrape_rss_sources()
    all_posts.extend(rss_posts)

    # Phase 2: Direct HTML scraping
    print("\n── Phase 2: Direct HTML Scraping ──")

    print("\n  📍 ConsumerAffairs Reviews")
    ca_posts = scrape_consumer_affairs()
    print(f"    ✅ {len(ca_posts)} reviews")
    all_posts.extend(ca_posts)

    print("\n  📍 Collectors Universe (direct)")
    cu_posts = scrape_collectors_universe_direct()
    print(f"    ✅ {len(cu_posts)} posts")
    all_posts.extend(cu_posts)

    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for post in all_posts:
        url = post.get("url", "")
        text_hash = hashlib.md5(post.get("text", "")[:200].encode()).hexdigest()
        key = url or text_hash
        if key in seen_urls:
            continue
        seen_urls.add(key)
        deduped.append(post)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"📊 SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total posts: {len(deduped)} (deduped from {len(all_posts)})")

    from collections import Counter
    src_counts = Counter(p.get("source", "?") for p in deduped)
    for src, cnt in src_counts.most_common():
        print(f"    {src}: {cnt}")

    # Save
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved to {OUTPUT_PATH}")

    return deduped


if __name__ == "__main__":
    run_new_forums_scraper()
