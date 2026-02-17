# scrape_blowout_indirect.py — Indirect Blowout Cards scraper
# Since blowoutforums.com is protected by Incapsula/Imperva bot protection,
# this scraper collects Blowout-related discussions from accessible sources:
#   1. Reddit (posts mentioning Blowout Cards/Forums)
#   2. Bluesky (posts mentioning Blowout)
#   3. Google News RSS (Blowout Cards news articles)

import requests
import json
import os
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Any
from urllib.parse import quote

SAVE_PATH = "data/scraped_blowout_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Reddit subreddits where Blowout Cards is commonly discussed
BLOWOUT_SUBREDDITS = [
    "baseballcards",
    "sportscards",
    "basketballcards",
    "footballcards",
    "hockeycards",
    "tradingcardcommunity",
    "PSAcard",
    "Flipping",
]

# Search queries to find Blowout-related content
BLOWOUT_SEARCH_QUERIES = [
    "blowout cards",
    "blowout forums",
    "blowoutcards",
    "blowoutforums",
    "blowout box break",
    "blowout case break",
]

# Bluesky search terms
BLUESKY_SEARCH_TERMS = [
    "blowout cards",
    "blowoutcards",
    "blowout forums",
    "blowout box break",
]


def _reddit_get(url: str, params: dict = None) -> dict:
    """Make a Reddit JSON API request with rate limiting."""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 60))
            print(f"  [RATE LIMITED] Waiting {wait}s...")
            time.sleep(wait)
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  [WARN] Reddit request failed: {e}")
    return {}


def scrape_reddit_blowout() -> List[Dict[str, Any]]:
    """Search Reddit for Blowout Cards mentions."""
    print("  Searching Reddit for Blowout Cards mentions...")
    posts = []
    seen_ids = set()

    # 1. Search across all of Reddit
    for query in BLOWOUT_SEARCH_QUERIES:
        url = "https://www.reddit.com/search.json"
        params = {
            "q": query,
            "sort": "new",
            "limit": 25,
            "t": "month",
        }
        data = _reddit_get(url, params)
        children = data.get("data", {}).get("children", [])

        for child in children:
            d = child.get("data", {})
            post_id = d.get("id", "")
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            text = d.get("selftext", "")
            title = d.get("title", "")
            combined = f"{title} {text}".lower()

            # Must actually mention blowout
            if not any(kw in combined for kw in ["blowout", "blowoutcards", "blowoutforums"]):
                continue

            posts.append({
                "text": text or title,
                "title": title,
                "source": "Reddit (Blowout mention)",
                "url": f"https://www.reddit.com{d.get('permalink', '')}",
                "username": d.get("author", "unknown"),
                "post_date": datetime.fromtimestamp(d.get("created_utc", 0)).strftime("%Y-%m-%d") if d.get("created_utc") else datetime.now().strftime("%Y-%m-%d"),
                "_logged_date": datetime.now().isoformat(),
                "subreddit": d.get("subreddit", ""),
                "search_term": query,
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "post_id": f"reddit_blowout_{post_id}",
                "_blowout_source": "reddit_search",
            })

        time.sleep(1.5)

    # 2. Search within specific subreddits
    for sub in BLOWOUT_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {
            "q": "blowout",
            "restrict_sr": "on",
            "sort": "new",
            "limit": 10,
            "t": "year",
        }
        data = _reddit_get(url, params)
        children = data.get("data", {}).get("children", [])

        for child in children:
            d = child.get("data", {})
            post_id = d.get("id", "")
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            text = d.get("selftext", "")
            title = d.get("title", "")

            posts.append({
                "text": text or title,
                "title": title,
                "source": "Reddit (Blowout mention)",
                "url": f"https://www.reddit.com{d.get('permalink', '')}",
                "username": d.get("author", "unknown"),
                "post_date": datetime.fromtimestamp(d.get("created_utc", 0)).strftime("%Y-%m-%d") if d.get("created_utc") else datetime.now().strftime("%Y-%m-%d"),
                "_logged_date": datetime.now().isoformat(),
                "subreddit": d.get("subreddit", ""),
                "search_term": "blowout",
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "post_id": f"reddit_blowout_{post_id}",
                "_blowout_source": "reddit_subreddit",
            })

        time.sleep(1.5)

    print(f"  Found {len(posts)} Reddit posts mentioning Blowout Cards")
    return posts


def scrape_bluesky_blowout() -> List[Dict[str, Any]]:
    """Search Bluesky for Blowout Cards mentions."""
    print("  Searching Bluesky for Blowout Cards mentions...")
    posts = []
    seen_uris = set()
    api_base = "https://public.api.bsky.app"

    for term in BLUESKY_SEARCH_TERMS:
        url = f"{api_base}/app.bsky.feed.searchPosts"
        params = {
            "q": term,
            "limit": 25,
            "sort": "latest",
        }
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue

            data = r.json()
            for item in data.get("posts", []):
                uri = item.get("uri", "")
                if uri in seen_uris:
                    continue
                seen_uris.add(uri)

                record = item.get("record", {})
                text = record.get("text", "")
                created = record.get("createdAt", "")

                # Must mention blowout
                if not any(kw in text.lower() for kw in ["blowout", "blowoutcards"]):
                    continue

                author = item.get("author", {})
                handle = author.get("handle", "unknown")

                # Parse date
                post_date = datetime.now().strftime("%Y-%m-%d")
                if created:
                    try:
                        post_date = datetime.fromisoformat(created.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                # Build web URL
                parts = uri.split("/")
                web_url = f"https://bsky.app/profile/{handle}/post/{parts[-1]}" if len(parts) > 0 else ""

                posts.append({
                    "text": text,
                    "title": "",
                    "source": "Bluesky (Blowout mention)",
                    "url": web_url,
                    "username": handle,
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "search_term": term,
                    "score": item.get("likeCount", 0),
                    "like_count": item.get("likeCount", 0),
                    "repost_count": item.get("repostCount", 0),
                    "post_id": f"bsky_blowout_{uri.split('/')[-1]}",
                    "_blowout_source": "bluesky_search",
                })

        except Exception as e:
            print(f"  [WARN] Bluesky search failed for '{term}': {e}")

        time.sleep(1.0)

    print(f"  Found {len(posts)} Bluesky posts mentioning Blowout Cards")
    return posts


def scrape_google_news_blowout() -> List[Dict[str, Any]]:
    """Fetch Blowout Cards news from Google News RSS."""
    print("  Fetching Blowout Cards news from Google News RSS...")
    posts = []

    queries = [
        "Blowout Cards",
        "Blowout Cards forum trading cards",
    ]

    for query in queries:
        encoded = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"  [WARN] Google News RSS returned {r.status_code} for '{query}'")
                continue

            root = ET.fromstring(r.content)
            channel = root.find("channel")
            if channel is None:
                continue

            for item in channel.findall("item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                description = item.findtext("description", "").strip()

                # Clean HTML from description
                description = re.sub(r"<[^>]+>", "", description).strip()

                # Parse date
                post_date = datetime.now().strftime("%Y-%m-%d")
                if pub_date:
                    try:
                        from email.utils import parsedate_to_datetime
                        post_date = parsedate_to_datetime(pub_date).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                text = f"{title}\n{description}" if description else title

                posts.append({
                    "text": text,
                    "title": title,
                    "source": "Google News (Blowout)",
                    "url": link,
                    "username": "news",
                    "post_date": post_date,
                    "_logged_date": datetime.now().isoformat(),
                    "search_term": query,
                    "score": 0,
                    "post_id": f"gnews_blowout_{hash(link) % 10**8}",
                    "_blowout_source": "google_news",
                })

        except Exception as e:
            print(f"  [WARN] Google News RSS failed for '{query}': {e}")

        time.sleep(1.0)

    print(f"  Found {len(posts)} Google News articles about Blowout Cards")
    return posts


def run_blowout_scraper() -> List[Dict[str, Any]]:
    """Run all indirect Blowout Cards scrapers and save results."""
    print("\n" + "=" * 50)
    print("🃏 BLOWOUT CARDS INDIRECT SCRAPER")
    print("  (via Reddit, Bluesky, Google News)")
    print("=" * 50)

    all_posts = []

    # Reddit
    try:
        reddit_posts = scrape_reddit_blowout()
        all_posts.extend(reddit_posts)
    except Exception as e:
        print(f"  [ERROR] Reddit Blowout scraper failed: {e}")

    # Bluesky
    try:
        bluesky_posts = scrape_bluesky_blowout()
        all_posts.extend(bluesky_posts)
    except Exception as e:
        print(f"  [ERROR] Bluesky Blowout scraper failed: {e}")

    # Google News
    try:
        news_posts = scrape_google_news_blowout()
        all_posts.extend(news_posts)
    except Exception as e:
        print(f"  [ERROR] Google News Blowout scraper failed: {e}")

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for post in all_posts:
        url = post.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique.append(post)

    # Sort by date
    unique.sort(key=lambda x: x.get("post_date", ""), reverse=True)

    # Save
    os.makedirs(os.path.dirname(SAVE_PATH) if os.path.dirname(SAVE_PATH) else ".", exist_ok=True)
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f"\n  Total Blowout posts: {len(unique)}")
    print(f"  Saved to: {SAVE_PATH}")
    return unique


if __name__ == "__main__":
    results = run_blowout_scraper()
    print(f"\nDone. {len(results)} posts collected.")
