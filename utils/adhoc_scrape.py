# adhoc_scrape.py — On-demand topic scraper for Ask AI follow-up
# Scrapes Google News RSS + Reddit search for a specific topic,
# enriches results, and appends to the persistent adhoc dataset.
import requests
import json
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
from urllib.parse import quote
from xml.etree import ElementTree as ET
from collections import Counter

ADHOC_PATH = "data/adhoc_scraped_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_rss_date(date_str: str) -> str:
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _scrape_google_news(query: str, max_results: int = 30) -> List[Dict[str, Any]]:
    """Scrape Google News RSS for a topic."""
    posts = []
    try:
        encoded = quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(rss_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return posts
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:max_results]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = re.sub(r"<[^>]+>", "", (item.findtext("description") or "")).strip()

            post_date = _parse_rss_date(pub_date)
            text = title
            if description and description != title:
                text = f"{title}\n{description}"
            if len(text) < 15:
                continue

            posts.append({
                "text": text,
                "title": title,
                "source": "Google News (adhoc)",
                "url": link,
                "username": "",
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": query,
                "score": 0,
                "post_id": f"adhoc_gn_{hash(link) % 10**8}",
                "_adhoc": True,
                "_adhoc_query": query,
            })
    except Exception as e:
        print(f"  [WARN] Google News failed for '{query}': {e}")
    return posts


def _scrape_reddit_search(query: str, max_results: int = 30) -> List[Dict[str, Any]]:
    """Search Reddit for a topic via the public JSON API."""
    posts = []
    try:
        encoded = quote(query)
        url = f"https://www.reddit.com/search.json?q={encoded}&sort=relevance&limit={max_results}"
        r = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=15)
        if r.status_code != 200:
            return posts
        data = r.json()
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            title = p.get("title", "")
            selftext = p.get("selftext", "")
            text = f"{title}\n{selftext}" if selftext else title
            if len(text) < 15:
                continue

            created = p.get("created_utc", 0)
            post_date = datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else datetime.now().strftime("%Y-%m-%d")

            posts.append({
                "text": text[:3000],
                "title": title,
                "source": "Reddit",
                "subreddit": p.get("subreddit", ""),
                "url": f"https://www.reddit.com{p.get('permalink', '')}",
                "username": p.get("author", ""),
                "post_date": post_date,
                "_logged_date": datetime.now().isoformat(),
                "search_term": query,
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "post_id": f"adhoc_rd_{p.get('id', hash(title) % 10**8)}",
                "_adhoc": True,
                "_adhoc_query": query,
            })
    except Exception as e:
        print(f"  [WARN] Reddit search failed for '{query}': {e}")
    return posts


def _basic_enrich(post: Dict[str, Any]) -> Dict[str, Any]:
    """Apply lightweight enrichment to adhoc posts."""
    text_lower = (post.get("text", "") + " " + post.get("title", "")).lower()

    # Sentiment heuristic
    neg_kw = ["complaint", "issue", "problem", "frustrated", "broken", "scam", "terrible", "awful", "hate", "worst"]
    pos_kw = ["love", "great", "amazing", "excellent", "impressed", "best", "happy"]
    neg_score = sum(1 for k in neg_kw if k in text_lower)
    pos_score = sum(1 for k in pos_kw if k in text_lower)
    if neg_score > pos_score:
        post["brand_sentiment"] = "Negative"
    elif pos_score > neg_score:
        post["brand_sentiment"] = "Positive"
    else:
        post["brand_sentiment"] = "Neutral"

    # Type heuristic
    if any(k in text_lower for k in ["should", "wish", "need", "please add", "feature request"]):
        post["type_tag"] = "Feature Request"
    elif any(k in text_lower for k in ["bug", "broken", "crash", "error", "glitch"]):
        post["type_tag"] = "Bug Report"
    elif neg_score > 0:
        post["type_tag"] = "Complaint"
    else:
        post["type_tag"] = "Discussion"

    # Subtag / topic detection
    topic_map = {
        "Vault": ["vault", "psa vault", "ebay vault"],
        "Authentication": ["authentication", "authenticity guarantee", "ag "],
        "Grading": ["grading", "psa", "bgs", "cgc", "beckett"],
        "Price Guide": ["price guide", "card ladder", "scan to price"],
        "Shipping": ["shipping", "tracking", "label", "damaged"],
        "Payments": ["payment", "payout", "funds held"],
        "Returns": ["return", "inad", "refund"],
        "Fees": ["fee", "final value", "commission"],
        "Promoted Listings": ["promoted listing", "promoted standard"],
        "Search": ["search", "best match", "visibility"],
        "Live Shopping": ["live break", "whatnot", "live shopping"],
        "Acquisition": ["acquisition", "acquired", "merger", "bought", "purchase"],
    }
    for topic, keywords in topic_map.items():
        if any(kw in text_lower for kw in keywords):
            post["subtag"] = topic
            break
    else:
        post["subtag"] = "General"

    post["taxonomy"] = {
        "type": post.get("type_tag", "Discussion"),
        "topic": post.get("subtag", "General"),
        "theme": post.get("subtag", "General"),
    }
    post["persona"] = "Unknown"
    post["signal_strength"] = 30
    post["clarity"] = "Unknown"
    return post


def _load_existing() -> List[Dict[str, Any]]:
    """Load existing adhoc posts."""
    if os.path.exists(ADHOC_PATH):
        try:
            with open(ADHOC_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save(posts: List[Dict[str, Any]]):
    """Save adhoc posts."""
    os.makedirs(os.path.dirname(ADHOC_PATH) if os.path.dirname(ADHOC_PATH) else ".", exist_ok=True)
    with open(ADHOC_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def run_adhoc_scrape(topic: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Run an ad-hoc scrape for a specific topic.

    Returns:
        (new_posts, summary_message)
    """
    print(f"🔍 Ad-hoc scrape: '{topic}'")

    # Generate multiple search queries from the topic
    queries = [topic]
    # Add variations
    words = topic.lower().split()
    if len(words) >= 2:
        queries.append(f'"{topic}"')  # Exact phrase
    # Add site-specific queries
    queries.append(f"{topic} site:reddit.com")

    all_posts = []

    # Google News
    for q in queries[:3]:
        print(f"  📰 Google News: {q}")
        posts = _scrape_google_news(q)
        all_posts.extend(posts)
        time.sleep(0.5)

    # Reddit search
    print(f"  💬 Reddit: {topic}")
    reddit_posts = _scrape_reddit_search(topic)
    all_posts.extend(reddit_posts)

    # Deduplicate by URL or title
    seen = set()
    unique = []
    for p in all_posts:
        key = p.get("url", "") or p.get("title", "")[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    # Enrich
    enriched = [_basic_enrich(p) for p in unique]

    # Merge with existing adhoc data
    existing = _load_existing()
    existing_urls = {p.get("url", "") for p in existing if p.get("url")}
    new_posts = [p for p in enriched if p.get("url", "") not in existing_urls]
    merged = existing + new_posts
    _save(merged)

    # Summary
    source_counts = Counter(p.get("source", "?") for p in new_posts)
    summary_parts = [f"{cnt} from {src}" for src, cnt in source_counts.most_common()]
    summary = f"Scraped **{len(new_posts)} new posts** for \"{topic}\" ({', '.join(summary_parts)}). Total adhoc dataset: {len(merged)} posts."

    print(f"  ✅ {len(new_posts)} new posts added (total adhoc: {len(merged)})")
    return new_posts, summary


if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Beckett acquisition PSA Collectors Universe"
    posts, summary = run_adhoc_scrape(topic)
    print(summary)
