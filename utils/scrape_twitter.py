# scrape_twitter.py — Twitter/X scraper via Google News RSS indexing
# Twitter's guest token API and GraphQL endpoints are dead as of late 2024.
# This scraper pulls indexed tweets from Google News RSS (site:x.com queries),
# which reliably captures public tweets about collectibles topics.

import requests
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

# Search queries — "site:x.com" restricts Google to indexed tweets
SEARCH_QUERIES = [
    "site:x.com ebay collectibles",
    "site:x.com ebay trading cards",
    "site:x.com ebay vault",
    "site:x.com ebay authentication guarantee",
    "site:x.com psa grading cards",
    "site:x.com goldin auctions",
    "site:x.com fanatics collect",
    "site:x.com sports cards graded",
    "site:x.com ebay seller shipping",
]

# Known collectibles accounts to pull timelines from
TWITTER_ACCOUNTS = [
    "eBay",
    "PSAcard",
    "GoldinCo",
    "Aborotics",
    "CardPurchaser",
]

SAVE_PATH = "data/scraped_twitter_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_google_news_rss(rss_url: str, search_term: str) -> list:
    """Fetch and parse a Google News RSS feed, extracting tweet-like content."""
    posts = []
    try:
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return posts

        root = ET.fromstring(r.content)
        channel = root.find("channel")
        if channel is None:
            return posts

        for item in channel.findall("item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            description = item.findtext("description", "").strip()

            # Clean HTML from description
            description = re.sub(r"<[^>]+>", "", description).strip()

            # Extract username from x.com or twitter.com URLs
            username = "unknown"
            url_match = re.search(r"(?:x\.com|twitter\.com)/(\w+)", link)
            if url_match:
                username = url_match.group(1)

            # Parse date
            post_date = datetime.now().strftime("%Y-%m-%d")
            if pub_date:
                try:
                    from email.utils import parsedate_to_datetime
                    post_date = parsedate_to_datetime(pub_date).strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Build text — title often IS the tweet text for x.com results
            text = title
            if description and description != title:
                text = f"{title}\n{description}"

            # Skip very short or non-tweet content
            if len(text) < 20:
                continue

            posts.append({
                "text": text,
                "title": title,
                "source": "Twitter/X",
                "url": link,
                "username": username,
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": search_term,
                "score": 0,
                "like_count": 0,
                "repost_count": 0,
                "post_id": f"twitter_{hash(link) % 10**8}",
            })

    except Exception as e:
        print(f"  [WARN] RSS parse failed for '{search_term}': {e}")

    return posts


def scrape_twitter_search() -> list:
    """Search for tweets via Google News RSS (site:x.com)."""
    print("  Searching Google News for indexed tweets...")
    all_posts = []

    for query in SEARCH_QUERIES:
        encoded = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        posts = _parse_google_news_rss(rss_url, query)
        all_posts.extend(posts)
        print(f"    '{query}': {len(posts)} tweets")
        time.sleep(1.0)

    return all_posts


def scrape_twitter_accounts() -> list:
    """Pull indexed tweets from specific accounts via Google News."""
    print("  Fetching indexed tweets from known accounts...")
    all_posts = []

    for account in TWITTER_ACCOUNTS:
        query = f"site:x.com/{account}"
        encoded = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        posts = _parse_google_news_rss(rss_url, f"@{account}")
        all_posts.extend(posts)
        print(f"    @{account}: {len(posts)} tweets")
        time.sleep(1.0)

    return all_posts


def run_twitter_scraper() -> list:
    """Main entry point for Twitter/X scraper."""
    print("\U0001f680 Starting Twitter/X scraper (Google News indexed tweets)...")

    all_posts = []

    # Search-based tweets
    try:
        search_posts = scrape_twitter_search()
        all_posts.extend(search_posts)
    except Exception as e:
        print(f"  \u274c Twitter search scrape failed: {e}")

    # Account-based tweets
    try:
        account_posts = scrape_twitter_accounts()
        all_posts.extend(account_posts)
    except Exception as e:
        print(f"  \u274c Twitter account scrape failed: {e}")

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

    print(f"\n\u2705 Scraped {len(unique)} unique tweets \u2192 {SAVE_PATH}")
    return unique


if __name__ == "__main__":
    run_twitter_scraper()
